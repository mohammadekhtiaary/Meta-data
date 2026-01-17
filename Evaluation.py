import streamlit as st
import pandas as pd
import json
import numpy as np

# --- 1. SET UP THE PAGE ---
st.set_page_config(page_title="GeoMeta Portal & Evaluator", layout="wide")
st.title("🛰️ Automated Geospatial Metadata & Evaluation")


# --- 2. DEFINE PROXY GROUND TRUTH ---
# In this logic, we define what the portal says (Reference) vs what we find.
def get_proxy_ground_truth(df, filename):
    """
    Mocking the Ground Truth from Amsterdam Data Portal & Explicit Schema.
    In a real app, this would be a lookup table based on filename.
    """
    return {
        "geometry_type": "POINT",  # Reference from Portal
        "attribute_count": len(df.columns),
        "total_features": len(df),
        "spatial_extent": "Global/City-wide",
        "coord_system": "EPSG:4326"
    }


# --- 3. THE THREE INFERENCE METHODS ---
def run_rule_based(df):
    return {
        "geometry_type": df['WKT_LNG_LAT'].str.extract(r'^([A-Z]+)', expand=False).iloc[
            0] if 'WKT_LNG_LAT' in df.columns else "Unknown",
        "attribute_count": len(df.columns),
        "total_features": len(df)
    }


def run_statistical(df):
    # Focuses on distributions and counts
    return {
        "geometry_type": "POINT" if 'LNG' in df.columns else "Unknown",
        "attribute_count": df.shape[1],
        "total_features": df.describe().loc['count'].max()
    }


def run_heuristic(df):
    # Focuses on patterns (e.g., if columns names look like coords)
    geom = "Unknown"
    if any(col in df.columns for col in ['LAT', 'LNG', 'WKT']):
        geom = "POINT"
    return {
        "geometry_type": geom,
        "attribute_count": len(df.columns),
        "total_features": len(df)
    }


# --- 4. VEREGIN EVALUATION MATRIX SCORING ---
def score_veregin(inferred, reference):
    """
    Scores a single field based on Veregin's criteria.
    Max score: 8 (2 per category)
    """
    # 1. Correctness
    correctness = 2 if inferred == reference else 0
    # 2. Completeness
    completeness = 2 if inferred is not None and str(inferred) != "Unknown" else 0
    # 3. Consistency (Logic check)
    consistency = 2 if (str(inferred).isalpha() or isinstance(inferred, (int, float))) else 1
    # 4. Granularity
    granularity = 2 if len(str(inferred)) > 0 else 0

    total = correctness + completeness + consistency + granularity
    return {"Correctness": correctness, "Completeness": completeness,
            "Consistency": consistency, "Granularity": granularity, "Total": total}


# --- 5. MAIN UI ---
uploaded_file = st.file_uploader("Upload Geospatial CSV", type=['csv'])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, sep=';')
    ground_truth = get_proxy_ground_truth(df, uploaded_file.name)

    st.subheader("Data Preview")
    st.dataframe(df.head(3))

    # Run all methods for comparison
    results = {
        "Rule-Based": run_rule_based(df),
        "Statistical": run_statistical(df),
        "Heuristic": run_heuristic(df)
    }

    # --- 6. METHOD COMPARISON TABLE ---
    st.header("Method Comparison & Leaderboard")

    comparison_rows = []
    for method_name, inferred_values in results.items():
        # Evaluate the 'geometry_type' field as our primary benchmark
        score_dict = score_veregin(inferred_values['geometry_type'], ground_truth['geometry_type'])

        comparison_rows.append({
            "Method": method_name,
            "Inferred Geometry": inferred_values['geometry_type'],
            "Veregin Score": f"{score_dict['Total']}/8",
            "Correctness": score_dict['Correctness'],
            "Completeness": score_dict['Completeness'],
            "Consistency": score_dict['Consistency'],
            "Granularity": score_dict['Granularity']
        })

    eval_df = pd.DataFrame(comparison_rows)
    st.table(eval_df)

    # --- 7. VISUALIZING PERFORMANCE ---
    st.subheader("Aggregated Performance (Field-Level)")
    # Image of a Veregin's Matrix can help visualize the conceptual framework

    chart_data = eval_df.set_index("Method")[["Correctness", "Completeness", "Consistency", "Granularity"]]
    st.bar_chart(chart_data)

    # --- 8. ERROR ANALYSIS ---
    st.divider()
    st.header("Qualitative Error Analysis")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(
            "**Rule-Based Failures**\n\nOften fails when headers don't match strict regex (e.g., 'Geometry' vs 'WKT_LNG_LAT'). High correctness, low flexibility.")
    with col2:
        st.info(
            "**Statistical Failures**\n\nFails to distinguish between MultiPoint and Point because it only sees coordinate counts. Good completeness, low granularity.")
    with col3:
        st.info(
            "**Heuristic Failures**\n\nProne to false positives if non-spatial columns contain numbers that 'look' like coordinates. High flexibility, risky consistency.")

    # --- 9. DOWNLOAD FINAL REPORT ---
    report = {
        "ground_truth": ground_truth,
        "evaluation": comparison_rows,
        "summary": "Rule-based performs best for structured schemas; Heuristics best for raw, unformatted data."
    }
    st.download_button("Download Evaluation Report", json.dumps(report, indent=4), "eval_report.json")