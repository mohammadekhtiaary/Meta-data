import streamlit as st
import pandas as pd
import json
import numpy as np

# --- 1. SET UP THE PAGE ---
st.set_page_config(page_title="GeoMeta Portal Evaluator", layout="wide")
st.title("🛰️ Geospatial Metadata Evaluation (Veregin Matrix)")


# --- 2. DYNAMIC PROXY GROUND TRUTH ---
# In a production environment, you would scrape the portal or use an API.
# Here we simulate the Reference values from maps.amsterdam.nl
def get_proxy_ground_truth(df, filename):
    """
    Simulating Reference values from Amsterdam Data Portal (e.g., https://maps.amsterdam.nl/open_geodata/?k=99)
    """
    return {
        "geometry_type": "POINT",  # Example: Portal says 'Punt' (Point)
        "attribute_count": 12,  # Example: Portal lists 12 attributes
        "total_features": len(df),  # Reference count
        "spatial_extent": "Amsterdam",
        "coord_system": "EPSG:28992"  # Typical for Amsterdam (Amersfoort/RD New)
    }


# --- 3. UPDATED VEREGIN SCORING LOGIC (0, 1, 2) ---
def score_field_veregin(inferred, reference, field_name):
    """
    Scores a metadata field based on 4 criteria (Max 8 points).
    0: Incorrect/Missing, 1: Partially Correct, 2: Fully Correct
    """
    scores = {"Correctness": 0, "Completeness": 0, "Consistency": 0, "Granularity": 0}

    # 1. Correctness: Direct match
    if str(inferred).lower() == str(reference).lower():
        scores["Correctness"] = 2
    elif str(inferred) in str(reference) or str(reference) in str(inferred):
        scores["Correctness"] = 1

    # 2. Completeness: Was it detected?
    if inferred is not None and str(inferred) != "Unknown":
        scores["Completeness"] = 2

    # 3. Consistency: Logic check (e.g., Point data shouldn't have Polygon attributes)
    # Simple logic: Is the type consistent with the data structure?
    if isinstance(inferred, (int, float)) and inferred >= 0:
        scores["Consistency"] = 2
    elif isinstance(inferred, str) and len(inferred) > 0:
        scores["Consistency"] = 2

    # 4. Granularity: Specificity check
    # Example: MultiPolygon (2) vs Polygon (1) vs Unknown (0)
    if "MULTI" in str(inferred).upper():
        scores["Granularity"] = 2
    elif inferred != "Unknown":
        scores["Granularity"] = 1

    scores["Total"] = sum(scores.values())
    return scores


# --- 4. MOCK INFERENCE METHODS (As per your script) ---
def run_rule_based(df):
    return {"geometry_type": "POINT", "attribute_count": len(df.columns)}


def run_statistical(df):
    return {"geometry_type": "POINT", "attribute_count": df.shape[1]}


def run_heuristic(df):
    return {"geometry_type": "GEOMETRY", "attribute_count": len(df.columns)}


# --- 5. MAIN UI & EVALUATION ---
uploaded_file = st.file_uploader("Upload Amsterdam Data Portal CSV", type=['csv'])

if uploaded_file:
    df = pd.read_csv(uploaded_file, sep=None, engine='python')  # Auto-detect separator
    ground_truth = get_proxy_ground_truth(df, uploaded_file.name)

    methods = {
        "Rule-Based": run_rule_based(df),
        "Statistical": run_statistical(df),
        "Heuristic": run_heuristic(df)
    }

    # --- EVALUATION ENGINE ---
    all_evals = []

    for method_name, inferred_data in methods.items():
        # Evaluate multiple fields
        for field in ["geometry_type", "attribute_count"]:
            inf_val = inferred_data.get(field)
            ref_val = ground_truth.get(field)

            scores = score_field_veregin(inf_val, ref_val, field)
            scores.update({
                "Method": method_name,
                "Field": field,
                "Inferred": inf_val,
                "Reference": ref_val
            })
            all_evals.append(scores)

    eval_df = pd.DataFrame(all_evals)

    # --- 6. DISPLAY RESULTS ---

    # A. Method-Level Performance (Aggregated)
    st.header("🏆 Method-Level Leaderboard")
    method_perf = eval_df.groupby("Method")["Total"].sum().reset_index()
    # Normalize to 100% or show raw points
    method_perf["Rank Score"] = (method_perf["Total"] / (len(eval_df['Field'].unique()) * 8)) * 100
    st.dataframe(method_perf.sort_values(by="Rank Score", ascending=False))

    # B. Field-Level Performance
    st.header("📊 Field-Level Performance")
    field_perf = eval_df.pivot_table(
        index="Field",
        columns="Method",
        values="Total",
        aggfunc="mean"
    )
    st.table(field_perf)

    # C. Veregin Matrix Breakdown
    st.header("🔍 Detailed Veregin Matrix Breakdown")
    st.dataframe(eval_df[["Method", "Field", "Correctness", "Completeness", "Consistency", "Granularity", "Total"]])

    # --- 7. QUALITATIVE ERROR ANALYSIS ---
    st.divider()
    st.header("📝 Qualitative Error Analysis")

    for method in methods.keys():
        with st.expander(f"Analysis for {method}"):
            low_scores = eval_df[(eval_df["Method"] == method) & (eval_df["Total"] < 6)]
            if not low_scores.empty:
                st.warning(f"Systematic failures detected in: {', '.join(low_scores['Field'].unique())}")
                st.write("Pattern: Inferred values lack the granularity required by the Amsterdam Portal schema.")
            else:
                st.success("High alignment with Proxy Ground Truth.")