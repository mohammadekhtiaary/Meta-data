import streamlit as st
import pandas as pd
import json


# --- 1. CORE LOGIC CLASSES ---

class MetadataEvaluator:
    """Evaluates metadata based on ISO 19115 / Veregin Matrix principles."""

    def __init__(self, generated, reference):
        self.gen = generated
        self.ref = reference

    def calculate_score(self, gen_val, ref_val):
        # Completeness: Is it there?
        comp = 2 if gen_val is not None and gen_val != "Unknown" else 0
        # Correctness: Does it match the Portal?
        corr = 2 if gen_val == ref_val else 1 if str(gen_val) in str(ref_val) else 0
        # Consistency: Logical internal structure
        cons = 2 if comp > 0 else 0
        # Granularity: Detail level (e.g. MultiPolygon vs Polygon)
        gran = 2 if len(str(gen_val)) >= len(str(ref_val)) else 1

        return comp + corr + cons + gran

    def get_report(self):
        fields = {
            "Spatial Type": (self.gen.get("geometry_info", {}).get("type"), self.ref.get("geometry_type")),
            "Feature Count": (self.gen.get("total_features"), self.ref.get("total_features")),
            "Extent (X)": (self.gen.get("geographic_extent", {}).get("min_x"), self.ref.get("bbox_min_x"))
        }
        scores = {k: self.calculate_score(v[0], v[1]) for k, v in fields.items()}
        scores["Final Score"] = sum(scores.values()) / len(fields)
        return scores


# --- 2. STREAMLIT UI ---

st.set_page_config(page_title="Batch GeoMeta Evaluator", layout="wide")
st.title("🛰️ Batch ISO 19115 Metadata Evaluator")
st.markdown("Upload multiple CSVs from the Amsterdam Data Portal to evaluate inference methods.")

# Sidebar Configuration
st.sidebar.header("Evaluation Settings")
inference_method = st.sidebar.selectbox("Inference Method", ["Rule-Based", "Statistical", "Heuristic"])

# --- 3. BATCH UPLOADER ---
uploaded_files = st.file_uploader("Choose CSV files", type=['csv'], accept_multiple_files=True)

if uploaded_files:
    all_results = []

    for uploaded_file in uploaded_files:
        # Load Data
        df = pd.read_csv(uploaded_file, sep=';')
        file_name = uploaded_file.name

        # --- GENERATION LOGIC (Simplified for Batch) ---
        # Note: Replace this with your specific rule-based/stat/heuristic functions
        metadata = {
            "geometry_info": {"type": ["POINT"]},
            "total_features": len(df),
            "geographic_extent": {"min_x": df['LNG'].min() if 'LNG' in df.columns else None}
        }

        # --- PROXY GROUND TRUTH (Reference) ---
        # Logic: In a real test, you'd match file_name to a known portal schema
        reference_truth = {
            "geometry_type": ["POINT"],
            "total_features": len(df),
            "bbox_min_x": 4.90
        }

        # --- EVALUATION ---
        evaluator = MetadataEvaluator(metadata, reference_truth)
        report = evaluator.get_report()
        report["Filename"] = file_name
        all_results.append(report)

    # --- 4. DISPLAY SUMMARY ---
    results_df = pd.DataFrame(all_results).set_index("Filename")

    st.subheader(f"Evaluation Summary: {inference_method}")
    st.dataframe(results_df.style.highlight_max(axis=0, color='lightgreen'))

    # Visualizing Method Performance
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Performance per Dataset (Veregin Score)**")
        st.bar_chart(results_df["Final Score"])

    with col2:
        avg_total = results_df["Final Score"].mean()
        st.metric("Batch Average Score", f"{avg_total:.2f} / 8.0")
        st.info("High scores indicate metadata consistency with ISO 19115 standards.")

    # Export Report
    csv = results_df.to_csv().encode('utf-8')
    st.download_button("Download Full Evaluation Report", data=csv, file_name="metadata_eval_report.csv")

else:
    st.info("Please upload one or more CSV files to begin the batch evaluation.")