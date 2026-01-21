import streamlit as st
import pandas as pd
import json
import re

# =========================================================
# 1. PAGE CONFIG
# =========================================================
st.set_page_config(page_title="GeoMeta ISO 19115 Evaluation Portal", layout="wide")
st.title("🛰️ Automated Geospatial Metadata Evaluation (ISO 19115 + Veregin)")

# =========================================================
# 2. SIDEBAR
# =========================================================
st.sidebar.header("Inference Method")
inference_method = st.sidebar.selectbox(
    "Select Metadata Inference Method",
    ["Rule-Based (Schema)", "Statistical Profiling", "Heuristic-Based"]
)

st.sidebar.header("Reference Metadata")
ref_file = st.sidebar.file_uploader("Upload Proxy Ground Truth (JSON)", type=["json"])

# =========================================================
# 3. METADATA INFERENCE METHODS
# =========================================================
def get_rule_based_metadata(df):
    return {
        "method": "Rule-Based",
        "geometry_info": {
            "type": df['WKT_LNG_LAT'].str.extract(
                r'^([A-Z]+)', expand=False
            ).dropna().unique().tolist()
            if 'WKT_LNG_LAT' in df.columns else None,
            "dimensionality": "2D"
        },
        "attributes": {col: str(df[col].dtype) for col in df.columns},
        "total_features": len(df)
    }


def get_statistical_metadata(df):
    stats = {}
    for col in df.columns:
        stats[col] = {
            "dtype": str(df[col].dtype),
            "missing": int(df[col].isnull().sum()),
            "unique": int(df[col].nunique())
        }
        if pd.api.types.is_numeric_dtype(df[col]):
            stats[col].update({
                "min": float(df[col].min()),
                "max": float(df[col].max())
            })
    return {
        "method": "Statistical Profiling",
        "attribute_stats": stats,
        "total_features": len(df)
    }


def get_heuristic_metadata(df):
    heuristics = {}
    for col in df.columns:
        unique_ratio = df[col].nunique() / len(df)
        if pd.api.types.is_integer_dtype(df[col]) and unique_ratio > 0.9:
            heuristics[col] = "Identifier"
        elif df[col].nunique() < 10:
            heuristics[col] = "Categorical"
        elif pd.api.types.is_float_dtype(df[col]):
            heuristics[col] = "Continuous"
        else:
            heuristics[col] = "General"
    return {
        "method": "Heuristic-Based",
        "classifications": heuristics,
        "total_features": len(df)
    }

# =========================================================
# 4. VEREGIN SCORING FUNCTIONS
# =========================================================
def score_correctness(inferred, reference):
    if inferred is None:
        return 0
    if inferred == reference:
        return 2
    if isinstance(inferred, list) and reference in inferred:
        return 2
    return 1 if inferred else 0


def score_completeness(inferred):
    return 2 if inferred not in [None, "", [], {}] else 0


def score_consistency(inferred, related=None):
    if inferred is None:
        return 0
    if related is None:
        return 2
    return 2 if inferred != related else 1


def score_granularity(inferred, reference):
    if inferred is None:
        return 0
    if inferred == reference:
        return 2
    return 1


def evaluate_field(inferred, reference, related=None):
    scores = {
        "correctness": score_correctness(inferred, reference),
        "completeness": score_completeness(inferred),
        "consistency": score_consistency(inferred, related),
        "granularity": score_granularity(inferred, reference)
    }
    scores["total"] = sum(scores.values())
    return scores

# =========================================================
# 5. ISO 19115-ALIGNED EVALUATION
# =========================================================
def evaluate_metadata_iso(inferred, reference):
    results = {}

    results["geometry_type"] = evaluate_field(
        inferred.get("geometry_info", {}).get("type"),
        reference.get("geometry_type"),
        related=inferred.get("geometry_info", {}).get("dimensionality")
    )

    results["bounding_box"] = evaluate_field(
        inferred.get("geographic_extent"),
        reference.get("bounding_box")
    )

    results["attribute_count"] = evaluate_field(
        len(inferred.get("attributes", {})) if "attributes" in inferred else None,
        reference.get("attribute_count")
    )

    results["total_features"] = evaluate_field(
        inferred.get("total_features"),
        reference.get("total_features")
    )

    return results


def aggregate_scores(field_scores):
    total = sum(v["total"] for v in field_scores.values())
    max_score = len(field_scores) * 8
    return {
        "total_score": total,
        "max_score": max_score,
        "normalized_score": round(total / max_score, 3)
    }

# =========================================================
# 6. MAIN INTERFACE
# =========================================================
uploaded_file = st.file_uploader("Upload Dataset (CSV)", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file, sep=";")

    st.subheader("Dataset Preview")
    st.dataframe(df.head())

    # Geographic Extent
    geo_extent = {
        "min_x": float(df["LNG"].min()) if "LNG" in df.columns else None,
        "max_x": float(df["LNG"].max()) if "LNG" in df.columns else None,
        "min_y": float(df["LAT"].min()) if "LAT" in df.columns else None,
        "max_y": float(df["LAT"].max()) if "LAT" in df.columns else None
    }

    # Inference
    if inference_method == "Rule-Based (Schema)":
        metadata = get_rule_based_metadata(df)
    elif inference_method == "Statistical Profiling":
        metadata = get_statistical_metadata(df)
    else:
        metadata = get_heuristic_metadata(df)

    metadata["geographic_extent"] = geo_extent

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Generated Metadata")
        st.json(metadata)

    # =====================================================
    # 7. EVALUATION
    # =====================================================
    if ref_file:
        reference_metadata = json.load(ref_file)

        field_scores = evaluate_metadata_iso(metadata, reference_metadata)
        method_score = aggregate_scores(field_scores)

        with col2:
            st.subheader("ISO 19115 Evaluation (Veregin Matrix)")
            st.json(field_scores)

            st.metric(
                label="Overall Method Performance",
                value=method_score["normalized_score"]
            )

            st.write("**Raw Score:**", f"{method_score['total_score']} / {method_score['max_score']}")

    # =====================================================
    # 8. DOWNLOAD RESULTS
    # =====================================================
    st.download_button(
        "Download Inferred Metadata",
        data=json.dumps(metadata, indent=2),
        file_name="inferred_metadata.json",
        mime="application/json"
    )

    if ref_file:
        st.download_button(
            "Download Evaluation Results",
            data=json.dumps(
                {"fields": field_scores, "method": method_score},
                indent=2
            ),
            file_name="iso19115_evaluation.json",
            mime="application/json"
        )