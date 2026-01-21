import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json

# --------------------------------------------------
# 1. ISO 19115-1 GROUND TRUTH DEFINITION
# --------------------------------------------------
ISO_REQUIREMENTS = {
    "MD_SpatialRepresentationType": "vector",
    "EX_GeographicBoundingBox": "Required",
    "MD_CharacterSet": "utf8",
    "DQ_DataQuality": "Level 1",
    "MD_FeatureCatalogueDescription": "Required"
}

# Example inferred metadata (generated / extracted)
INFERRED_METADATA = {
    "MD_SpatialRepresentationType": "Vector",
    "EX_GeographicBoundingBox": "Provided",
    "MD_CharacterSet": "UTF8",
    "DQ_DataQuality": "Level 1",
    "MD_FeatureCatalogueDescription": "Unknown"
}

# --------------------------------------------------
# 2. VEREGIN-BASED ISO EVALUATION ENGINE
# --------------------------------------------------
class ISOVereginEvaluator:
    def __init__(self, inferred_data: dict, ground_truth: dict):
        self.inferred = inferred_data
        self.gt = ground_truth
        self.criteria = ["Correctness", "Completeness", "Consistency", "Granularity"]

    def score_field(self, field_name, gen_val, gt_val):
        scores = {c: 0 for c in self.criteria}

        # Completeness
        if gen_val and gen_val != "Unknown":
            scores["Completeness"] = 2

        # Correctness
        if gen_val is not None and gt_val is not None:
            if str(gen_val).lower() == str(gt_val).lower():
                scores["Correctness"] = 2
            elif str(gt_val).lower() in str(gen_val).lower():
                scores["Correctness"] = 1

        # Consistency (logical validity within ISO schema)
        scores["Consistency"] = 2 if scores["Correctness"] > 0 else 0

        # Granularity (level of detail)
        if isinstance(gen_val, str) and "multi" in gen_val.lower():
            scores["Granularity"] = 2
        else:
            scores["Granularity"] = 1

        return scores

    def evaluate(self):
        results = []

        for field, gt_val in self.gt.items():
            gen_val = self.inferred.get(field, None)
            scores = self.score_field(field, gen_val, gt_val)

            results.append({
                "ISO Element": field,
                "Generated Value": gen_val,
                "Ground Truth": gt_val,
                **scores
            })

        return pd.DataFrame(results)


# --------------------------------------------------
# 3. STREAMLIT APP
# --------------------------------------------------
st.set_page_config(
    page_title="ISO 19115-1 Metadata Quality Evaluation",
    layout="wide"
)

st.title("📊 ISO 19115-1 Metadata Quality Evaluation")
st.markdown("**Veregin-based assessment of inferred geospatial metadata**")

evaluator = ISOVereginEvaluator(INFERRED_METADATA, ISO_REQUIREMENTS)
df = evaluator.evaluate()

# ---- Table ----
st.subheader("🔍 Field-level Evaluation")
st.dataframe(df, use_container_width=True)

# ---- Aggregated Scores ----
st.subheader("📈 Average Quality Scores")
avg_scores = df[["Correctness", "Completeness", "Consistency", "Granularity"]].mean()

fig = go.Figure(
    data=[
        go.Bar(
            x=avg_scores.index,
            y=avg_scores.values
        )
    ]
)

fig.update_layout(
    yaxis_title="Score (0–2)",
    xaxis_title="Quality Dimension",
    title="Average ISO Metadata Quality"
)

st.plotly_chart(fig, use_container_width=True)

# ---- Overall Score ----
st.subheader("✅ Overall Metadata Quality Score")
overall_score = avg_scores.mean()
st.metric(
    label="Overall Quality (0–2)",
    value=round(overall_score, 2)
)