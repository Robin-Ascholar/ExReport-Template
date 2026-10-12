from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import TimeSeriesSplit


TARGET_COL = "Sal"
KEY_COLS = ["ZDMC", "DataTime"]
RIDGE_CANDIDATES = [0.1, 1.0, 10.0, 100.0]


def find_split_dirs(base_dir: Path) -> Tuple[Path, Path]:
    train_dir = next((p for p in base_dir.iterdir() if p.is_dir() and "训练" in p.name), None)
    test_dir = next((p for p in base_dir.iterdir() if p.is_dir() and "测试" in p.name), None)
    if train_dir is None or test_dir is None:
        raise RuntimeError(f"未找到训练/测试目录，请检查: {base_dir}")
    return train_dir, test_dir


def read_table(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df["DataTime"] = pd.to_datetime(df["DataTime"], errors="coerce")
    df = df.dropna(subset=["ZDMC", "DataTime"])
    df = df.drop_duplicates(subset=KEY_COLS, keep="first")
    return df


def merge_multisource(split_dir: Path) -> pd.DataFrame:
    files = sorted(split_dir.glob("*.xlsx"))
    if len(files) != 5:
        raise RuntimeError(f"Expected 5 source files in {split_dir}, got {len(files)}")

    anchor_file = next((f for f in files if "03." in f.name), files[0])
    other_files = [f for f in files if f != anchor_file]

    merged = read_table(anchor_file)
    for file_path in other_files:
        df = read_table(file_path)
        merged = merged.merge(df, on=KEY_COLS, how="left", suffixes=("", "_dup"))
        dup_cols = [c for c in merged.columns if c.endswith("_dup")]
        if dup_cols:
            merged = merged.drop(columns=dup_cols)

    return merged.sort_values(KEY_COLS).reset_index(drop=True)


def sanitize_physical_ranges(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.copy()
    rules = {
        "pH": (0.0, 14.0),
        "Sal": (0.0, 45.0),
        "TDS_ppt": (0.0, None),
        "DO_ppm": (0.0, None),
    }
    for col, (low, high) in rules.items():
        if col not in clean.columns:
            continue
        mask = pd.Series(False, index=clean.index)
        if low is not None:
            mask |= clean[col] < low
        if high is not None:
            mask |= clean[col] > high
        clean.loc[mask, col] = np.nan
    return clean


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["hour"] = out["DataTime"].dt.hour
    out["dayofweek"] = out["DataTime"].dt.dayofweek
    out["month"] = out["DataTime"].dt.month
    out["hour_sin"] = np.sin(2 * np.pi * out["hour"] / 24.0)
    out["hour_cos"] = np.cos(2 * np.pi * out["hour"] / 24.0)
    out["month_sin"] = np.sin(2 * np.pi * out["month"] / 12.0)
    out["month_cos"] = np.cos(2 * np.pi * out["month"] / 12.0)
    return out


def build_xy_hourly(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    data = add_time_features(df)
    y = data[TARGET_COL]
    keep = y.notna()
    data = data.loc[keep].copy()
    y = y.loc[keep].copy()

    drop_cols = ["DataTime", TARGET_COL]
    X = data.drop(columns=[c for c in drop_cols if c in data.columns])
    return X, y


def to_daily(df: pd.DataFrame) -> pd.DataFrame:
    work = add_time_features(df)
    work["date"] = work["DataTime"].dt.floor("D")

    numeric_cols = [
        c
        for c in work.select_dtypes(include=[np.number]).columns
        if c not in {"hour", "dayofweek", "month"}
    ]

    agg_spec = {c: ["mean", "std", "min", "max"] for c in numeric_cols}
    grouped = work.groupby(["ZDMC", "date"], as_index=False).agg(agg_spec)
    grouped.columns = [
        "_".join(col).strip("_") if isinstance(col, tuple) else col for col in grouped.columns
    ]

    grouped["month"] = grouped["date"].dt.month
    grouped["dayofyear"] = grouped["date"].dt.dayofyear
    return grouped


def build_xy_daily(df_daily: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    target_name = f"{TARGET_COL}_mean"
    if target_name not in df_daily.columns:
        raise RuntimeError(f"Missing {target_name} in daily dataset")

    y = df_daily[target_name]
    keep = y.notna()
    data = df_daily.loc[keep].copy()
    y = y.loc[keep].copy()

    drop_cols = ["date", target_name]
    X = data.drop(columns=[c for c in drop_cols if c in data.columns])
    leak_cols = [c for c in X.columns if c.startswith("Sal_")]
    if leak_cols:
        X = X.drop(columns=leak_cols)
    return X, y


def tune_ridge_alpha(X_train: pd.DataFrame, y_train: pd.Series) -> float:
    splitter = TimeSeriesSplit(n_splits=5)
    best_alpha = RIDGE_CANDIDATES[0]
    best_rmse = float("inf")

    for alpha in RIDGE_CANDIDATES:
        fold_rmse: List[float] = []
        for tr_idx, va_idx in splitter.split(X_train):
            X_tr = X_train.iloc[tr_idx]
            y_tr = y_train.iloc[tr_idx]
            X_va = X_train.iloc[va_idx]
            y_va = y_train.iloc[va_idx]

            pipe = make_regression_pipeline(X_tr, Ridge(alpha=alpha))
            pipe.fit(X_tr, y_tr)
            pred = pipe.predict(X_va)
            rmse = float(np.sqrt(mean_squared_error(y_va, pred)))
            fold_rmse.append(rmse)

        avg_rmse = float(np.mean(fold_rmse))
        if avg_rmse < best_rmse:
            best_rmse = avg_rmse
            best_alpha = alpha

    return best_alpha


def make_regression_pipeline(X: pd.DataFrame, model) -> Pipeline:
    categorical_cols = [
        c
        for c in X.columns
        if pd.api.types.is_object_dtype(X[c])
        or pd.api.types.is_string_dtype(X[c])
        or isinstance(X[c].dtype, pd.CategoricalDtype)
    ]
    numeric_cols = [c for c in X.columns if c not in categorical_cols]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_cols,
            ),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_cols,
            ),
        ]
    )

    return Pipeline(steps=[("preprocessor", preprocessor), ("model", model)])


def evaluate_regression(y_true: pd.Series, y_pred: np.ndarray) -> Dict[str, float]:
    mse = mean_squared_error(y_true, y_pred)
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mse)),
        "r2": float(r2_score(y_true, y_pred)),
    }


def train_and_eval(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    output_dir: Path,
    tag: str,
) -> pd.DataFrame:
    best_alpha = tune_ridge_alpha(X_train, y_train)
    models = {
        "LinearRegression": LinearRegression(),
        f"Ridge(alpha={best_alpha})": Ridge(alpha=best_alpha),
    }

    metrics: List[Dict[str, float | str]] = []
    preds_cache: Dict[str, np.ndarray] = {}

    for name, model in models.items():
        pipeline = make_regression_pipeline(X_train, model)
        pipeline.fit(X_train, y_train)
        pred = pipeline.predict(X_test)
        preds_cache[name] = pred

        item = evaluate_regression(y_test, pred)
        item["model"] = name
        metrics.append(item)

    metrics_df = pd.DataFrame(metrics).sort_values("rmse")
    metrics_df.to_csv(output_dir / f"metrics_{tag}.csv", index=False, encoding="utf-8-sig")

    best_model_name = metrics_df.iloc[0]["model"]
    best_pred = preds_cache[best_model_name]

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(y_test, best_pred, alpha=0.25, s=12)
    y_min = min(float(y_test.min()), float(np.min(best_pred)))
    y_max = max(float(y_test.max()), float(np.max(best_pred)))
    ax.plot([y_min, y_max], [y_min, y_max], linestyle="--")
    ax.set_xlabel("True Sal")
    ax.set_ylabel("Predicted Sal")
    ax.set_title(f"{tag} best model: {best_model_name}")
    fig.tight_layout()
    fig.savefig(output_dir / f"scatter_{tag}_best.png", dpi=180)
    plt.close(fig)

    return metrics_df


def run_clustering(
    train_daily: pd.DataFrame,
    test_daily: pd.DataFrame,
    output_dir: Path,
) -> Dict[str, float | int]:
    feature_cols = [
        c for c in train_daily.columns if c not in {"date", "Sal_mean", "ZDMC"}
    ]

    X_train = train_daily[feature_cols]
    X_test = test_daily[feature_cols]

    prep = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    X_train_t = prep.fit_transform(X_train)
    X_test_t = prep.transform(X_test)

    best_k = None
    best_score = -1.0
    for k in range(2, 7):
        km = KMeans(n_clusters=k, random_state=42, n_init=20)
        labels = km.fit_predict(X_train_t)
        score = silhouette_score(X_train_t, labels)
        if score > best_score:
            best_score = score
            best_k = k

    if best_k is None:
        raise RuntimeError("无法确定聚类簇数，请检查训练数据是否有效。")
    model = KMeans(n_clusters=best_k, random_state=42, n_init=20)
    train_labels = model.fit_predict(X_train_t)
    test_labels = model.predict(X_test_t)

    train_out = train_daily.copy()
    test_out = test_daily.copy()
    train_out["cluster"] = train_labels
    test_out["cluster"] = test_labels

    combined = pd.concat([
        train_out.assign(split="train"),
        test_out.assign(split="test"),
    ], ignore_index=True)

    key_vars = [
        c
        for c in ["Sal_mean", "Temp_C_mean", "pH_mean", "Turb_NTU_mean", "WSavg_mean", "Abs_speed_mean"]
        if c in combined.columns
    ]

    cluster_profile = (
        combined.groupby("cluster")[key_vars]
        .mean()
        .round(4)
        .reset_index()
        .sort_values("cluster")
    )
    cluster_profile.to_csv(output_dir / "cluster_profile.csv", index=False, encoding="utf-8-sig")

    cluster_counts = combined.groupby(["split", "cluster"]).size().unstack(fill_value=0)
    cluster_counts.to_csv(output_dir / "cluster_counts.csv", encoding="utf-8-sig")

    fig, ax = plt.subplots(figsize=(7, 4))
    cluster_counts.T.plot(kind="bar", ax=ax)
    ax.set_xlabel("Cluster")
    ax.set_ylabel("Count")
    ax.set_title(f"Daily clusters (k={best_k})")
    fig.tight_layout()
    fig.savefig(output_dir / "cluster_counts.png", dpi=180)
    plt.close(fig)

    return {"best_k": int(best_k), "silhouette": float(best_score)}


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    output_dir = base_dir / "outputs"
    output_dir.mkdir(exist_ok=True)

    train_dir, test_dir = find_split_dirs(base_dir)
    train_raw = sanitize_physical_ranges(merge_multisource(train_dir))
    test_raw = sanitize_physical_ranges(merge_multisource(test_dir))

    summary = {
        "train_rows_merged": int(len(train_raw)),
        "test_rows_merged": int(len(test_raw)),
        "train_time_min": str(train_raw["DataTime"].min()),
        "train_time_max": str(train_raw["DataTime"].max()),
        "test_time_min": str(test_raw["DataTime"].min()),
        "test_time_max": str(test_raw["DataTime"].max()),
    }

    X_train_h, y_train_h = build_xy_hourly(train_raw)
    X_test_h, y_test_h = build_xy_hourly(test_raw)
    hourly_metrics = train_and_eval(
        X_train_h, y_train_h, X_test_h, y_test_h, output_dir, tag="hourly"
    )

    train_daily = to_daily(train_raw)
    test_daily = to_daily(test_raw)
    X_train_d, y_train_d = build_xy_daily(train_daily)
    X_test_d, y_test_d = build_xy_daily(test_daily)
    daily_metrics = train_and_eval(
        X_train_d, y_train_d, X_test_d, y_test_d, output_dir, tag="daily"
    )

    clustering_info = run_clustering(train_daily, test_daily, output_dir)

    summary["hourly_best_model"] = str(hourly_metrics.iloc[0]["model"])
    summary["hourly_best_rmse"] = float(hourly_metrics.iloc[0]["rmse"])
    summary["daily_best_model"] = str(daily_metrics.iloc[0]["model"])
    summary["daily_best_rmse"] = float(daily_metrics.iloc[0]["rmse"])
    summary.update(clustering_info)

    with open(output_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("=== Run completed ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Outputs saved to: {output_dir}")


if __name__ == "__main__":
    main()
