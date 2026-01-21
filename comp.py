import streamlit as st
import pandas as pd
import numpy as np
import json

# --- 1. METADATA INFERENCE ENGINE ---
# These represent your 3 methods (Rule-Based, Statistical, Heuristic)

def infer_metadata(df, method):
    meta = {}
    if method == "Rule-Based":
        meta['geom'] = "POINT" if "LNG" in df.columns else "UNKNOWN"
        meta['count'] = len(df)
        meta['bbox'] = df['LNG'].min() if 'LNG' in df.columns else 0
    elif method == "Statistical":
        # Simulate a slight error in statistical profiling for testing
        meta['geom'] = "POINT"
        meta['count'] = int(df.shape[0])
        meta['bbox'] = round(df['LNG'].mean(), 2)
    else:  # Heuristic
        meta['geom'] = "VECTOR"
        meta['count'] = len(df.index)
        meta['bbox'] = df['LNG'].quantile(0.1)
    return meta


# --- 2. EVALUATION LOGIC (Veregin's Matrix) ---

def calculate_veregin_score(inferred, actual):
    """
    Scores each field: Correctness(2), Completeness(2), Consistency(2), Granularity(2)
    Total max score = 8 per field.
    """
    # 1. Completeness (Is value present?)
    comp = 2 if inferred is not None else 0

    # 2. Correctness (Does it match ground truth?)
    # We use a tolerance for numeric values (BBox)
    if isinstance(inferred, (int, float)):
        corr = 2 if abs(inferred - actual) < 0.01 else 1 if abs(inferred - actual) < 0.5 else 0
    else:
        corr = 2 if str(inferred) == str(actual) else 0

    # 3. Consistency (Logic check)
    cons = 2 if comp == 2 and corr >= 1 else 0

    # 4. Granularity (Detail level)
    gran = 2 if len(str(inferred)) >= len(str(actual)) else 1

    return comp + corr + cons + gran


# --- 3. STREAMLIT UI ---

st.set_page_config(page_title="ISO 19115 Evaluator Pro", layout="wide")
st.title("🛰️ ISO 19115 Quality Metric Tool")

st.sidebar.header("Evaluation Parameters")
selected_method = st.sidebar.selectbox("Select Inference Method", ["Rule-Based", "Statistical", "Heuristic"])

uploaded_files = st.file_uploader("Upload Multiple Amsterdam Data Portal CSVs", type=['csv'],
                                  accept_multiple_files=True)

if uploaded_files:
    summary_data = []

    for file in uploaded_files:
        # Load the dataset
        df = pd.read_csv(file, sep=';')

        # A. DERIVE PROXY GROUND TRUTH (The "Real" values from the file)
        # In ISO 19115, these are the 'True' descriptors
        truth = {
            'geom': "POINT",  # Assuming portal says POINT
            'count': len(df),
            'bbox': df['LNG'].min() if 'LNG' in df.columns else 0
        }

        # B. RUN SELECTED INFERENCE METHOD
        inferred = infer_metadata(df, selected_method)

        # C. SCORE EACH FIELD
        geom_score = calculate_veregin_score(inferred['geom'], truth['geom'])
        count_score = calculate_veregin_score(inferred['count'], truth['count'])
        bbox_score = calculate_veregin_score(inferred['bbox'], truth['bbox'])

        # Calculate ISO 19115 Average
        avg_score = (geom_score + count_score + bbox_score) / 3

        summary_data.append({
            "Filename": file.name,
            "Geometry Score": geom_score,
            "Feature Count Score": count_score,
            "BBox Score": bbox_score,
            "ISO 19115 Weighted Total": round(avg_score, 2)
        })

    # --- 4. DATA PRESENTATION ---
    results_df = pd.DataFrame(summary_data)

    # Metrics Row
    c1, c2, c3 = st.columns(3)
    c1.metric("Avg Quality Score", f"{results_df['ISO 19115 Weighted Total'].mean():.2f} / 8")
    c2.metric("Files Processed", len(uploaded_files))
    c3.metric("Method Reliability", "High" if results_df['ISO 19115 Weighted Total'].mean() > 6 else "Low")

    st.subheader("Detailed Evaluation Table")
    st.dataframe(results_df, use_container_width=True)

    # Visualization of performance across datasets
    st.subheader("Performance Variance per Dataset")
    st.line_chart(results_df.set_index("Filename")["ISO 19115 Weighted Total"])

else:
    st.warning("Please upload files to see the evaluation.")