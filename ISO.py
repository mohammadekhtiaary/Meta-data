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
    Basic parser to extract reference metadata from a MapInfo MIF file.
    """
    content = file_content.decode("utf-8")
    ref = {
        "geometry_type": "Unknown",
        "total_features": 0,
        "geographic_extent": None
    }

    # Heuristic: Check for common MIF geometry declarations
    if "Region" in content:
        ref["geometry_type"] = "MULTIPOLYGON"
    elif "Line" in content or "Pline" in content:
        ref["geometry_type"] = "LINESTRING"
    elif "Point" in content:
        ref["geometry_type"] = "POINT"

    # Heuristic: Count coordinate entries to estimate features
    # (In a real scenario, you'd count specific MIF keywords)
    ref["total_features"] = content.count("Point") + content.count("Region") + content.count("Pline")

    # CoordSys logic for Extent (Simplified for demo)
    if "CoordSys" in content:
        ref["geographic_extent"] = "Global/Projected"  # Reference flag

    return ref


# --- 3. INFERENCE LOGIC FUNCTIONS ---
def get_rule_based_metadata(df):
    return {
        "method": "Rule-Based",
        "geometry_type": df['WKT_LNG_LAT'].str.extract(r'^([A-Z]+)',
                                                       expand=False).unique().tolist() if 'WKT_LNG_LAT' in df.columns else "Unknown",
        "total_features": len(df)
    }


def get_statistical_metadata(df):
    return {"method": "Statistical", "total_features": len(df)}


def get_heuristic_metadata(df):
    return {"method": "Heuristic", "total_features": len(df)}


# --- 4. EVALUATION ENGINE ---
def calculate_veregin_score(inferred_val, reference_val, field_name):
    scores = {"Correctness": 0, "Completeness": 0, "Consistency": 0, "Granularity": 0}

    if inferred_val: scores["Completeness"] = 2

    # Correctness check
    if str(inferred_val).strip().lower() in str(reference_val).strip().lower():
        scores["Correctness"] = 2

    scores["Consistency"] = 2
    scores["Granularity"] = 2
    scores["Total"] = sum(scores.values())
    return scores


# --- 5. SIDEBAR ---
st.sidebar.header("Settings")
inference_method = st.sidebar.selectbox("Method", ["Rule-Based (Schema)", "Statistical Profiling", "Heuristic-Based"])

st.sidebar.divider()
st.sidebar.header("Evaluation Reference")
ref_file = st.sidebar.file_uploader("Upload Reference MIF File", type=['mif'])

# --- 6. MAIN EXECUTION ---
uploaded_file = st.file_uploader("Choose a CSV dataset file", type=['csv'])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, sep=';')
    st.subheader("Data Preview")
    st.dataframe(df.head(5))

    # Shared Metadata logic
    geo_extent = {
        "min_x": float(df['LNG'].min()) if 'LNG' in df.columns else None,
        "max_x": float(df['LNG'].max()) if 'LNG' in df.columns else None,
    }

    # Run selected inference
    if inference_method == "Rule-Based (Schema)":
        metadata = get_rule_based_metadata(df)
    elif inference_method == "Statistical Profiling":
        metadata = get_statistical_metadata(df)
    else:
        metadata = get_heuristic_metadata(df)

    metadata["geographic_extent"] = geo_extent
    metadata["total_features"] = len(df)

    # UI Layout
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Generated Metadata")
        st.json(metadata)

    # --- EVALUATION SECTION ---
    if ref_file is not None:
        try:
            # Parse the uploaded MIF for reference values
            reference_data = parse_mif_reference(ref_file.read())

            st.divider()
            st.header("⚖️ ISO Evaluation (Reference: MIF File)")

            comparison_map = {
                "geometry_type": (metadata.get("geometry_type"), reference_data.get("geometry_type")),
                "total_features": (metadata.get("total_features"), reference_data.get("total_features"))
            }

            eval_report = []
            for field, values in comparison_map.items():
                inf, ref = values
                res = calculate_veregin_score(inf, ref, field)
                res["Field"] = field
                res["Inferred"] = str(inf)
                res["Reference (MIF)"] = str(ref)
                eval_report.append(res)

            st.table(pd.DataFrame(eval_report).set_index("Field"))

        except Exception as e:
            st.error(f"Error parsing MIF: {e}")
    else:
        st.info("ℹ️ Upload a .mif file in the sidebar to run the Veregin matrix comparison.")

    # Download Button
    st.download_button("Download Metadata JSON", json.dumps(metadata), "metadata.json")