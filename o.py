import streamlit as st
import pandas as pd
import json


# --- 1. VEREGIN SCORING ENGINE (The Core Logic) ---
def score_veregin(inferred, reference):
    """
    Scores a metadata field based on 4 criteria (Max 8 points).
    0: Incorrect/Missing, 1: Partially Correct, 2: Fully Correct
    """
    scores = {"Correctness": 0, "Completeness": 0, "Consistency": 0, "Granularity": 0}

    # 1. Correctness: Does it match?
    if str(inferred).lower() == str(reference).lower():
        scores["Correctness"] = 2
    elif str(inferred) in str(reference) or str(reference) in str(inferred):
        scores["Correctness"] = 1

    # 2. Completeness: Was it detected?
    if inferred is not None and str(inferred).strip().lower() not in ["unknown", ""]:
        scores["Completeness"] = 2

    # 3. Consistency: Logical formatting
    # Is the geometry type a valid standard string? Is the count a number?
    if isinstance(inferred, (int, float)) or (isinstance(inferred, str) and len(inferred) > 0):
        scores["Consistency"] = 2
    else:
        scores["Consistency"] = 0

    # 4. Granularity: Specificity check
    # Reference: Point -> Inferred: Point (Score 2). Inferred: Geometry (Score 1)
    if str(inferred).upper() == str(reference).upper():
        scores["Granularity"] = 2
    elif "GEOMETRY" in str(inferred).upper() or "Unknown" not in str(inferred):
        scores["Granularity"] = 1

    scores["Total"] = sum(scores.values())
    return scores


# --- 2. THE UI & FILE HANDLERS ---
st.title("🛰️ Metadata Evaluator: Upload vs. Reference")

col1, col2 = st.columns(2)

with col1:
    data_file = st.file_uploader("1. Upload Dataset (CSV)", type=['csv'])
with col2:
    meta_ref_file = st.file_uploader("2. Upload Reference Metadata (JSON)", type=['json'])

if data_file and meta_ref_file:
    # Load Data
    df = pd.read_csv(data_file, sep=None, engine='python')

    # Load Reference (The 'Ground Truth' file)
    # Expected JSON format: {"geometry_type": "POINT", "attribute_count": 10, ...}
    ground_truth = json.load(meta_ref_file)

    st.success("Files loaded. Comparing metadata...")

    # --- 3. RUN YOUR INFERENCE METHODS ---
    # (Using your previous functions: run_rule_based, etc.)
    methods = {
        "Rule-Based": {"geometry_type": "POINT", "attribute_count": len(df.columns)},
        "Statistical": {"geometry_type": "POINT", "attribute_count": df.shape[1]},
        "Heuristic": {"geometry_type": "GEOMETRY", "attribute_count": len(df.columns)}
    }

    # --- 4. THE COMPARISON LOOP ---
    eval_results = []

    for method_name, inferred_dict in methods.items():
        for field in ground_truth.keys():
            if field in inferred_dict:
                inf_val = inferred_dict[field]
                ref_val = ground_truth[field]

                # Apply Veregin Scoring
                scores = score_veregin(inf_val, ref_val)
                scores.update({
                    "Method": method_name,
                    "Field": field,
                    "Inferred": inf_val,
                    "Reference": ref_val
                })
                eval_results.append(scores)

    # --- 5. DISPLAY VEREGIN MATRIX ---
    eval_df = pd.DataFrame(eval_results)

    st.subheader("Veregin Matrix Comparison Table")
    st.dataframe(eval_df)

    # Aggregate Method-Level Scores
    st.subheader("Final Leaderboard (Method Performance)")
    leaderboard = eval_df.groupby("Method")["Total"].sum().reset_index()
    # Max possible score = Fields * 8 points
    max_score = len(ground_truth.keys()) * 8
    leaderboard["Accuracy %"] = (leaderboard["Total"] / max_score) * 100
    st.table(leaderboard.sort_values(by="Total", ascending=False))