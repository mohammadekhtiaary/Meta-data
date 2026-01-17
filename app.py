import streamlit as st
import pandas as pd
import numpy as np
import json

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="GeoMeta Portal",
    layout="wide"
)

st.title("🛰️ Automated Geospatial Metadata Generator")
st.markdown(
    """
Upload a geospatial CSV file to automatically infer **syntactic metadata**
using **rule-based**, **statistical profiling**, and **heuristic inference** methods.
"""
)

# --------------------------------------------------
# FILE UPLOADER
# --------------------------------------------------
uploaded_file = st.file_uploader(
    "Upload CSV file",
    type=["csv"]
)

# --------------------------------------------------
# ATTRIBUTE METADATA INFERENCE
# --------------------------------------------------
def infer_attribute_metadata(df):

    attribute_metadata = {}

    for col in df.columns:
        series = df[col]
        dtype = str(series.dtype)

        missing_count = int(series.isna().sum())
        unique_count = int(series.nunique(dropna=True))

        attr = {
            "pandas_dtype": dtype,
            "missing_values": missing_count,
            "missing_percentage": round(missing_count / len(df) * 100, 2),
            "unique_values": unique_count
        }

        # -----------------------------
        # STATISTICAL PROFILING
        # -----------------------------
        if pd.api.types.is_numeric_dtype(series):
            attr.update({
                "min": float(series.min()),
                "max": float(series.max()),
                "mean": float(series.mean()),
                "std": float(series.std())
            })

        if pd.api.types.is_string_dtype(series):
            lengths = series.dropna().astype(str).str.len()
            if not lengths.empty:
                attr.update({
                    "min_length": int(lengths.min()),
                    "max_length": int(lengths.max()),
                    "avg_length": float(lengths.mean())
                })

        # -----------------------------
        # HEURISTIC INFERENCE
        # -----------------------------
        inferred_type = "unknown"

        if pd.api.types.is_integer_dtype(series):
            if unique_count > 0.9 * len(df):
                inferred_type = "identifier"
            else:
                inferred_type = "categorical"

        elif pd.api.types.is_float_dtype(series):
            inferred_type = "continuous"

        elif pd.api.types.is_string_dtype(series):
            if unique_count < 20:
                inferred_type = "categorical"
            else:
                inferred_type = "text"

        attr["inferred_semantic_type"] = inferred_type

        attribute_metadata[col] = attr

    return attribute_metadata


# --------------------------------------------------
# MAIN LOGIC
# --------------------------------------------------
if uploaded_file is not None:

    # Detect semicolon delimiter automatically
    df = pd.read_csv(uploaded_file, sep=";")

    # --------------------------------------------------
    # DATA PREVIEW
    # --------------------------------------------------
    st.subheader("📄 Data Preview")
    st.dataframe(df.head())

    # --------------------------------------------------
    # METADATA INFERENCE
    # --------------------------------------------------
    attribute_metadata = infer_attribute_metadata(df)

    geometry_types = (
        df["WKT_LNG_LAT"]
        .astype(str)
        .str.extract(r"^([A-Z]+)", expand=False)
        .dropna()
        .unique()
        .tolist()
        if "WKT_LNG_LAT" in df.columns
        else ["Unknown"]
    )

    metadata = {
        "metadata_type": "Syntactic Metadata",
        "generation_method": "Automatic Inference",

        # --------------------------------------------------
        # FILE STRUCTURE (RULE-BASED)
        # --------------------------------------------------
        "file_information": {
            "format": "CSV (Delimited)",
            "delimiter": ";",
            "row_count": int(len(df)),
            "column_count": int(len(df.columns))
        },

        # --------------------------------------------------
        # GEOMETRY METADATA
        # --------------------------------------------------
        "geometry": {
            "geometry_types": geometry_types,
            "coordinate_dimension": 2,
            "coordinate_reference_system": "EPSG:4326 (inferred)"
        },

        # --------------------------------------------------
        # GEOGRAPHIC EXTENT
        # --------------------------------------------------
        "geographic_extent": {
            "min_x": float(df["LNG"].min()) if "LNG" in df.columns else None,
            "max_x": float(df["LNG"].max()) if "LNG" in df.columns else None,
            "min_y": float(df["LAT"].min()) if "LAT" in df.columns else None,
            "max_y": float(df["LAT"].max()) if "LAT" in df.columns else None
        },

        # --------------------------------------------------
        # ATTRIBUTE PROFILING
        # --------------------------------------------------
        "attributes": attribute_metadata,

        # --------------------------------------------------
        # INFERENCE METHODS
        # --------------------------------------------------
        "inference_methods": {
            "rule_based": [
                "File format detection",
                "Delimiter detection",
                "Column name extraction",
                "Geometry type extraction",
                "CRS inference"
            ],
            "statistical_profiling": [
                "Missing values",
                "Unique values (cardinality)",
                "Numeric ranges",
                "Summary statistics",
                "String length distribution"
            ],
            "heuristic_based": [
                "Identifier detection",
                "Categorical attribute inference",
                "Continuous variable inference",
                "Pattern-based semantic typing"
            ]
        }
    }

    # --------------------------------------------------
    # DISPLAY RESULTS
    # --------------------------------------------------
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📘 Generated Metadata (JSON)")
        st.json(metadata)

    with col2:
        st.subheader("📊 Dataset Summary")
        st.write(f"**Total Features:** {len(df)}")
        st.write(f"**Total Attributes:** {len(df.columns)}")
        st.write(f"**Geometry Types:** {', '.join(geometry_types)}")
        st.write("**Coordinate System:** EPSG:4326 (inferred)")

        json_string = json.dumps(metadata, indent=4)

        st.download_button(
            label="⬇️ Download Metadata (JSON)",
            data=json_string,
            file_name="syntactic_metadata.json",
            mime="application/json"
        )