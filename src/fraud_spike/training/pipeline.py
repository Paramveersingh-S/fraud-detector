import lightgbm as lgb
import pandas as pd
import numpy as np
import json
import joblib
import os
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    roc_auc_score, average_precision_score,
    precision_score, recall_score, f1_score
)

DROP_COLS = ['TransactionID', 'isFraud', 'TransactionDT', 'uid']

def temporal_split(df: pd.DataFrame):
    t70 = df['TransactionDT'].quantile(0.70)
    t85 = df['TransactionDT'].quantile(0.85)
    train = df[df['TransactionDT'] <= t70]
    val = df[(df['TransactionDT'] > t70) & (df['TransactionDT'] <= t85)]
    test = df[df['TransactionDT'] > t85]
    return train, val, test

def get_feature_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in DROP_COLS and not c.startswith('_')]

def train_model(df: pd.DataFrame):
    train, val, test = temporal_split(df)
    feature_cols = get_feature_cols(df)
    cat_cols = [c for c in feature_cols if str(train[c].dtype) == 'category']

    X_train, y_train = train[feature_cols], train['isFraud']
    X_val, y_val = val[feature_cols], val['isFraud']

    scale_pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    params = {
        'objective': 'binary',
        'metric': 'auc',
        'boosting_type': 'gbdt',
        'num_leaves': 63,
        'learning_rate': 0.03,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'scale_pos_weight': scale_pos_weight,
        'seed': 42,
        'verbosity': -1,
    }

    train_set = lgb.Dataset(X_train, label=y_train, categorical_feature=cat_cols)
    val_set = lgb.Dataset(X_val, label=y_val, reference=train_set, categorical_feature=cat_cols)

    model = lgb.train(
        params,
        train_set,
        num_boost_round=2000,
        valid_sets=[train_set, val_set],
        valid_names=['train', 'val'],
        callbacks=[lgb.early_stopping(100), lgb.log_evaluation(50)],
    )

    model.save_model('models/fraud_spike_lgbm.txt')
    
    # Train Isolation Forest
    numeric_cols = [c for c in feature_cols if str(train[c].dtype) != 'category']
    X_train_num = X_train[numeric_cols].fillna(0)
    iso_forest = IsolationForest(n_estimators=100, contamination=0.01, random_state=42)
    iso_forest.fit(X_train_num)
    
    os.makedirs('models', exist_ok=True)
    joblib.dump(iso_forest, 'models/fraud_spike_isoforest.joblib')
    
    return model, iso_forest, feature_cols, (train, val, test)

def evaluate(model, iso_forest, feature_cols, test_df):
    X_test, y_test = test_df[feature_cols], test_df['isFraud']
    y_proba = model.predict(X_test, num_iteration=model.best_iteration)

    roc_auc = roc_auc_score(y_test, y_proba)
    pr_auc = average_precision_score(y_test, y_proba)

    fn_cost = test_df.loc[test_df['isFraud'] == 1, 'TransactionAmt'].median()
    fp_cost = test_df.loc[test_df['isFraud'] == 0, 'TransactionAmt'].median() * 0.05

    best_threshold, best_cost = 0.5, float('inf')
    for t in np.arange(0.01, 0.99, 0.01):
        preds = (y_proba >= t).astype(int)
        fp = int(((preds == 1) & (y_test == 0)).sum())
        fn = int(((preds == 0) & (y_test == 1)).sum())
        cost = fp * fp_cost + fn * fn_cost
        if cost < best_cost:
            best_cost, best_threshold = cost, t

    final_preds = (y_proba >= best_threshold).astype(int)
    naive_cost = (y_test == 1).sum() * fn_cost
    
    numeric_cols = [c for c in feature_cols if str(test_df[c].dtype) != 'category']
    X_test_num = X_test[numeric_cols].fillna(0)
    anomaly_scores = -iso_forest.score_samples(X_test_num)
    avg_anomaly_fraud = float(np.mean(anomaly_scores[y_test == 1])) if (y_test == 1).sum() > 0 else 0.0
    avg_anomaly_legit = float(np.mean(anomaly_scores[y_test == 0])) if (y_test == 0).sum() > 0 else 0.0

    report = {
        'roc_auc': round(float(roc_auc), 4),
        'pr_auc': round(float(pr_auc), 4),
        'threshold': round(float(best_threshold), 2),
        'precision': round(float(precision_score(y_test, final_preds)), 4),
        'recall': round(float(recall_score(y_test, final_preds)), 4),
        'f1': round(float(f1_score(y_test, final_preds)), 4),
        'assumed_fp_cost': round(float(fp_cost), 2),
        'assumed_fn_cost': round(float(fn_cost), 2),
        'expected_cost_at_threshold': round(float(best_cost), 2),
        'naive_baseline_cost': round(float(naive_cost), 2),
        'cost_reduction_vs_baseline_pct': round(100 * (1 - best_cost / max(naive_cost, 1)), 2),
        'avg_anomaly_score_fraud': round(avg_anomaly_fraud, 4),
        'avg_anomaly_score_legit': round(avg_anomaly_legit, 4),
    }

    with open('artifacts/metrics_report.json', 'w') as f:
        json.dump(report, f, indent=2)

    return report
