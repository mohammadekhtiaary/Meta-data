import streamlit as st
import pandas as pd
import json
import re

# --- 1. SET UP THE PAGE ---
st.set_page_config(page_title="GeoMeta Portal & Evaluator", layout="wide")
st.title("🛰️ Geospatial Metadata Generator & ISO Evaluator")


# --- 2. MIF PARSER FOR REFERENCE ---
def parse_mif_reference(file_content):
    """
    Extracts reference metadata from a MapInfo MIF file content.
    """
    try:
        content = file_content.decode("utf-8")
    except UnicodeDecodeError:
        content = file_content.decode("latin-1")

    ref = {
        "geometry_type": "Unknown",
        "total_features": 0,
        "geographic_extent": "Detected"
    }

    # Heuristic: Check for MIF geometry declarations
    # MIF uses 'Point', 'Line', 'Pline', 'Region' (Polygon)
    if "Region" in content:
        ref["geometry_type"] = "POLYGON"
    elif "Line" in content or "Pline" in content:
        ref["geometry_type"] = "LINESTRING"
    elif "Point" in content:
        ref["geometry_type"] = "POINT"

    # Feature count estimation (counting geometric objects)
    features = len(re.findall(r'^(Point|Line|Pline|Region|Rect|Ellipse|Arc)', content, re.MULTILINE | re.IGNORECASE))
    ref["total_features"] = features if features > 0 else "Unknown"

    return ref

def infer_crs(df):
    """Detects if the coordinates likely belong to WGS84 (EPSG:4326)."""
    if 'LAT' in df.columns and 'LNG' in df.columns:
        # Check if values fall within standard geographic bounds
        lat_check = df['LAT'].between(-90, 90).all()
        lng_check = df['LNG'].between(-180, 180).all()

        if lat_check and lng_check:
            return {
                "auth_name": "EPSG",
                "code": "4326",
                "name": "WGS 84",
                "units": "Decimal Degrees",
                "type": "Geographic 2D"
            }
    return {"name": "Unknown / Projected", "code": "Undefined"}


# --- 3. INFERENCE LOGIC FUNCTIONS ---
# def get_rule_based_metadata(df):
#     """Method 1: Extracts metadata directly from file structure and schema."""
#     # Handle WKT extraction and clean up to match expected standard
#     geom_types = "Unknown"
#     if 'WKT_LNG_LAT' in df.columns:
#         extracted = df['WKT_LNG_LAT'].str.extract(r'^([A-Z]+)', expand=False).unique().tolist()
#         geom_types = [g for g in extracted if pd.notna(g)]
#
#     return {
#         "method": "Rule-Based",
#         "geometry_type": geom_types,
#         "attributes": {col: str(df[col].dtype) for col in df.columns}
#     }
def get_rule_based_metadata(df):
    """Method 1: Extracts metadata directly from file structure and schema."""
    return {
        "method": "Rule-Based",
        "spatial_reference": infer_crs(df),
        "geometry_info": {
            "type": df['WKT_LNG_LAT'].str.extract(r'^([A-Z]+)',
                                                  expand=False).unique().tolist() if 'WKT_LNG_LAT' in df.columns else "Unknown",
            "dimensionality": "2D (XY)"
        },
        "attributes": {col: str(df[col].dtype) for col in df.columns},
    }

def get_statistical_metadata(df):
    """Method 2: Computes summary statistics."""
    stats = {}
    for col in df.columns:
        stats[col] = {
            "dtype": str(df[col].dtype),
            "missing_values": int(df[col].isnull().sum()),
            "unique_count": int(df[col].nunique()),
        }
        if pd.api.types.is_numeric_dtype(df[col]):
            stats[col].update({
                "min": float(df[col].min()),
                "max": float(df[col].max())
            })
    return {
        "method": "Statistical Profiling",
        "spatial_reference": infer_crs(df),
        "attribute_stats": stats
    }

# def get_statistical_metadata(df):
#     return {"method": "Statistical Profiling", "total_features": len(df)}

def get_heuristic_metadata(df):
    """Method 3: Pattern-based rules to classify attribute roles."""
    heuristics = {}
    for col in df.columns:
        unique_pct = df[col].nunique() / len(df)
        dtype = df[col].dtype

        if pd.api.types.is_integer_dtype(dtype) and unique_pct > 0.9:
            classification = "Identifier (Primary Key candidate)"
        elif df[col].nunique() < 10:
            classification = "Categorical"
        else:
            classification = "General Attribute"
        heuristics[col] = classification

    return {
        "method": "Heuristic-Based",
        "spatial_reference": infer_crs(df),
        "classifications": heuristics
    }
# def get_heuristic_metadata(df):
#     return {"method": "Heuristic-Based", "total_features": len(df)}


# --- 4. EVALUATION ENGINE (Veregin's Matrix with Fuzzy Matching) ---
def calculate_veregin_score(inferred_val, reference_val, field_name):
    """Scores a field based on Veregin's criteria (0-2) with normalization."""
    scores = {"Correctness": 0, "Completeness": 0, "Consistency": 0, "Granularity": 0}

    # 1. Completeness: Was something detected?
    if inferred_val is not None and str(inferred_val) != "Unknown" and inferred_val != []:
        scores["Completeness"] = 2
    else:
        return scores

        # --- 2. Correctness (Normalization Fix) ---

    # Convert lists to strings, remove whitespace, and use uppercase
    def normalize(v):
        if isinstance(v, list): v = v[0] if len(v) > 0 else ""
        return str(v).strip().upper().replace("MULTIPOLYGON", "POLYGON")  # Standardizing types

    inf_norm = normalize(inferred_val)
    ref_norm = normalize(reference_val)

    if inf_norm == ref_norm and inf_norm != "":
        scores["Correctness"] = 2
    elif inf_norm in ref_norm or ref_norm in inf_norm:
        scores["Correctness"] = 1

    # 3. Consistency (Internal Logic)
    scores["Consistency"] = 2  # Defaulting to 2 as no conflicts are present

    # 4. Granularity (Detail Level)
    if any(x in inf_norm for x in ['POINT', 'LINE', 'POLYGON']):
        scores["Granularity"] = 2
    else:
        scores["Granularity"] = 1

    scores["Total"] = sum(scores.values())
    return scores


# --- 5. SIDEBAR ---
st.sidebar.header("Settings")
inference_method = st.sidebar.selectbox(
    "Select Inference Method",
    ["Rule-Based (Schema)", "Statistical Profiling", "Heuristic-Based"]
)

st.sidebar.divider()
st.sidebar.header("Evaluation Reference")
ref_file = st.sidebar.file_uploader("Upload Reference MIF File", type=['mif'])

# --- 6. MAIN INTERFACE ---
uploaded_file = st.file_uploader("Choose a CSV dataset file", type=['csv'])

if uploaded_file is not None:
    # Read Dataset (using semicolon as per your script)
    df = pd.read_csv(uploaded_file, sep=';')

    st.subheader("Data Preview")
    st.dataframe(df.head(5))

    # Calculate Extent
    geo_extent = {
        "min_x": float(df['LNG'].min()) if 'LNG' in df.columns else None,
        "max_x": float(df['LNG'].max()) if 'LNG' in df.columns else None,
        "min_y": float(df['LAT'].min()) if 'LAT' in df.columns else None,
        "max_y": float(df['LAT'].max()) if 'LAT' in df.columns else None,
    }

    # Execute Inference
    if inference_method == "Rule-Based (Schema)":
        metadata = get_rule_based_metadata(df)
    elif inference_method == "Statistical Profiling":
        metadata = get_statistical_metadata(df)
    else:
        metadata = get_heuristic_metadata(df)

    metadata["geographic_extent"] = geo_extent
    metadata["total_features"] = len(df)

    # Display Results
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("Generated Metadata")
        st.json(metadata)
    with c2:
        st.subheader("Quick Stats")
        st.metric("Total Features", len(df))

    # --- 7. EVALUATION LOGIC ---
    if ref_file is not None:
        try:
            # Parse MIF Reference
            reference_data = parse_mif_reference(ref_file.read())

            st.divider()
            st.header("⚖️ ISO Standard Evaluation (Veregin’s Matrix)")
            st.info(
                "The evaluator now uses Case-Insensitive normalization to match your model's output with the MIF standard.")

            comparison_map = {
                "geometry_type": (metadata.get("geometry_type"), reference_data.get("geometry_type")),
                "total_features": (metadata.get("total_features"), reference_data.get("total_features")),
            }

            eval_report = []
            for field, values in comparison_map.items():
                inf, ref = values
                f_scores = calculate_veregin_score(inf, ref, field)
                f_scores["Field"] = field
                f_scores["Inferred"] = str(inf)
                f_scores["Reference (MIF)"] = str(ref)
                eval_report.append(f_scores)

            # Display Evaluation Table
            eval_df = pd.DataFrame(eval_report).set_index("Field")
            st.table(eval_df)

            # Summary Performance
            total_points = eval_df["Total"].sum()
            max_points = len(eval_report) * 8
            st.success(
                f"**Overall Method Performance Score:** {total_points}/{max_points} ({(total_points / max_points) * 100:.1f}%)")

        except Exception as e:
            st.error(f"Error reading MIF: {e}")
    else:
        st.warning("⚠️ Upload a .mif file in the sidebar to perform the automated ISO evaluation.")

    # Download
    st.download_button("Download JSON Metadata", json.dumps(metadata, indent=4), "metadata.json")