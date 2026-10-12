
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 中文显示配置
matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

COLORS = {
    "blue": "#2F5597",
    "orange": "#E67E22",
    "green": "#3A7D44",
    "red": "#C0392B",
    "gray": "#7F8C8D",
}

BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"
FIGURES_DIR = BASE_DIR / "figures"
FIGURES_DIR.mkdir(exist_ok=True)


def ensure_outputs_exist() -> None:
    required = [
        "metrics_hourly.csv",
        "metrics_daily.csv",
        "cluster_counts.csv",
        "cluster_profile.csv",
        "summary.json",
        "scatter_hourly_best.png",
        "scatter_daily_best.png",
    ]
    missing = [name for name in required if not (OUTPUTS_DIR / name).exists()]
    if missing:
        joined = "\n- ".join([""] + missing)
        raise FileNotFoundError(
            f"缺少结果文件，请先运行 run_experiments.py。缺失文件:{joined}"
        )


def pick_ridge_name(df: pd.DataFrame) -> str:
    ridge_rows = df[df["model"].str.contains("Ridge", na=False)]
    if ridge_rows.empty:
        return "Ridge"
    return str(ridge_rows.iloc[0]["model"])


def plot_metric_comparison() -> None:
    hourly = pd.read_csv(OUTPUTS_DIR / "metrics_hourly.csv")
    daily = pd.read_csv(OUTPUTS_DIR / "metrics_daily.csv")

    h = hourly.set_index("model")
    d = daily.set_index("model")

    ridge_h = pick_ridge_name(hourly)
    ridge_d = pick_ridge_name(daily)

    model_labels = ["LinearRegression", "Ridge"]
    metric_defs = [
        ("mae", "MAE"),
        ("rmse", "RMSE"),
        ("r2", "R²"),
    ]

    x = np.arange(len(model_labels))
    width = 0.34

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for i, (key, title) in enumerate(metric_defs):
        ax = axes[i]

        hourly_vals = [
            float(h.get(key, pd.Series()).get("LinearRegression", 0.0)),
            float(h.get(key, pd.Series()).get(ridge_h, 0.0)),
        ]
        daily_vals = [
            float(d.get(key, pd.Series()).get("LinearRegression", 0.0)),
            float(d.get(key, pd.Series()).get(ridge_d, 0.0)),
        ]

        bars1 = ax.bar(x - width / 2, hourly_vals, width, label="小时级", color=COLORS["blue"], alpha=0.85)
        bars2 = ax.bar(x + width / 2, daily_vals, width, label="天级", color=COLORS["orange"], alpha=0.85)

        for bars in (bars1, bars2):
            for bar in bars:
                y = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2, y, f"{y:.3f}", ha="center", va="bottom", fontsize=9)

        ax.set_xticks(x)
        ax.set_xticklabels(model_labels)
        ax.set_title(f"{title} 对比")
        ax.grid(axis="y", alpha=0.25)
        ax.set_axisbelow(True)

    axes[0].legend()
    fig.suptitle("模型性能对比（小时级 vs 天级）")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "图5_模型指标对比.png", dpi=220)
    plt.close(fig)


def plot_cluster_counts() -> None:
    counts = pd.read_csv(OUTPUTS_DIR / "cluster_counts.csv", index_col=0)
    with open(OUTPUTS_DIR / "summary.json", "r", encoding="utf-8") as f:
        summary = json.load(f)

    k = int(summary.get("best_k", counts.shape[1]))
    x = np.arange(k)
    width = 0.34

    train = counts.loc["train"] if "train" in counts.index else counts.iloc[0]
    test = counts.loc["test"] if "test" in counts.index else counts.iloc[-1]

    train_vals = [int(train.get(str(i), train.get(i, 0))) for i in range(k)]
    test_vals = [int(test.get(str(i), test.get(i, 0))) for i in range(k)]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars1 = ax.bar(x - width / 2, train_vals, width, label="训练集", color=COLORS["blue"], alpha=0.85)
    bars2 = ax.bar(x + width / 2, test_vals, width, label="测试集", color=COLORS["orange"], alpha=0.85)

    for bars in (bars1, bars2):
        for bar in bars:
            y = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, y, f"{int(y)}", ha="center", va="bottom", fontsize=10)

    ax.set_xticks(x)
    ax.set_xticklabels([f"簇{i}" for i in range(k)])
    ax.set_xlabel("聚类簇")
    ax.set_ylabel("样本数")
    ax.set_title(f"聚类样本分布（k={k}, 轮廓系数={summary.get('silhouette', 0):.3f}）")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "图3_聚类样本分布.png", dpi=220)
    plt.close(fig)


def plot_cluster_profile_radar() -> None:
    profile = pd.read_csv(OUTPUTS_DIR / "cluster_profile.csv")

    features = [
        ("Sal_mean", "盐度"),
        ("Temp_C_mean", "温度"),
        ("pH_mean", "pH"),
        ("Turb_NTU_mean", "浊度"),
        ("WSavg_mean", "风速"),
        ("Abs_speed_mean", "流速"),
    ]
    usable = [(col, label) for col, label in features if col in profile.columns]
    if len(usable) < 3:
        return

    cols = [c for c, _ in usable]
    labels = [l for _, l in usable]

    data = profile[cols].copy()
    span = (data.max() - data.min()).replace(0, 1.0)
    norm = (data - data.min()) / span

    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"polar": True})
    palette = [COLORS["blue"], COLORS["orange"], COLORS["green"], COLORS["red"]]

    for i, row in norm.iterrows():
        vals = row.to_list()
        vals += vals[:1]
        cluster_id = int(profile.iloc[i]["cluster"]) if "cluster" in profile.columns else i
        color = palette[i % len(palette)]
        ax.plot(angles, vals, linewidth=2, color=color, label=f"簇{cluster_id}")
        ax.fill(angles, vals, color=color, alpha=0.14)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1)
    ax.set_title("聚类画像雷达图（各指标归一化）", pad=18)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1))

    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "图4_聚类画像雷达图.png", dpi=220)
    plt.close(fig)


def copy_core_scatter_figures() -> None:
    mapping = {
        OUTPUTS_DIR / "scatter_hourly_best.png": FIGURES_DIR / "图1_小时级预测散点图.png",
        OUTPUTS_DIR / "scatter_daily_best.png": FIGURES_DIR / "图2_天级预测散点图.png",
        OUTPUTS_DIR / "cluster_counts.png": FIGURES_DIR / "图6_聚类原始柱状图.png",
    }
    for src, dst in mapping.items():
        img = plt.imread(src)
        plt.figure(figsize=(8, 6))
        plt.imshow(img)
        plt.axis("off")
        plt.tight_layout()
        plt.savefig(dst, dpi=220)
        plt.close()


def main() -> None:
    ensure_outputs_exist()

    copy_core_scatter_figures()
    plot_cluster_counts()
    plot_cluster_profile_radar()
    plot_metric_comparison()

    print("图表已生成，输出目录:", FIGURES_DIR)


if __name__ == "__main__":
    main()
