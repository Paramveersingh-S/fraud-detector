import shap
import pandas as pd

def build_explainer(model):
    # tree_path_dependent avoids needing a background dataset and is fast
    # enough to run per-transaction at serve time.
    return shap.TreeExplainer(model, feature_perturbation='tree_path_dependent')

def explain_transaction(explainer, feature_cols: list[str], row: dict, top_k=5):
    row_df = pd.DataFrame([row])[feature_cols]
    sv = explainer.shap_values(row_df)
    # SHAP's return shape for LightGBM boosters varies by version
    values = sv[1][0] if isinstance(sv, list) else sv[0]
    contributions = sorted(zip(feature_cols, values), key=lambda x: abs(x[1]), reverse=True)[:top_k]
    return [{'feature': f, 'contribution': round(float(v), 4)} for f, v in contributions]
