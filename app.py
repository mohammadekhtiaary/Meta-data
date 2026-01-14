import streamlit as st
import pandas as pd
import json

# --- 1. SET UP THE PAGE ---
st.set_page_config(page_title="GeoMeta Portal", layout="wide")
st.title("🛰️ Automated Geospatial Metadata Generator")
st.markdown("Upload your geospatial CSV or Row Data to generate syntactic metadata automatically.")

# --- 2. FILE UPLOADER WIDGET ---
uploaded_file = st.file_uploader("Choose a CSV file", type=['csv'])

if uploaded_file is not None:
    # Read the data (detecting your specific semicolon delimiter)
    df = pd.read_csv(uploaded_file, sep=';')

    # Show a preview of the data
    st.subheader("Data Preview")
    st.dataframe(df.head(5))

    # --- 3. YOUR METADATA LOGIC ---
    # (Simplified version of your previously created code)
    metadata = {
        "format": "CSV (Delimited)",
        "row_count": len(df),
        "geometry_types": df['WKT_LNG_LAT'].str.extract(r'^([A-Z]+)',
                                                        expand=False).unique().tolist() if 'WKT_LNG_LAT' in df.columns else [
            "Unknown"],
        "geographic_extent": {
            "min_x": df['LNG'].min() if 'LNG' in df.columns else None,
            "max_x": df['LNG'].max() if 'LNG' in df.columns else None,
            "min_y": df['LAT'].min() if 'LAT' in df.columns else None,
            "max_y": df['LAT'].max() if 'LAT' in df.columns else None,
        },
        "attributes": {col: str(df[col].dtype) for col in df.columns}
    }

    # --- 4. DISPLAY RESULTS ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Generated Metadata (JSON)")
        st.json(metadata)

    with col2:
        st.subheader("Quick Stats")
        st.write(f"**Total Features:** {len(df)}")
        st.write(f"**Coordinate System:** EPSG:4326 (Inferred)")

        # Download Button for the Metadata
        json_string = json.dumps(metadata, indent=4)
        st.download_button(
            label="Download Metadata as JSON",
            file_name="metadata.json",
            mime="application/json",
            data=json_string,
        )
