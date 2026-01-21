import streamlit as st
import pandas as pd
import requests
import zipfile
import io
import re


# --- 1. VEREGIN SCORING ENGINE ---
def score_veregin(inferred, reference):
    scores = {"Correctness": 0, "Completeness": 0, "Consistency": 0, "Granularity": 0}
    if str(inferred).lower() == str(reference).lower():
        scores["Correctness"] = 2
    elif str(inferred) in str(reference) or str(reference) in str(inferred):
        scores["Correctness"] = 1
    scores["Completeness"] = 2 if (inferred and str(inferred).lower() != "unknown") else 0
    scores["Consistency"] = 2 if len(str(inferred)) > 0 else 0
    scores["Granularity"] = 2 if str(inferred).upper() == str(reference).upper() else 1
    scores["Total"] = sum(scores.values())
    return scores


# --- 2. TEXT-BASED MIF PARSER (No GeoPandas needed!) ---
def parse_mif_header(mif_text):
    """Parses a .mif file as text to extract metadata."""
    meta = {}
    # Look for Geometry Type (usually near 'Data' section or by looking at objects)
    if "Point" in mif_text:
        meta["geometry_type"] = "POINT"
    elif "Region" in mif_text:
        meta["geometry_type"] = "POLYGON"
    elif "Line" in mif_text:
        meta["geometry_type"] = "LINESTRING"

    # Look for Column Count
    col_match = re.search(r"Columns\s+(\d+)", mif_text, re.IGNORECASE)
    meta["attribute_count"] = int(col_match.group(1)) if col_match else "Unknown"

    return meta


# --- 3. UI & DOWNLOAD LOGIC ---
st.title("🛰️ Automated URL Metadata Evaluator")

# Example URL from Amsterdam Data Portal (typically they provide ZIPs)
url = st.text_input("Paste Amsterdam Data Portal ZIP Link:",
                    "https://maps.amsterdam.nl/open_geodata/geojson.php?KAARTLAAG=PARKEREN_GEMEENTE&GEMEENTE=Amsterdam")

if st.button("Download and Evaluate"):
    try:
        response = requests.get(url)
        z = zipfile.ZipFile(io.BytesIO(response.content))

        # Find the .mif file in the zip
        mif_filename = [f for f in z.namelist() if f.endswith('.mif')][0]
        with z.open(mif_filename) as f:
            mif_content = f.read().decode('utf-8')
            ground_truth = parse_mif_header(mif_content)

        st.success(f"Reference data extracted from {mif_filename}")
        st.write("**Reference Metadata Found:**", ground_truth)

        # Now you can compare this 'ground_truth' to your automated metadata!
        # (Insert your run_rule_based() and scoring loop here)

    except Exception as e:
        st.error(f"Could not process URL. Make sure it is a direct link to a ZIP file. Error: {e}")