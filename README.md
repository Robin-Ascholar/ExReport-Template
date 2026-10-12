# TJU Thesis Bachelor Template

天津大学本科生毕业论文与课程实验报告的 LaTeX 模板仓库。模板按天津大学 2026 届本科生毕业论文格式整理，也适合结构相近的课程实验报告。

根目录是可复用的干净模板；`examples/` 保存已经完成的实验示例。每次开始新报告时，建议从仓库下载或复制根目录模板，避免在旧实验目录上继续修改。

## 目录结构

```text
.
├── contents/                 # 封面信息、摘要、章节和附录
├── figures/                  # 学校 Logo、校名等模板资源
├── examples/                 # 已完成的实验示例，不参与根目录编译
├── tjuthesis-Bachelor.cls    # 模板格式定义
├── tjumian.tex               # 唯一编译入口
├── reference.bib             # 参考文献库
├── 独创性声明.pdf             # 签字后替换的声明页
└── .vscode/                  # LaTeX Workshop 编译配置
```

模板基于 `ctexbook` 构建，参考天津大学本科生毕业设计（论文）相关撰写规范及往年开源模板。格式文件仅提供排版能力，具体课程的封面字段、章节要求和评分标准仍以任课教师发布的要求为准。

## 快速开始

### 环境要求

当前模板主要在 Windows + TeX Live 环境下测试。需要安装 XeLaTeX、Biber 和 `latexmk`，并确保系统中存在 `SimSun`、`SimHei`、`Times New Roman` 等字体。

Overleaf 和 macOS 未在本仓库中做完整验证；如果字体名称不同，需要修改 `tjuthesis-Bachelor.cls` 中的字体设置。

### 使用方法

1. 下载仓库后，在根目录打开 VS Code。
2. 在 `contents/introduction.tex` 中填写 `\ctitle`、`\cauthor`、`\cnumber`、`\csupervisor` 等封面信息，以及中英文摘要和关键词。
3. 在 `contents/` 下编辑章节。增删章节时，同步修改 `tjumian.tex` 中的 `\include`。
4. 将图片放入 `figures/`，使用模板提供的 `\figuremacro`、`\tablemacro` 命令插入图表，并使用 `\ref{label}` 交叉引用。
5. 在 `reference.bib` 中添加 BibLaTeX 文献条目，在正文中使用 `\cite{label}` 引用。
6. 如需加入签字后的独创性声明，将扫描件命名为 `独创性声明.pdf` 并替换根目录文件；是否插入声明页由 `tjumian.tex` 控制。
7. 使用 LaTeX Workshop 的“构建 LaTeX 项目”编译。辅助文件已写入 `.gitignore`，也可以使用插件的“清除辅助文件”功能清理。

命令行编译：

```powershell
latexmk -xelatex -interaction=nonstopmode -file-line-error tjumian.tex
```

清理编译产物：

```powershell
latexmk -C tjumian.tex
```

## 开始一份新报告

建议流程：

1. 复制仓库根目录到新的报告目录，并删除或保留 `examples/`；
2. 修改 `contents/introduction.tex` 的封面、摘要和关键词；
3. 按实验要求修改章节文件，图片统一放入 `figures/`；
4. 将数据分析代码放在单独的 `scripts/` 或 `data/` 目录，不和模板源码混放；
5. 编译检查目录、引用、图表和参考文献，提交前运行 `latexmk -C` 清理辅助文件；
6. 最终提交源文件和 PDF，实验数据是否入库按文件大小、版权和课程要求决定。

不建议把个人姓名、学号、实验数据和编译产物直接提交到模板根目录。模板仓库可以长期公开维护，具体报告则应作为独立项目或 `examples/` 下的归档。

## 如何贡献

如果发现模板问题，欢迎提交 Issue 或 Pull Request。提交前请确认根目录模板可以正常编译，并且没有将个人信息、实验数据和 LaTeX 辅助文件混入模板源码。

## 许可证

本项目基于 GPL-3.0 许可证开源，详情请参见 `LICENSE` 文件。

## 致谢

本模板参考了 `hyzhangtjnk/TJU-2024-Graduation-Thesis` 和 `haimingz/tjuthesis`，感谢相关作者和 LaTeX 宏包维护者。
