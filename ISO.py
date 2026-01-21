import streamlit as st
import pandas as pd
import json
import re

# =========================================================
# 1. PAGE CONFIG
# =========================================================
st.set_page_config(page_title="ISO 19115 Metadata Evaluation (MID/MIF)", layout="wide")
st.title("🛰️ ISO 19115 Metadata Evaluation using MID/MIF Proxy Ground Truth")

# =========================================================
# 2. SIDEBAR
# =========================================================
st.sidebar.header("Inference Method")
inference_method = st.sidebar.selectbox(
    "Select Metadata Inference Method",
    ["Rule-Based (Schema)", "Statistical Profiling", "Heuristic-Based"]
)

st.sidebar.header("Reference Files (MID/MIF)")
mif_file = st.sidebar.file_uploader("Upload .MIF file", type=["mif"])
mid_file = st.sidebar.file_uploader("Upload .MID file", type=["mid"])

# =========================================================
# 3. METADATA INFERENCE METHODS
# =========================================================
def get_rule_based_metadata(df):
    return {
        "method": "Rule-Based",
        "geometry_info": {
            "type": df["WKT_LNG_LAT"].str.extract(r'^([A-Z]+)', expand=False).dropna().unique().tolist()
            if "WKT_LNG_LAT" in df.columns else None,
            "dimensionality": "2D"
        },
        "attributes": {c: str(df[c].dtype) for c in df.columns},
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
    return {
        "method": "Statistical Profiling",
        "attribute_stats": stats,
        "total_features": len(df)
    }


def get_heuristic_metadata(df):
    roles = {}
    for col in df.columns:
        unique_ratio = df[col].nunique() / len(df)
        if pd.api.types.is_integer_dtype(df[col]) and unique_ratio > 0.9:
            roles[col] = "Identifier"
        elif df[col].nunique() < 10:
            roles[col] = "Categorical"
        elif pd.api.types.is_float_dtype(df[col]):
            roles[col] = "Continuous"
        else:
            roles[col] = "General"
    return {
        "method": "Heuristic-Based",
        "classifications": roles,
        "total_features": len(df)
    }

# =========================================================
# 4. MID / MIF PARSING (REFERENCE METADATA)
# =========================================================
def parse_mif(mif_text):
    geometry_type = None
    bounds = None

    for line in mif_text.splitlines():
        line = line.strip()

        if line.startswith(("Point", "Line", "Pline", "Region")):
            geometry_type = line.split()[0]

        if line.startswith("Bounds"):
            nums = re.findall(r"[-+]?\d*\.\d+|\d+", line)
            if len(nums) == 4:
                bounds = {
                    "min_x": float(nums[0]),
                    "min_y": float(nums[1]),
                    "max_x": float(nums[2]),
                    "max_y": float(nums[3])
                }

    return {
        "geometry_type": geometry_type,
        "bounding_box": bounds,
        "dimensionality": "2D"
    }


def parse_mid(mid_text):
    rows = mid_text.splitlines()
    rows = [r for r in rows if r.strip() != ""]
    return {
        "total_features": len(rows)
    }

# =========================================================
# 5. VEREGIN SCORING FUNCTIONS
# =========================================================
def score_correctness(inferred, reference):
    if inferred is None:
        return 0
    if inferred == reference:
        return 2
    if isinstance(inferred, list) and reference in inferred:
        return 2
    return 1


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
# 6. ISO 19115-INSPIRED EVALUATION
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
# 7. MAIN INTERFACE
# =========================================================
csv_file = st.file_uploader("Upload Dataset (CSV)", type=["csv"])

if csv_file and mif_file and mid_file:
    df = pd.read_csv(csv_file, sep=";")

    st.subheader("Dataset Preview")
    st.dataframe(df.head())

    # -----------------------
    # Inferred metadata
    # -----------------------
    if inference_method == "Rule-Based (Schema)":
        metadata = get_rule_based_metadata(df)
    elif inference_method == "Statistical Profiling":
        metadata = get_statistical_metadata(df)
    else:
        metadata = get_heuristic_metadata(df)

    metadata["geographic_extent"] = {
        "min_x": float(df["LNG"].min()) if "LNG" in df.columns else None,
        "max_x": float(df["LNG"].max()) if "LNG" in df.columns else None,
        "min_y": float(df["LAT"].min()) if "LAT" in df.columns else None,
        "max_y": float(df["LAT"].max()) if "LAT" in df.columns else None
    }

    # -----------------------
    # Reference metadata
    # -----------------------
    mif_text = mif_file.read().decode("utf-8", errors="ignore")
    mid_text = mid_file.read().decode("utf-8", errors="ignore")

    ref_mif = parse_mif(mif_text)
    ref_mid = parse_mid(mid_text)

    reference_metadata = {
        "geometry_type": ref_mif["geometry_type"],
        "bounding_box": ref_mif["bounding_box"],
        "total_features": ref_mid["total_features"],
        "attribute_count": len(df.columns)
    }

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Inferred Metadata")
        st.json(metadata)

    with col2:
        st.subheader("Reference Metadata (MID/MIF)")
        st.json(reference_metadata)

    # -----------------------
    # Evaluation
    # -----------------------
    field_scores = evaluate_metadata_iso(metadata, reference_metadata)
    method_score = aggregate_scores(field_scores)

    st.subheader("ISO 19115 Evaluation (Veregin Matrix)")
    st.json(field_scores)

    st.metric(
        "Overall Method Performance",
        method_score["normalized_score"]
    )

    st.write(f"Raw Score: {method_score['total_score']} / {method_score['max_score']}")

    # -----------------------
    # Download results
    # -----------------------
    st.download_button(
        "Download Evaluation Results",
        json.dumps(
            {"fields": field_scores, "method": method_score},
            indent=2
        ),
        file_name="iso19115_mid_mif_evaluation.json",
        mime="application/json"
    )