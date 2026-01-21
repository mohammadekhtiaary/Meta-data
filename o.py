import streamlit as st
import pandas as pd
import geopandas as gpd
import os
import tempfile


# --- 1. VEREGIN SCORING ENGINE ---
def score_veregin(inferred, reference):
    scores = {"Correctness": 0, "Completeness": 0, "Consistency": 0, "Granularity": 0}

    # Correctness
    if str(inferred).lower() == str(reference).lower():
        scores["Correctness"] = 2
    elif str(inferred) in str(reference) or str(reference) in str(inferred):
        scores["Correctness"] = 1

    # Completeness
    if inferred is not None and str(inferred).strip().lower() not in ["unknown", ""]:
        scores["Completeness"] = 2

    # Consistency & Granularity (Logic based on your class requirements)
    scores["Consistency"] = 2 if (isinstance(inferred, (int, float)) or len(str(inferred)) > 0) else 0
    scores["Granularity"] = 2 if str(inferred).upper() == str(reference).upper() else 1

    scores["Total"] = sum(scores.values())
    return scores


# --- 2. MAPINFO LOADER ---
def load_mapinfo_reference(mif_file, mid_file):
    """
    Saves uploaded MIF/MID to a temp directory so GeoPandas/GDAL can read them.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # MIF and MID must have the same base name in the same folder
        base_name = "reference"
        mif_path = os.path.join(tmpdir, f"{base_name}.mif")
        mid_path = os.path.join(tmpdir, f"{base_name}.mid")

        with open(mif_path, "wb") as f:
            f.write(mif_file.getbuffer())
        with open(mid_path, "wb") as f:
            f.write(mid_file.getbuffer())

        # Read using GeoPandas
        gdf = gpd.read_file(mif_path)

        # Extract Reference Metadata for Comparison
        ref_meta = {
            "geometry_type": str(gdf.geom_type.iloc[0]).upper(),
            "attribute_count": len(gdf.columns) - 1,  # Exclude 'geometry' column
            "total_features": len(gdf),
            "coord_system": str(gdf.crs) if gdf.crs else "Unknown"
        }
        return ref_meta


# --- 3. UI & EVALUATION ---
st.title("🛰️ MapInfo MIF/MID Evaluator")

st.sidebar.header("Upload Files")
data_csv = st.sidebar.file_uploader("Upload Target Dataset (CSV)", type=['csv'])

st.sidebar.subheader("Reference Files (MapInfo)")
ref_mif = st.sidebar.file_uploader("Upload Reference .mif", type=['mif'])
ref_mid = st.sidebar.file_uploader("Upload Reference .mid", type=['mid'])

if data_csv and ref_mif and ref_mid:
    # 1. Process Reference
    ground_truth = load_mapinfo_reference(ref_mif, ref_mid)

    # 2. Process Target CSV
    df = pd.read_csv(data_csv, sep=None, engine='python')

    # 3. Define Inference Methods
    methods = {
        "Rule-Based": {
            "geometry_type": "POINT" if "WKT" in df.columns else "Unknown",
            "attribute_count": len(df.columns)
        },
        "Statistical": {
            "geometry_type": "POINT" if any(c in df.columns for c in ['LAT', 'LON']) else "Unknown",
            "attribute_count": df.shape[1]
        }
    }

    # 4. Evaluation Loop
    results = []
    for m_name, m_data in methods.items():
        for field in ["geometry_type", "attribute_count"]:
            inf = m_data.get(field)
            ref = ground_truth.get(field)

            v_score = score_veregin(inf, ref)
            v_score.update({"Method": m_name, "Field": field, "Inferred": inf, "Reference": ref})
            results.append(v_score)

    # 5. Display
    eval_df = pd.DataFrame(results)
    st.write("### Veregin Matrix Scoring", eval_df)

    # Method Performance summary
    summary = eval_df.groupby("Method")["Total"].sum().reset_index()
    st.bar_chart(summary.set_index("Method"))