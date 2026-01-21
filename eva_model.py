import pandas as pd
import numpy as np


class VereginEvaluator:
    def __init__(self, generated_meta, ground_truth_meta):
        self.gen = generated_meta
        self.gt = ground_truth_meta
        self.criteria = ["correctness", "completeness", "consistency", "granularity"]

    def evaluate_field(self, field_name, gen_val, gt_val):
        """
        Applies Veregin's logic to a single field.
        Returns a dictionary of scores (0-2) for the 4 criteria.
        """
        scores = {c: 0 for c in self.criteria}

        # 1. Completeness: Was it detected?
        if gen_val is not None and gen_val != "Unknown" and gen_val != {}:
            scores["completeness"] = 2

        # 2. Correctness: Does it match ground truth?
        if str(gen_val).lower() == str(gt_val).lower():
            scores["correctness"] = 2
        elif gen_val and any(x in str(gen_val).lower() for x in str(gt_val).lower().split()):
            scores["correctness"] = 1  # Partial match

        # 3. Consistency: Logic check (e.g., Geometry type vs Dimensionality)
        # Rule: If Geometry is Point/Polygon and Dim is 2D, it's consistent.
        if field_name == "geometry_type":
            dim = self.gen.get("geometry_info", {}).get("dimensionality", "")
            if "2D" in dim and gen_val in ["POINT", "POLYGON", "LINESTRING"]:
                scores["consistency"] = 2
        else:
            scores["consistency"] = 2  # Default if no logical conflict

        # 4. Granularity: Precision level
        # Example: Detecting 'MultiPolygon' vs just 'Polygon'
        if field_name == "geometry_type":
            if "MULTI" in str(gen_val).upper():
                scores["granularity"] = 2
            else:
                scores["granularity"] = 1  # Coarse detection
        else:
            scores["granularity"] = 2

        return scores

    def get_report(self):
        """Calculates the total Veregin Score for the method."""
        # Define fields to evaluate based on your code structure
        fields_to_compare = {
            "geometry_type": (self.gen.get("geometry_info", {}).get("type", [""])[0],
                              self.gt.get("geometry_type", [""])[0]),
            "feature_count": (self.gen.get("total_features"), self.gt.get("total_features")),
            "bbox": (self.gen.get("geographic_extent", {}).get("min_x"),
                     self.gt.get("geographic_extent", {}).get("min_x"))
        }

        report = []
        total_method_score = 0

        for field, (gen_v, gt_v) in fields_to_compare.items():
            field_scores = self.evaluate_field(field, gen_v, gt_v)
            field_total = sum(field_scores.values())
            total_method_score += field_total

            report.append({
                "Field": field,
                **field_scores,
                "Total (max 8)": field_total
            })

        return pd.DataFrame(report), total_method_score


# --- Streamlit Integration Logic ---
def display_evaluation(generated_meta, proxy_gt):
    evaluator = VereginEvaluator(generated_meta, proxy_gt)
    df_report, final_score = evaluator.get_report()

    st.header("📊 Veregin Matrix Evaluation")
    st.table(df_report)

    max_possible = len(df_report) * 8
    st.metric("Total Method Performance", f"{final_score} / {max_possible}",
              delta=f"{round((final_score / max_possible) * 100)}%")