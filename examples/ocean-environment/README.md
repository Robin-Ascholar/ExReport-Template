# 海洋环境数据实验示例

这是一个基于本仓库模板完成的课程实验报告示例，主题为多源海洋监测数据的盐度变化分析与预测。

- `report/`：该实验报告的 LaTeX 源文件和章节内容；
- `data/`：训练集、测试集和字段说明；
- `scripts/`：实验运行和绘图脚本；
- `figures/`：实验图表；
- `outputs/`：模型指标、聚类结果和中间输出；
- `report.pdf`：归档时生成的报告成品。

示例用于参考报告结构和数据分析流程。新实验请从仓库根目录模板开始，不要直接覆盖本示例。

在 `report/` 目录中运行 `latexmk -xelatex -interaction=nonstopmode -file-line-error tjumian.tex` 可以单独编译该示例；编译前请确保已安装 XeLaTeX、Biber 和 `latexmk`。
