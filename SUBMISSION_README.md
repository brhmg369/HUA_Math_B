# 华数杯 B 题提交包说明

本提交包包含 VLSI 布图规划建模论文、LaTeX 源文件、Python 求解与绘图程序、题目数据以及最终结果文件。

## 目录结构

- `paper/main.pdf`：最终论文 PDF。
- `paper/main.tex`、`paper/sections/`、`paper/references.tex`：论文 LaTeX 源文件。
- `src/`：问题一至问题四的求解与绘图程序。
- `results/`：最终数值结果、布局坐标、验证记录与图形。
- `2026年第七届华数杯数学建模竞赛赛题/`：题面、原始附件与参考资料。
- `requirements.txt`：Python 依赖。

## 复现方法

在项目根目录执行：

```powershell
pip install -r requirements.txt
python src\q1_floorplanning.py --output-dir results\q1
python src\q2_fixed_outline_hpwl.py --output-dir results\q2 --refine-passes 2 --refine-top 3 --refine-method mixed
python src\q3_min_deadspace.py --output-dir results\q3 --refine-passes 2 --refine-top 3 --refine-method mixed
python src\q4_nonrect_floorplanning.py --output-dir results\q4
```

在 `paper` 目录连续编译两次论文：

```powershell
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex
```

最终 PDF 已经连续两遍 XeLaTeX 编译、日志检查和逐页渲染抽查。
