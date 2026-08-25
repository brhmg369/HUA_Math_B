# 队友 fork 部分采纳修改说明

> 修改日期：2026-08-25
> 审核对象：队友 fork `Yclar/HUA_Math_B`，审核时参考提交 `3b10148`
> 本仓库目标分支：`main`
> 处理结论：部分采纳，不做整仓合并

## 1. 为什么是部分采纳

队友 fork 指出了前两处关键口径问题，这两点是正确且需要修正的：

1. 第二问 fixed-outline 的死区率公式应使用连续轮廓面积，不能把边长简单向上取整后再说实际死区率略大于 0.15。
2. 第三问中 terminal 更合理的处理是只作为 HPWL 固定 pin，不作为 hard-block outline 的边界硬约束。

但 fork 也存在不能整仓采纳的问题：

- fork 基于较早版本，未包含本仓库已经完成的第四问；
- fork 的 Q3 文档较短，不能替代当前面向论文手的详细同步文档；
- fork 对“最小死区率”的部分表述仍容易被写成严格全局证明，而当前 packing 构造器不是完备可行性判定器；
- 因此采取“采纳核心口径与结果方向，保留本仓库结构、Q4、详细论文文档和验证体系”的方案。

## 2. 已采纳内容

### 2.1 Q2 连续 fixed-outline 口径

已修改 `src/q2_fixed_outline_hpwl.py`：

- 新增 `outline_side`，保存连续边长；
- 轮廓面积使用 \(L_{\mathrm{cont}}^2=(1+\Gamma)A_{\mathrm{blocks}}\)；
- 整数坐标合法化使用 \(G=\lfloor L_{\mathrm{cont}}\rfloor\)；
- summary 输出同时保留 `grid_side` 和 `outline_side`；
- validation、SVG、PNG 标题均同步连续轮廓口径。

Q2 重新运行后结果：

| 芯片 | grid_side | outline_side | deadspace | HPWL |
|---|---:|---:|---:|---:|
| n100 | 454 | 454.341446492 | 0.15000000 | 220279.0 |
| n200 | 449 | 449.500166852 | 0.15000000 | 410072.5 |
| n300 | 560 | 560.486841951 | 0.15000000 | 560492.5 |

### 2.2 Q3 terminal 口径

已修改 `src/q3_min_deadspace.py`：

- terminal 不再进入 hard-block 搜索下界；
- 正式下界改为 `max(area_lower_bound, block_side_lower_bound)`；
- terminal 最大坐标仅作为 `terminal_coordinate_side` 和 `terminal_inside_sensitivity_side` 诊断列；
- validation 中 `terminal_out_of_bounds_count` 不再使结果 invalid；
- 新增 `terminals_constrained=false`，明确正式模型不以 terminal 为轮廓约束；
- 默认 refinement 方法改为 `mixed`，与 Q2 运行口径一致。

Q3 重新运行后结果：

| 芯片 | lower_bound_side | first feasible side | deadspace | HPWL | terminal_outside_count |
|---|---:|---:|---:|---:|---:|
| n100 | 424 | 439 | 0.07364861 | 239551.0 | 168 |
| n200 | 420 | 432 | 0.06219834 | 442024.0 | 284 |
| n300 | 523 | 537 | 0.05563935 | 640695.5 | 290 |

注意：这里的 first feasible side 是当前确定性 packing 搜索预算下找到的首个可行边长，不写成严格全局最小边长。

### 2.3 论文手同步文档

已重写并更新：

- `docs/q2_paper_writer_sync.md`
- `docs/q3_paper_writer_sync.md`

文档中已补充：

- Q2 连续边长和整数坐标边界的关系；
- Q3 terminal 只参与 HPWL 的正式口径；
- Q3 terminal-inside 替代解释的敏感性说明；
- 哪些结论可以写，哪些不能写；
- 推荐放哪些表、哪些图、哪些算法流程和验证表；
- 摘要、结果分析、模型假设、边界情况的可直接使用句式。

## 3. 未采纳内容

### 3.1 未整仓合并 fork

不采纳整仓合并，原因是 fork 落后本仓库主线，且不包含已完成的第四问。如果整仓覆盖，会丢失 Q4 代码、结果和论文同步文档。

### 3.2 未删除或回退第四问

本轮只修正第二问和第三问，不影响第四问。`src/q4_nonrect_floorplanning.py`、`docs/q4_paper_writer_sync.md` 和 `results/q4/` 均保留。

### 3.3 未采纳“严格全局最小死区率”表述

当前 Q3 的边长搜索使用 deterministic packing constructors。构造成功可以证明该边长可行；构造失败不能证明该边长数学不可行。因此论文中只能写：

> 在当前确定性 packing 搜索预算下，搜索得到的首个可行边长为……

不能写：

> 已证明所有更小边长不可行。

### 3.4 未把 terminal-inside 作为正式约束

terminal-inside 只作为敏感性诊断保留：

| 芯片 | official Q3 side | terminal-inside sensitivity side |
|---|---:|---:|
| n100 | 439 | 444 |
| n200 | 432 | 438 |
| n300 | 537 | 548 |

论文正文的正式模型按 terminal 只参与 HPWL 写；若讨论题意歧义，再单独说明该敏感性边界。

## 4. 重新生成的文件

代码：

- `src/q2_fixed_outline_hpwl.py`
- `src/q3_min_deadspace.py`

文档：

- `README.md`
- `docs/q2_paper_writer_sync.md`
- `docs/q3_paper_writer_sync.md`
- `docs/partial_teammate_adoption_note.md`

Q2 结果：

- `results/q2/q2_summary.csv`
- `results/q2/q2_candidate_runs.csv`
- `results/q2/q2_validation.json`
- `results/q2/layouts/*.csv`
- `results/q2/figures/*.png`
- `results/q2/figures/*.svg`

Q3 结果：

- `results/q3/q3_summary.csv`
- `results/q3/q3_feasibility_log.csv`
- `results/q3/q3_candidate_runs.csv`
- `results/q3/q3_validation.json`
- `results/q3/layouts/*.csv`
- `results/q3/figures/*.png`
- `results/q3/figures/*.svg`

## 5. 已执行校验

已执行：

```powershell
python -m py_compile src\q2_fixed_outline_hpwl.py src\q3_min_deadspace.py
python -m py_compile src\q1_floorplanning.py src\q2_fixed_outline_hpwl.py src\q3_min_deadspace.py src\q4_nonrect_floorplanning.py
```

已重新运行：

```powershell
python src\q2_fixed_outline_hpwl.py --output-dir results\q2 --refine-passes 2 --refine-top 3 --refine-method mixed
python src\q3_min_deadspace.py --output-dir results\q3 --refine-passes 2 --refine-top 3 --refine-method mixed
```

已额外核对：

- Q2/Q3 summary 与 validation JSON 中的 HPWL、边长、死区率一致；
- Q2/Q3 PNG 图像非空；
- Q2/Q3 validation 中 hard block 越界数为 0、重叠数为 0、面积守恒为 true、HPWL 复算一致为 true。

## 6. 给论文手的最终口径

第二问：

> fixed-outline 边长按连续公式 \(L_{\mathrm{cont}}=\sqrt{(1+\Gamma)A_{\mathrm{blocks}}}\) 计算，第二问 \(\Gamma=0.15\)。由于输出坐标为整数，程序使用 \(G=\lfloor L_{\mathrm{cont}}\rfloor\) 进行合法化。三组芯片均得到通过约束校验的 HPWL 可行布局。

第三问：

> terminal 坐标只作为 HPWL 的固定 pin，不作为 hard-block 轮廓硬约束。程序从 hard-block 下界出发逐个整数边长搜索，在当前确定性 packing 搜索预算下得到首个可行边长 439、432、537，并在这些边长下进一步优化 HPWL。该结果不声称全局最小死区率，只作为当前搜索与验证体系下的可复现结果。
