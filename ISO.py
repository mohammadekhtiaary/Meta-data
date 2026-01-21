import streamlit as st
import pandas as pd
import json
import re

# --- 1. SET UP THE PAGE ---
st.set_page_config(page_title="GeoMeta Portal & Evaluator", layout="wide")
st.title("🛰️ Geospatial Metadata Generator & ISO Evaluator")


# --- 2. INFERENCE LOGIC FUNCTIONS ---

def get_rule_based_metadata(df):
    """Method 1: Extracts metadata directly from file structure and schema."""
    return {
        "method": "Rule-Based",
        "geometry_type": df['WKT_LNG_LAT'].str.extract(r'^([A-Z]+)',
                                                       expand=False).unique().tolist() if 'WKT_LNG_LAT' in df.columns else "Unknown",
        "attributes": {col: str(df[col].dtype) for col in df.columns}
    }


def get_statistical_metadata(df):
    """Method 2: Computes summary statistics."""
    stats = {}
    for col in df.columns:
        stats[col] = {"dtype": str(df[col].dtype), "unique_count": int(df[col].nunique())}
    return {"method": "Statistical Profiling", "attribute_stats": stats}


def get_heuristic_metadata(df):
    """Method 3: Pattern-based rules."""
    heuristics = {}
    for col in df.columns:
        heuristics[col] = "Categorical" if df[col].nunique() < 10 else "General Attribute"
    return {"method": "Heuristic-Based", "classifications": heuristics}


# --- 3. EVALUATION ENGINE (Veregin's Matrix) ---

def calculate_veregin_score(inferred_val, reference_val, field_name):
    """Scores a field based on Veregin's criteria (0-2)."""
    scores = {"Correctness": 0, "Completeness": 0, "Consistency": 0, "Granularity": 0}

    # 1. Completeness
    if inferred_val is not None and inferred_val != "Unknown" and inferred_val != []:
        scores["Completeness"] = 2
    else:
        return scores

        # 2. Correctness
    if str(inferred_val).strip().lower() == str(reference_val).strip().lower():
        scores["Correctness"] = 2
    elif str(inferred_val).lower() in str(reference_val).lower():
        scores["Correctness"] = 1

    # 3. Consistency
    if field_name == "geographic_extent":
        if isinstance(inferred_val, dict) and inferred_val.get("min_x", 0) < inferred_val.get("max_x", 0):
            scores["Consistency"] = 2
    else:
        scores["Consistency"] = 2

    # 4. Granularity
    if field_name == "geometry_type" and any(x in str(inferred_val).upper() for x in ['MULTI', 'POINT', 'LINE']):
        scores["Granularity"] = 2
    else:
        scores["Granularity"] = 1

    scores["Total"] = sum(scores.values())
    return scores


# --- 4. SIDEBAR CONFIGURATION ---
st.sidebar.header("Settings")
inference_method = st.sidebar.selectbox(
    "Select Inference Method",
    ["Rule-Based (Schema)", "Statistical Profiling", "Heuristic-Based"]
)

st.sidebar.divider()
st.sidebar.header("Evaluation Reference")
ref_file = st.sidebar.file_uploader("Upload Reference Metadata (JSON/MID)", type=['json', 'mid'])

# --- 5. MAIN INTERFACE ---
uploaded_file = st.file_uploader("Choose a CSV dataset file", type=['csv'])

if uploaded_file is not None:
    # Read Dataset
    df = pd.read_csv(uploaded_file, sep=';')

    st.subheader("Data Preview")
    st.dataframe(df.head(5))

    # Calculate Shared Metadata (Extent)
    geo_extent = {
        "min_x": float(df['LNG'].min()) if 'LNG' in df.columns else None,
        "max_x": float(df['LNG'].max()) if 'LNG' in df.columns else None,
        "min_y": float(df['LAT'].min()) if 'LAT' in df.columns else None,
        "max_y": float(df['LAT'].max()) if 'LAT' in df.columns else None,
    }

    # Execute Inference Method
    if inference_method == "Rule-Based (Schema)":
        metadata = get_rule_based_metadata(df)
    elif inference_method == "Statistical Profiling":
        metadata = get_statistical_metadata(df)
    else:
        metadata = get_heuristic_metadata(df)

    metadata["geographic_extent"] = geo_extent
    metadata["total_features"] = len(df)

    # --- DISPLAY METADATA RESULTS ---
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader(f"Generated Metadata ({inference_method})")
        st.json(metadata)
    with col2:
        st.subheader("Quick Stats")
        st.metric("Total Features", len(df))

    # --- 6. EVALUATION SECTION ---
    if ref_file is not None:
        try:
            reference_data = json.load(ref_file)
            st.divider()
            st.header("⚖️ ISO Standard Evaluation (Veregin’s Matrix)")

            # Map values for comparison
            # Note: reference_data must contain these keys
            comparison_map = {
                "geometry_type": (metadata.get("geometry_type"), reference_data.get("geometry_type")),
                "total_features": (metadata.get("total_features"), reference_data.get("total_features")),
                "geographic_extent": (metadata.get("geographic_extent"), reference_data.get("geographic_extent"))
            }

            eval_report = []
            for field, values in comparison_map.items():
                inferred, reference = values
                f_scores = calculate_veregin_score(inferred, reference, field)
                f_scores["Field"] = field
                eval_report.append(f_scores)

            # Display Table
            eval_df = pd.DataFrame(eval_report).set_index("Field")
            st.table(eval_df)

            # Summary Metrics
            total_score = eval_df["Total"].sum()
            max_score = len(eval_report) * 8
            st.info(f"**Method Performance Score:** {total_score}/{max_score} ({(total_score / max_score) * 100:.1f}%)")

        except Exception as e:
            st.error(f"Error processing reference file: {e}")
    else:
        st.info("💡 Upload a reference file in the sidebar to see ISO Evaluation scores.")

    # Download Generated Metadata
    st.download_button(
        label="Download Metadata JSON",
        file_name="generated_metadata.json",
        mime="application/json",
        data=json.dumps(metadata, indent=4),
    )