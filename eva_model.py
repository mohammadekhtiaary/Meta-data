import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json

# --- 1. ISO 19115-1 GROUND TRUTH DEFINITION ---
# Mapping standard ISO elements to our data fields
ISO_REQUIREMENTS = {
    "MD_SpatialRepresentationType": "vector",  # ISO CodeList
    "EX_GeographicBoundingBox": "Required",  # Mandatory
    "MD_CharacterSet": "utf8",  # Mandatory
    "DQ_DataQuality": "Level 1",  # Quality info
    "MD_FeatureCatalogueDescription": "Required"
}


# --- 2. VEREGIN EVALUATION ENGINE ---
class ISOVereginEvaluator:
    def __init__(self, inferred_data, ground_truth):
        self.inferred = inferred_data
        self.gt = ground_truth
        self.criteria = ["Correctness", "Completeness", "Consistency", "Granularity"]

    def score_field(self, field_name, gen_val, gt_val):
        scores = {c: 0 for c in self.criteria}

        # 1. Completeness: Is the ISO mandatory element present?
        if gen_val and gen_val != "Unknown":
            scores["Completeness"] = 2

        # 2. Correctness: Does it match ISO CodeLists or values?
        if str(gen_val).lower() == str(gt_val).lower():
            scores["Correctness"] = 2
        elif gen_val and str(gt_val).lower() in str(gen_val).lower():
            scores["Correctness"] = 1

        # 3. Consistency: Is it logically sound within ISO schema?
        # e.g., If type is 'vector', we expect geometry.
        scores["Consistency"] = 2 if (scores["Correctness"] > 0) else 0

        # 4. Granularity: Does it meet ISO level of detail?
        if "Multi" in str(gen_val):
            scores["Granularity"] = 2