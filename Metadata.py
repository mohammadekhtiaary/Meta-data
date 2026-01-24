import streamlit as st
import pandas as pd
import json
import re

# --- 1. SET UP THE PAGE ---
st.set_page_config(page_title="GeoMeta Portal", layout="wide")
st.title("🛰️ Automated Geospatial Metadata Generator")

# --- 2. SIDEBAR CONFIGURATION ---
st.sidebar.header("Inference Settings")
inference_method = st.sidebar.selectbox(
    "Select Inference Method",
    ["Rule-Based (Schema)", "Statistical Profiling", "Heuristic-Based"]
)


# --- 3. HELPER FUNCTIONS ---

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


# --- 4. INFERENCE LOGIC FUNCTIONS ---

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


# --- 5. MAIN INTERFACE ---
uploaded_file = st.file_uploader("Choose a CSV file", type=['csv'])

if uploaded_file is not None:
    # Attempt to read with semicolon, fallback to comma
    try:
        df = pd.read_csv(uploaded_file, sep=';')
        if len(df.columns) <= 1:  # Basic check if separator failed
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, sep=',')
    except Exception as e:
        st.error(f"Error loading file: {e}")

    st.subheader("Data Preview")
    st.dataframe(df.head(5))

    # Calculate Geographic Extent
    geo_extent = {
        "min_x": float(df['LNG'].min()) if 'LNG' in df.columns else None,
        "max_x": float(df['LNG'].max()) if 'LNG' in df.columns else None,
        "min_y": float(df['LAT'].min()) if 'LAT' in df.columns else None,
        "max_y": float(df['LAT'].max()) if 'LAT' in df.columns else None,
    }

    # Execute selected method
    if inference_method == "Rule-Based (Schema)":
        metadata = get_rule_based_metadata(df)
    elif inference_method == "Statistical Profiling":
        metadata = get_statistical_metadata(df)
    else:
        metadata = get_heuristic_metadata(df)

    # Append shared metadata
    metadata["geographic_extent"] = geo_extent
    metadata["total_features"] = len(df)

    # --- 6. DISPLAY RESULTS ---
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(f"Generated Metadata ({inference_method})")
        st.json(metadata)

    with col2:
        st.subheader("Quick Stats")
        st.metric("Total Features", len(df))

        # Display CRS Information prominently
        crs = metadata["spatial_reference"]
        st.info(f"**Detected CRS:** {crs.get('name', 'Unknown')} ({crs.get('code', 'N/A')})")

        if geo_extent["min_x"] is not None:
            st.write("**Bounding Box**")
            st.caption(f"Lon: {geo_extent['min_x']} to {geo_extent['max_x']}")
            st.caption(f"Lat: {geo_extent['min_y']} to {geo_extent['max_y']}")

        # Download Button
        json_string = json.dumps(metadata, indent=4)
        st.download_button(
            label="Download Metadata JSON",
            file_name=f"metadata_{inference_method.lower().replace(' ', '_')}.json",
            mime="application/json",
            data=json_string,
        )