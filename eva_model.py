import streamlit as st
import pandas as pd
import json
import plotly.graph_objects as go
from math import sqrt

# --- 1. SET UP THE PAGE ---
st.set_page_config(page_title="GeoMeta Portal & Eval", layout="wide")
st.title("🛰️ Geospatial Metadata: Generation & Evaluation")


# --- 2. EVALUATION LOGIC (Veregin's Matrix) ---
class VereginEvaluator:
    def __init__(self, generated_meta, ground_truth):
        self.gen = generated_meta
        self.gt = ground_truth
        self.criteria = ["Correctness", "Completeness", "Consistency", "Granularity"]

    def score_field(self, field_name, gen_val, gt_val):
        # scoring logic: 0 (missing), 1 (partial), 2 (full)
        scores = {c: 0 for c in self.criteria}

        # Completeness
        if gen_val and gen_val != "Unknown": scores["Completeness"] = 2

        # Correctness
        if str(gen_val).lower() == str(gt_val).lower():
            scores["Correctness"] = 2
        elif gen_val and str(gt_val).lower() in str(gen_val).lower():
            scores["Correctness"] = 1

        # Consistency & Granularity (Simplified logic for demo)
        scores["Consistency"] = 2 if scores["Correctness"] > 0 else 0
        scores["Granularity"] = 2 if "Multi" in str(gen_val) else 1

        return scores


# --- 3. METADATA INFERENCE METHODS (Your Original Logic) ---
def get_rule_based_metadata(df):
    return {
        "geometry_type": df['WKT_LNG_LAT'].str.extract(r'^([A-Z]+)', expand=False).unique().tolist()[
            0] if 'WKT_LNG_LAT' in df.columns else "Unknown",
        "total_features": len(df),
        "attributes": list(df.columns)
    }


# --- 4. STREAMLIT INTERFACE ---
tab1, tab2 = st.tabs(["🚀 Metadata Generator", "📊 Evaluation Matrix"])

with tab1:
    uploaded_file = st.file_uploader("Upload CSV", type=['csv'])
    if uploaded_file:
        df = pd.read_csv(uploaded_file, sep=';')
        st.write("### Data Preview", df.head(3))

        # Inference
        metadata = get_rule_based_metadata(df)
        st.json(metadata)
        st.session_state['last_meta'] = metadata

with tab2:
    st.header("Method Comparison (Veregin Matrix)")

    # Proxy Ground Truth (Input from Amsterdam Portal)
    st.info("Enter Proxy Ground Truth from Amsterdam Data Portal below:")
    col_a, col_b = st.columns(2)
    gt_type = col_a.selectbox("Reference Geometry", ["POLYGON", "POINT", "LINESTRING"])
    gt_count = col_b.number_input("Reference Feature Count", value=100)

    if 'last_meta' in st.session_state:
        evaluator = VereginEvaluator(st.session_state['last_meta'],
                                     {"geometry_type": gt_type, "total_features": gt_count})

        # Calculate Scores
        geo_scores = evaluator.score_field("geometry", st.session_state['last_meta']['geometry_type'], gt_type)

        # Radar Chart for Visualization
        categories = list(geo_scores.keys())
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=list(geo_scores.values()),
            theta=categories,
            fill='toself',
            name='Rule-Based Method'
        ))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 2])), showlegend=True)

        st.plotly_chart(fig)

        # Detailed Matrix Table
        st.table(pd.DataFrame([geo_scores], index=["Geometry Type"]))