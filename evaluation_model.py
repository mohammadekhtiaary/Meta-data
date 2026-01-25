import streamlit as st
import pandas as pd
import json
import re

# --- 1. SET UP THE PAGE ---
st.set_page_config(page_title="GeoMeta Portal & Evaluator", layout="wide")
st.title("️ Geospatial Metadata Generator & Evaluator")


# --- 2. HELPER FUNCTIONS (Must be defined first) ---

def infer_crs(df):
    """Detects if the coordinates likely belong to WGS84 (EPSG:4326)."""
    if 'LAT' in df.columns and 'LNG' in df.columns:
        try:
            # Check if values fall within standard geographic bounds
            lat_check = df['LAT'].between(-90, 90).all()
            lng_check = df['LNG'].between(-180, 180).all()

            if lat_check and lng_check:
                return {
                    "auth_name": "EPSG",
                    "code": "4326",
                    "name": "WGS 84",
                    "units": "Decimal Degrees"
                }
        except:
            pass
    return {"name": "Unknown / Projected", "code": "Undefined"}


def parse_mif_reference(file_content):
    """Extracts reference metadata from a MapInfo MIF file content."""
    try:
        content = file_content.decode("utf-8")
    except UnicodeDecodeError:
        content = file_content.decode("latin-1")

    ref = {"geometry_type": "Unknown", "total_features": 0}

    # MIF geometry declarations: Point, Line, Pline, Region
    if "Region" in content:
        ref["geometry_type"] = "POLYGON"
    elif "Line" in content or "Pline" in content:
        ref["geometry_type"] = "LINESTRING"
    elif "Point" in content:
        ref["geometry_type"] = "POINT"

    features = len(re.findall(r'^(Point|Line|Pline|Region|Rect|Ellipse|Arc)', content, re.MULTILINE | re.IGNORECASE))
    ref["total_features"] = features if features > 0 else "Unknown"
    return ref


# --- 3. UPDATED INFERENCE LOGIC ---

def get_rule_based_metadata(df):
    """Method 1: Extracts metadata directly from file structure and schema."""
    geom_types = "Unknown"
    if 'WKT_LNG_LAT' in df.columns:
        extracted = df['WKT_LNG_LAT'].str.extract(r'^([A-Z]+)', expand=False).unique().tolist()
        geom_types = [g for g in extracted if pd.notna(g)]

    return {
        "method": "Rule-Based",
        "geometry_type": geom_types,
        "spatial_reference": infer_crs(df),
        "attributes": {col: str(df[col].dtype) for col in df.columns}
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
        "geometry_type": "POINT" if ('LAT' in df.columns) else "Unknown",
        "spatial_reference": infer_crs(df),
        "attribute_stats": stats
    }


def get_heuristic_metadata(df):
    """Method 3: Pattern-based rules to classify attribute roles."""
    heuristics = {}
    for col in df.columns:
        unique_pct = df[col].nunique() / len(df) if len(df) > 0 else 0
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
        "geometry_type": "POINT" if ('LAT' in df.columns) else "Unknown",
        "spatial_reference": infer_crs(df),
        "classifications": heuristics
    }


# --- 4. EVALUATION ENGINE ---

# def calculate_veregin_score(inferred_val, reference_val, field_name):
#     scores = {
#         "Correctness": 0,
#         "Completeness": 0,
#         "Consistency": 0,
#         "Granularity": 0
#     }
#
#     # 1. Completeness
#     if inferred_val and str(inferred_val) not in ["Unknown", "[]", "None"]:
#         scores["Completeness"] = 2
#     else:
#         return scores
#
#     # 2. Normalization
#     def normalize(v):
#         if isinstance(v, list):
#             v = v[0] if len(v) > 0 else ""
#         return str(v).strip().upper()
#
#     inf_norm = normalize(inferred_val)
#     ref_norm = normalize(reference_val)
#
#     # 3. Correctness
#     if inf_norm == ref_norm and inf_norm != "":
#         scores["Correctness"] = 2
#     elif inf_norm in ref_norm or ref_norm in inf_norm:
#         scores["Correctness"] = 1
#
#     # 4. Consistency
#     scores["Consistency"] = 2
#
#     # 5. Granularity (Binary)
#     if (
#         scores["Correctness"] == 2
#         and inf_norm not in ["GEOMETRY", "UNKNOWN"]
#         and "ESTIMATED" not in inf_norm
#     ):
#         scores["Granularity"] = 1
#     else:
#         scores["Granularity"] = 0
#
#     scores["Total"] = sum(scores.values())
#     return scores
def calculate_veregin_score(inferred_val, reference_val, field_name):
    scores = {
        "Correctness": 0,
        "Completeness": 0,
        "Consistency": 0,
        "Granularity": 0
    }

    # --- 1. Completeness ---
    if inferred_val and str(inferred_val) not in ["Unknown", "[]", "None"]:
        scores["Completeness"] = 2
    else:

        return scores

    # --- 2. Normalization ---
    def normalize(v):
        if isinstance(v, list):
            v = v[0] if len(v) > 0 else ""
        return str(v).strip().upper()

    inf_norm = normalize(inferred_val)
    ref_norm = normalize(reference_val)

    # --- 3. Correctness ---
    if inf_norm == ref_norm and inf_norm != "":
        scores["Correctness"] = 2
    elif inf_norm in ref_norm or ref_norm in inf_norm:
        scores["Correctness"] = 1
    else:
        scores["Correctness"] = 0

    # --- 4. Consistency ---
    scores["Consistency"] = 2

    # --- 5. Granularity ( Correctness و Completeness) ---
    if scores["Correctness"] == 2 and scores["Completeness"] == 2:
        scores["Granularity"] = 1
    else:
        scores["Granularity"] = 0

    scores["Total"] = sum(scores.values())
    return scores
# --- 5. APP INTERFACE ---

st.sidebar.header("Settings")
inference_method = st.sidebar.selectbox(
    "Select Inference Method",
    ["Rule-Based (Schema)", "Statistical Profiling", "Heuristic-Based"]
)

st.sidebar.divider()
st.sidebar.header("Evaluation Reference")
ref_file = st.sidebar.file_uploader("Upload Reference MIF File", type=['mif'])

uploaded_file = st.file_uploader("Choose a CSV dataset file", type=['csv'])

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, sep=';')
        if len(df.columns) <= 1:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=',')
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        st.stop()

    st.subheader("Data Preview")
    st.dataframe(df.head(5))

    # Trigger selected inference
    if inference_method == "Rule-Based (Schema)":
        metadata = get_rule_based_metadata(df)
    elif inference_method == "Statistical Profiling":
        metadata = get_statistical_metadata(df)
    else:
        metadata = get_heuristic_metadata(df)

    # Attach universal metadata
    metadata["total_features"] = len(df)
    metadata["geographic_extent"] = {
        "min_x": float(df['LNG'].min()) if 'LNG' in df.columns else None,
        "max_x": float(df['LNG'].max()) if 'LNG' in df.columns else None,
        "min_y": float(df['LAT'].min()) if 'LAT' in df.columns else None,
        "max_y": float(df['LAT'].max()) if 'LAT' in df.columns else None,
    }

    # UI Layout
    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.subheader("Generated Metadata")
        st.json(metadata)
    with col_right:
        st.subheader("Quick Stats")
        st.metric("Total Features", len(df))
        crs_info = metadata.get("spatial_reference", {})
        st.info(f"**Detected CRS:** {crs_info.get('name', 'Unknown')}")

    #  Evaluation
    if ref_file is not None:
        try:
            ref_data = parse_mif_reference(ref_file.read())
            st.divider()
            st.header(" Standard Evaluation")

            comp_map = {
                "geometry_type": (metadata.get("geometry_type"), ref_data.get("geometry_type")),
                "total_features": (metadata.get("total_features"), ref_data.get("total_features")),
            }

            eval_results = []
            for field, vals in comp_map.items():
                inf, ref = vals
                f_scores = calculate_veregin_score(inf, ref, field)
                f_scores.update({"Field": field, "Inferred": str(inf), "Reference": str(ref)})
                eval_results.append(f_scores)

            st.table(pd.DataFrame(eval_results).set_index("Field"))
        except Exception as e:
            st.error(f"Evaluation Error: {e}")

    st.download_button("Download JSON Metadata", json.dumps(metadata, indent=4), "metadata.json")