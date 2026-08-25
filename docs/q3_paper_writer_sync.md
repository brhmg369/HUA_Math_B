# 第三问论文手同步文档：修正 terminal 口径后的最小死区率搜索

> 任务状态：第三问已按队友 fork 的关键口径部分采纳并重跑。正式模型中 terminal 只作为 HPWL 固定 pin，不作为 hard-block 轮廓约束；Q3 结果、图、CSV、JSON 与论文写法均已同步更新。
> 主程序：`src/q3_min_deadspace.py`
> 主结果目录：`results/q3`
> 关联结果：`results/q2/q2_summary.csv`

## 0. 本轮修正结论

第三问之前最大的错误，是把 terminal 当成必须位于芯片轮廓内的硬约束。按题目和附件更稳妥的解释：

```text
hard block：参与面积、旋转、边界、不重叠约束。
terminal：由 .pl 给定固定坐标，只参与 HPWL 计算，不参与面积、不参与重叠、不强制落在 Q3 压缩后的 hard-block outline 内。
```

因此，第三问的第一层目标应是：

> 在 hard blocks 全部不重叠并位于正方形轮廓内的前提下，搜索尽可能小的整数边长 \(S\)，并计算对应死区率；随后在该边长下优化 HPWL。

本轮程序从由 hard blocks 给出的理论下界开始逐个整数边长搜索，没有使用任意小数死区率步长。当前确定性 packing 搜索得到的第一个可行边长为：

| 芯片 | hard-block 下界 | 搜索得到的首个可行边长 | 死区率 | terminal-inside 敏感性边长 |
|---|---:|---:|---:|---:|
| n100 | 424 | 439 | 0.07364861 | 444 |
| n200 | 420 | 432 | 0.06219834 | 438 |
| n300 | 523 | 537 | 0.05563935 | 548 |

论文中必须谨慎写：

- 可以写“当前确定性 packing 搜索预算下找到的最小可行边长”；
- 不可以写“已证明全局最小边长”；
- 可以写“若另采用 terminal 必须位于轮廓内的替代解释，则边长至少为 444/438/548，这只是敏感性边界，不是正式约束”。

## 1. 题意拆解

第三问依赖第二问，但目标层级发生变化。第二问给定 \(\Gamma=0.15\)，只优化 HPWL；第三问把 dead-space ratio 变成待压缩对象。

| 子任务 | 输入 | 输出 | 与前问关系 | 本轮写法 |
|---|---|---|---|---|
| Q3a 压缩边长 | hard blocks | 首个搜索可行边长 \(S_{\mathrm{found}}\)、\(\Gamma(S_{\mathrm{found}})\) | 复用 Q2 的 fixed-outline 几何约束 | 确定性构造搜索结果，不称全局证明 |
| Q3b 线长优化 | \(S_{\mathrm{found}}\)、netlist、terminal 坐标 | 最小边长下的布局和 HPWL | 复用 Q2 解析松弛、合法化、refinement | 当前预算下 HPWL 可行上界 |
| Q3c Q2/Q3 对比 | Q2/Q3 summary | 面积压缩与 HPWL 增量 | 同一 HPWL 定义 | 解释 trade-off |
| Q3d 口径敏感性 | terminal 坐标最大值 | terminal-inside sensitivity side | 用于说明队友修正来源 | 放附表或讨论，不作为正式模型约束 |

推荐主线：

```text
先说明 terminal 只参与 HPWL；
再说明第一层仅对 hard blocks 做 fixed-outline packing；
然后从 hard-block 下界开始枚举整数边长；
找到首个构造可行边长后，在该边长下优化 HPWL；
最后与 Q2 的 Gamma=0.15 结果对比。
```

## 2. 关键建模边界

### 2.1 Terminal 不作为轮廓硬约束

正式模型中 terminal 的用途只有一个：作为 net 的固定 pin 坐标参与 HPWL。

写作要点：

- terminal 坐标不缩放；
- terminal 不参与 hard-block 面积；
- terminal 不与 block 发生重叠约束；
- terminal 不用于判定 block packing 是否越界；
- terminal 可能位于压缩后的 hard-block outline 外，此时 HPWL 会自然反映远端连接代价。

这并不意味着 terminal 被“移动到芯片外”。它们本来就是 `.pl` 给定的固定连接端，Q3 只是压缩 hard-block 摆放区域。

### 2.2 为什么仍记录 terminal_inside_sensitivity_side

队友 fork 的合理提醒是：如果有人把 terminal 也理解为必须处于轮廓内，则最小边长会被 terminal 最大坐标主导。为了避免论文评审出现歧义，本轮保留诊断列：

\[
S_{\mathrm{terminal}}=\left\lceil\max_{t\in T}\max(X_t,Y_t)\right\rceil .
\]

三组数据分别为 444、438、548。该列只说明替代解释下的边界，不参与正式 Q3 可行性判断。

### 2.3 不设置任意死区率步长

第三问不能写成“每次将死区率降低 0.01 直到不可行”。因为这会引入没有依据的步长。当前程序把正方形边长作为离散决策变量：

\[
S\in\mathbb{Z}_{+},\qquad
\Gamma(S)=\frac{S^2-A_{\mathrm{blocks}}}{A_{\mathrm{blocks}}}.
\]

从下界开始逐个整数 \(S\) 搜索，既符合整数坐标输出，也避免任意 \(\Gamma\) 步长。

### 2.4 搜索失败不是数学不可行证明

MaxRects / shelf packing 是构造型启发式，不是完备判定器。若某个边长下候选构造失败，只能写：

> 在当前确定性 packing 候选集内未找到可行布局。

不能写：

> 该边长数学上不可行。

因此，本问结果应称为“搜索得到的首个可行边长”，不是“严格全局最小边长”。

## 3. 数学模型

### 3.1 输入集合和参数

- \(B=\{1,\ldots,n\}\)：hard block 集合；
- \(T\)：terminal 集合；
- \(E\)：net 集合；
- \(w_i,h_i\)：block \(i\) 的原始宽高；
- \(A_{\mathrm{blocks}}=\sum_i w_ih_i\)：所有 block 面积之和；
- \((X_t,Y_t)\)：terminal \(t\) 的固定坐标；
- \(S\)：Q3 搜索的正方形 hard-block outline 整数边长。

### 3.2 决策变量

对每个 block \(i\)：

\[
x_i,y_i\in\mathbb{Z}_{\ge 0},\qquad r_i\in\{0,1\}.
\]

旋转后的宽高为：

\[
(w_i(r_i),h_i(r_i))=
\begin{cases}
(w_i,h_i),& r_i=0,\\
(h_i,w_i),& r_i=1.
\end{cases}
\]

block pin 使用几何中心：

\[
c_i=\left(x_i+\frac{w_i(r_i)}{2},\ y_i+\frac{h_i(r_i)}{2}\right).
\]

### 3.3 hard-block 边界约束

\[
0\le x_i,\quad 0\le y_i,\quad
x_i+w_i(r_i)\le S,\quad
y_i+h_i(r_i)\le S,\qquad \forall i\in B.
\]

### 3.4 hard-block 不重叠约束

任意两个不同模块 \(i,j\) 至少有一个方向分离：

\[
x_i+w_i(r_i)\le x_j
\;\vee\;
x_j+w_j(r_j)\le x_i
\;\vee\;
y_i+h_i(r_i)\le y_j
\;\vee\;
y_j+h_j(r_j)\le y_i,\qquad \forall i<j.
\]

### 3.5 死区率目标

\[
\Gamma(S)=\frac{S^2-A_{\mathrm{blocks}}}{A_{\mathrm{blocks}}}.
\]

由于 \(A_{\mathrm{blocks}}\) 固定，最小化 \(\Gamma(S)\) 等价于最小化 \(S\)。本题采用词典序目标：

\[
\min S,\qquad
\text{then}\quad
\min \sum_{e\in E}\operatorname{HPWL}(e)\ \text{at the found side}.
\]

### 3.6 HPWL 目标

设 net \(e\) 的 pin 坐标集合为 \(\mathcal{P}_e\)。其中 block pin 坐标来自 \(c_i\)，terminal pin 坐标为 `.pl` 给定的 \((X_t,Y_t)\)。则：

\[
\operatorname{HPWL}(e)=
\max_{p\in\mathcal{P}_e} X_p-\min_{p\in\mathcal{P}_e} X_p+
\max_{p\in\mathcal{P}_e} Y_p-\min_{p\in\mathcal{P}_e} Y_p .
\]

第二层目标为：

\[
\min \sum_{e\in E}\operatorname{HPWL}(e).
\]

该目标在 fixed-outline hard-block floorplanning 中仍是 NP-hard，不能宣称全局最优。

## 4. 下界与搜索区间

### 4.1 hard-block 面积下界

任何可行正方形边长必须满足：

\[
S^2\ge A_{\mathrm{blocks}},
\qquad
S_{\mathrm{area}}=\left\lceil\sqrt{A_{\mathrm{blocks}}}\right\rceil .
\]

### 4.2 最大模块边下界

任意 block 无论是否旋转，其较长边必须能被正方形容纳：

\[
S_{\mathrm{block}}=\max_i\max(w_i,h_i).
\]

### 4.3 正式搜索下界

正式 Q3 口径下：

\[
S_{\mathrm{lb}}=\max(S_{\mathrm{area}},S_{\mathrm{block}}).
\]

本轮三组芯片：

| 芯片 | \(A_{\mathrm{blocks}}\) | \(S_{\mathrm{area}}\) | \(S_{\mathrm{block}}\) | \(S_{\mathrm{lb}}\) |
|---|---:|---:|---:|---:|
| n100 | 179501 | 424 | 67 | 424 |
| n200 | 175696 | 420 | 48 | 420 |
| n300 | 273170 | 523 | 48 | 523 |

### 4.4 搜索上界

第二问 \(\Gamma=0.15\) 的结果给出一个已知可行上界。修正后 Q2 使用连续边长，但整数坐标边界分别为：

| 芯片 | Q2 连续边长 \(L_{0.15}\) | Q2 整数坐标边界 \(G_{0.15}\) | Q2 HPWL |
|---|---:|---:|---:|
| n100 | 454.341446492 | 454 | 220279.0 |
| n200 | 449.500166852 | 449 | 410072.5 |
| n300 | 560.486841951 | 560 | 560492.5 |

Q3 在 \([S_{\mathrm{lb}},G_{0.15}]\) 内逐个整数边长搜索。搜索区间短、物理意义明确，不需要二分和小数步长。

## 5. 求解算法

### 5.1 总流程

建议论文配一个算法流程图，节点如下：

```text
读取 blocks / nets / pl
-> 计算 A_blocks、最大模块边、terminal 诊断坐标
-> 得到 hard-block 搜索下界 S_lb
-> 读取 Q2 的 Gamma=0.15 整数坐标边界作为上界
-> 从 S_lb 到上界逐个整数边长做 packing 构造
-> 记录首个可行边长 S_found
-> 在 S_found 下调用 Q2 HPWL 求解器
-> 输出布局、HPWL、Gamma、验证报告和图
```

### 5.2 可行性构造器

第一层只需要找到“存在一个可行 packing”的证据，不需要该 packing 的 HPWL 最优。因此程序使用 `rectpack` 的 MaxRects 变体快速构造可行布局：

```text
MaxRectsBssf / MaxRectsBaf / MaxRectsBlsf
× SORT_AREA / SORT_LSIDE / SORT_SSIDE / SORT_RATIO
```

若 rectpack 构造成功，则得到一个 block 不越界、不重叠的布局证书；若失败，则只表示当前构造器没有找到布局。

### 5.3 最小搜索边长下的 HPWL 更新

确定 \(S_{\mathrm{found}}\) 后，程序重新调用第二问目标引导求解器。该求解器包含：

1. quadratic wirelength relaxation：得到 block 的目标中心；
2. 多种确定性初值：degree/area/target/shelf 等；
3. fixed-outline legalisation：保证 block 不重叠且在边界内；
4. mixed refinement：n100 使用精确重插入，n200/n300 使用快速 HPWL 断点搜索；
5. 复算 HPWL 与可行性验证。

本次正式运行命令为：

```powershell
python src\q3_min_deadspace.py --output-dir results\q3 --refine-passes 2 --refine-top 3 --refine-method mixed
```

### 5.4 伪代码

论文可直接放如下伪代码：

```text
Algorithm Q3 Dead-space Search with HPWL Optimisation
Input: hard blocks, nets, fixed terminal coordinates, Q2 feasible grid side G_0.15
Output: first feasible side S_found, dead-space ratio, placement, HPWL

1. Compute total block area A_blocks.
2. Compute hard-block lower bounds:
      S_area = ceil(sqrt(A_blocks)),
      S_block = max_i max(w_i, h_i).
3. Set S_lb = max(S_area, S_block).
4. Compute the diagnostic terminal side:
      S_terminal = ceil(max_t max(X_t, Y_t)).
5. For S from S_lb to G_0.15:
      5.1 Try deterministic MaxRects packing variants with rotation.
      5.2 If all blocks are placed without overlap inside the S by S square,
          set S_found = S and stop.
6. Compute Gamma_found = (S_found^2 - A_blocks) / A_blocks.
7. Fix S = S_found and run the Q2 HPWL optimiser.
8. Recompute HPWL from the output coordinates.
9. Verify missing/duplicate blocks, boundary, overlap, area conservation,
   terminal diagnostics and HPWL consistency.
```

## 6. 第三问主结果

这张表建议放在“结果与分析”的主文中。

| 芯片 | \(A_{\mathrm{blocks}}\) | 面积下界 | 最大模块边下界 | hard-block 下界 | 搜索首个可行边长 | 死区率 | Q2 HPWL | Q3 HPWL | HPWL 增量 | 增量比例 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| n100 | 179501 | 424 | 67 | 424 | 439 | 0.07364861 | 220279.0 | 239551.0 | 19272.0 | 8.748905% |
| n200 | 175696 | 420 | 48 | 420 | 432 | 0.06219834 | 410072.5 | 442024.0 | 31951.5 | 7.791671% |
| n300 | 273170 | 523 | 48 | 523 | 537 | 0.05563935 | 560492.5 | 640695.5 | 80203.0 | 14.309380% |

正文解释建议：

- 与第二问 \(\Gamma=0.15\) 相比，Q3 把 hard-block outline 明显压缩；
- 轮廓更紧后，模块移动自由度下降，HPWL 上升是合理 trade-off；
- n300 的 HPWL 增量比例最大，说明更大规模和更复杂 netlist 对压缩更敏感；
- 由于 lower_bound_attained_by_search 均为 false，本轮不能写成“下界达成”或“全局最小死区率证明”。

## 7. 搜索日志

完整日志在 `results/q3/q3_feasibility_log.csv`。主文可放压缩表：

| 芯片 | 搜索范围 | 失败边长数 | 首个可行边长 | 构造方法 | 首个可行边长构造时间/s |
|---|---:|---:|---:|---|---:|
| n100 | 424-439 | 15 | 439 | rectpack:MaxRectsBssf:SORT_AREA | 0.0263 |
| n200 | 420-432 | 12 | 432 | rectpack:MaxRectsBssf:SORT_LSIDE | 0.3067 |
| n300 | 523-537 | 14 | 537 | rectpack:MaxRectsBssf:SORT_LSIDE | 0.9009 |

写法提醒：

> 搜索日志说明本文没有使用任意死区率步长，而是在整数边长上逐一构造。由于 packing 构造器并非完备判定器，小于首个可行边长的候选只应表述为“当前构造器未找到可行布局”，不应表述为数学不可行。

## 8. terminal 诊断与敏感性

虽然 terminal 不参与正式 hard-block 轮廓约束，本轮仍保留两个诊断量，方便论文手解释口径差异：

| 芯片 | terminal 坐标边界 | Q3 正式边长 | terminal 越出正式边长的数量 | 若强制 terminal inside 的最小边长下界 |
|---|---:|---:|---:|---:|
| n100 | 444 | 439 | 168 | 444 |
| n200 | 438 | 432 | 284 | 438 |
| n300 | 548 | 537 | 290 | 548 |

解释建议：

- 正式 Q3 中这些 terminal 仍用原始坐标参与 HPWL，因此线长计算没有丢失端点；
- terminal_outside_count 只说明“若把 terminal 画入同一 hard-block outline，会有多少 terminal 位于外侧”；
- 不要把 terminal_outside_count 写成布局无效；
- 若论文评委坚持 terminal 必须位于芯片外框内，可在讨论中说明该替代解释会把边长下界提高到 444/438/548，但这不是本文正式结果。

图注需要谨慎：Q3 主布局图主要展示 hard-block packing；若部分 terminal 在图框外被裁剪，不表示 HPWL 忽略 terminal。建议图注写“terminal 坐标参与 HPWL 复算，部分位于压缩 hard-block outline 外的 terminal 在诊断表中统计”。

## 9. 最小边长下候选 HPWL 对照

主文可放每组最优候选，附录放完整 `q3_candidate_runs.csv`。若篇幅允许，建议放如下压缩表：

| 芯片 | 候选方法 | 初值 HPWL | refinement 后 HPWL | 接受移动数 | refinement |
|---|---|---:|---:|---:|---|
| n100 | shelf_bfd:wide | 244183.0 | 239551.0 | 89 | exact_maxrect_reinsert |
| n200 | shelf_bfd:narrow | 442742.5 | 442024.0 | 81 | fast_hpwl_breakpoint |
| n200 | shelf_bfd:native | 451675.5 | 451160.5 | 56 | fast_hpwl_breakpoint |
| n300 | shelf_bfd:narrow | 644858.0 | 640695.5 | 69 | fast_hpwl_breakpoint |

可解释结论：

- 最小边长处空间极紧，许多 Q2 中可行的 MaxRects 目标引导合法化候选会失败，这是正常现象；
- shelf_bfd 行带构造在极紧边界下更容易给出可行初值；
- refinement 后 HPWL 均下降，说明即使边长被压缩，仍存在局部线长改善空间；
- 候选对照用于说明搜索过程，不构成 HPWL 全局最优证明。

## 10. 可行性验证表

论文建议给一个简化验证表：

| 芯片 | 越界 block 数 | 重叠对数 | 面积守恒 | HPWL 复算一致 | terminal 是否作为硬约束 | terminal 越出诊断数 | valid |
|---|---:|---:|---|---|---|---:|---|
| n100 | 0 | 0 | 是 | 是 | 否 | 168 | true |
| n200 | 0 | 0 | 是 | 是 | 否 | 284 | true |
| n300 | 0 | 0 | 是 | 是 | 否 | 290 | true |

正文可写：

> 程序对输出布局逐一检查 block 名称完整性、block 边界约束、不重叠约束、面积守恒和 HPWL 复算一致性。三组芯片均无 block 越界、无 block 重叠，摆放面积与输入 block 总面积一致，重新计算的 HPWL 与结果表完全一致。terminal 不作为 hard-block 轮廓硬约束，其越界数量仅作为口径敏感性诊断。

完整验证文件为 `results/q3/q3_validation.json`。

## 11. 图表安排

### 11.1 主文图

建议至少放三张 Q3 布局图：

- 图 Q3-1：n100 在搜索首个可行死区率下的 hard-block 布局；
- 图 Q3-2：n200 在搜索首个可行死区率下的 hard-block 布局；
- 图 Q3-3：n300 在搜索首个可行死区率下的 hard-block 布局。

对应文件：

- `results/q3/figures/n100_q3_layout.png`
- `results/q3/figures/n200_q3_layout.png`
- `results/q3/figures/n300_q3_layout.png`

同目录下有 SVG 版本，更适合论文排版。

图注建议包含：

- 外黑框：搜索得到的 hard-block 正方形轮廓；
- 彩色矩形：hard blocks；
- 黑色点：`.pl` 固定 terminal，参与 HPWL；
- 淡红色框：HPWL 较大的若干 nets 的外接框；
- 说明 terminal 不作为 hard-block outline 的越界判据。

### 11.2 对比图

建议论文手另做两张柱状图或折线图：

1. Q2 与 Q3 的边长/死区率对比：展示从 \(\Gamma=0.15\) 压缩到约 0.056-0.074；
2. Q2 与 Q3 的 HPWL 对比：展示更紧布局导致 HPWL 上升。

数据直接来自 `results/q3/q3_summary.csv`。如果篇幅紧，两张图可以并排展示，但不要做容易误导的双轴图。

### 11.3 主文表

建议主文至少放四张表：

1. hard-block 下界分解表；
2. 第三问主结果表；
3. Q2/Q3 权衡对比表；
4. 可行性验证与 terminal 诊断表。

候选 HPWL 对照表可以放附录，正文只保留一句“候选对照见附表”。

## 12. 论文各章节该写什么

### 12.1 问题分析

重点写三件事：

1. 第三问的目标从固定死区率变为压缩死区率；
2. 正方形整数边长是第一层核心决策变量，HPWL 是第二层目标；
3. terminal 固定坐标参与 HPWL，但不改变 hard-block packing 的面积和不重叠约束。

段落骨架：

> 第三问要求在 fixed-outline floorplanning 约束下进一步压缩 hard-block 摆放区域。由于死区率 \(\Gamma\) 与正方形边长 \(S\) 单调对应，问题可转化为对整数边长 \(S\) 的搜索。同时，HPWL 仍是布图质量的重要指标，但若将死区率和 HPWL 简单加权，会引入无物理依据的权重。因此本文采用词典序策略：先搜索尽可能小的可构造边长，再在该边长下优化 HPWL。

### 12.2 模型假设

建议列 5 条，并说明作用：

| 假设 | 用途 | 影响 |
|---|---|---|
| hard block 尺寸固定，可旋转 90 度 | 定义旋转变量和几何约束 | 若不允许旋转，可行边长可能变大 |
| block pin 位于几何中心 | 计算 HPWL | 与题目缺少内部 pin 偏移数据相匹配 |
| terminal 坐标固定且不缩放 | 保持 `.pl` 连接端位置 | HPWL 端点固定 |
| terminal 不参与 hard-block outline 约束 | 与修正后题意口径一致 | 部分 terminal 可位于压缩 outline 外 |
| 死区率以 block 总面积为分母 | 与 fixed-outline 公式一致 | 整数边长导致 \(\Gamma(S)\) 为离散值 |

### 12.3 模型建立

建议结构：

1. 定义 \(A_{\mathrm{blocks}}\)、\(S\)、\(\Gamma(S)\)；
2. 写 block 边界、不重叠约束；
3. 写 hard-block 下界 \(S_{\mathrm{lb}}\)；
4. 写第一层目标 \(\min S\)；
5. 写第二层 HPWL 目标；
6. 单独说明 terminal 诊断边界不是正式约束。

不要先写算法再补公式。第三问的说服力来自“离散边长搜索 + 完整验证 + 边界口径清楚”。

### 12.4 模型求解

建议分为四小节：

1. `hard-block 下界计算`：面积、最大模块边两个下界；
2. `边长可行性搜索`：整数 \(S\) 枚举，MaxRects 构造 packing；
3. `搜索边长下 HPWL 优化`：复用 Q2 的解析线长松弛、合法化和局部改进；
4. `验证与输出`：写 CSV、图、JSON，复算约束和 HPWL。

### 12.5 结果与分析

先回答死区率，再分析 HPWL 代价。建议顺序：

1. 主结果表；
2. 搜索日志说明；
3. Q2/Q3 对比；
4. terminal 敏感性解释；
5. 三张布局图；
6. 候选对照与 refinement 说明。

可用解释语句：

> 三组芯片在当前确定性 packing 搜索预算下得到的首个可行边长分别为 439、432、537，对应死区率为 0.07364861、0.06219834、0.05563935。与第二问 \(\Gamma=0.15\) 的结果相比，轮廓压缩导致 HPWL 分别上升 8.75%、7.79%、14.31%，反映出面积压缩与线长优化之间的权衡。

### 12.6 验证与稳健性

建议写四层验证：

1. 几何验证：block 越界、block 重叠、面积守恒；
2. 目标验证：HPWL 用输出坐标复算一致；
3. 搜索验证：记录每个整数边长的 packing 构造结果；
4. 口径验证：terminal_outside_count 作为敏感性诊断，不改变 valid 判据。

若论文篇幅足够，可以补充 `refine_passes` 或 `refine_top` 的计算预算敏感性，但必须实际运行后再写，不要编造。

## 13. 结果证据分配

| 证据 | 功能 | 放置位置 |
|---|---|---|
| \(\Gamma(S)\) 公式 | 定义第三问目标 | 模型建立 |
| hard-block 下界 | 给出搜索起点 | 模型建立 |
| Q2 边长 | 给出已知可行上界 | 求解算法 |
| Q3 搜索日志 | 说明没有任意步长 | 结果或附录 |
| Q3 HPWL | 第二层结果 | 主结果表 |
| Q2/Q3 HPWL 差值 | 权衡解释 | 结果分析 |
| terminal 诊断表 | 解释队友修正和题意歧义 | 讨论或附录 |
| JSON 验证细节 | 可复现性 | 附录或代码说明 |
| block 坐标全表 | 输出交付 | 附录或结果文件说明 |

## 14. 不要写过头的话

不要写：

- “第三问死区率达到全局最小。”
- “第三问 HPWL 达到全局最优。”
- “小于 439/432/537 的边长都已被数学证明不可行。”
- “terminal 必须位于本题正式 Q3 轮廓内。”
- “terminal 坐标被移动或缩放。”
- “MaxRects 算法对任意边长都能判定可行性。”

推荐写：

- “在当前确定性 packing 搜索预算下，搜索得到的首个可行边长为……”
- “所有 hard blocks 均通过边界、重叠和面积守恒验证。”
- “terminal 只作为固定 HPWL pin，terminal_outside_count 作为口径敏感性诊断。”
- “相比 \(\Gamma=0.15\) 的第二问结果，第三问以 HPWL 上升为代价换取更小 hard-block outline。”
- “由于构造器不是完备判定器，本文不声称第一层目标全局最优。”

## 15. 边界情况与审稿风险

### 15.1 terminal 在正式 Q3 边界外

这是本轮修正后的正常情形，不构成布局 invalid。HPWL 仍使用 terminal 原始坐标复算。

### 15.2 如果评委要求 terminal inside

可以在讨论中写：

> 若采用 terminal 也必须位于轮廓内的替代解释，则三组芯片的边长至少需要达到 444、438、548。本研究将其作为敏感性边界保留，但正式模型按 terminal 只参与 HPWL 的解释计算。

不要把这三个边长和正式 Q3 主结果混在同一列里。

### 15.3 搜索失败的边长

当前搜索日志中，n100 的 424-438、n200 的 420-431、n300 的 523-536 均未找到可行 packing。论文中只能写“未找到”，不能写“不可行”。

### 15.4 如果不允许 block 旋转

当前可行构造依赖旋转选项。若题面解释为不可旋转，需要重新运行并重写结果。

### 15.5 线长和面积的矛盾

更小的 hard-block outline 会挤压模块位置自由度，因此 HPWL 增大并不表示算法失败，而是第一层目标优先级导致的合理代价。论文中应主动解释这个 trade-off。

## 16. 交付文件清单

代码：

- `src/q3_min_deadspace.py`
- `src/q2_fixed_outline_hpwl.py`：Q3 调用其中的数据读取、HPWL、验证和绘图函数。

主结果：

- `results/q3/q3_summary.csv`
- `results/q3/q3_feasibility_log.csv`
- `results/q3/q3_candidate_runs.csv`
- `results/q3/q3_validation.json`

坐标：

- `results/q3/layouts/n100_q3_layout.csv`
- `results/q3/layouts/n200_q3_layout.csv`
- `results/q3/layouts/n300_q3_layout.csv`

图：

- `results/q3/figures/n100_q3_layout.png`
- `results/q3/figures/n200_q3_layout.png`
- `results/q3/figures/n300_q3_layout.png`
- 同目录下有 SVG 版本。

## 17. 复现命令

在项目根目录运行：

```powershell
python src\q3_min_deadspace.py --output-dir results\q3 --refine-passes 2 --refine-top 3 --refine-method mixed
```

验证语法：

```powershell
python -m py_compile src\q2_fixed_outline_hpwl.py src\q3_min_deadspace.py
```

若只想快速检查某一个芯片：

```powershell
python src\q3_min_deadspace.py --chips n100 --output-dir results\q3_n100_check
```

## 18. 摘要可用句

第三问摘要建议这样写：

> 针对最小死区率问题，本文将 fixed-outline hard-block 布局压缩转化为整数正方形边长搜索。修正题意后，terminal 坐标仅作为 HPWL 的固定 pin，不作为 hard-block 轮廓约束。程序从 hard-block 面积和最大模块边长给出的下界出发逐个枚举边长，并结合 MaxRects 构造与 Q2 的目标引导合法化，在当前确定性搜索预算下得到 n100、n200、n300 的首个可行边长分别为 439、432、537，对应死区率分别为 0.07364861、0.06219834、0.05563935。在上述边长下进一步优化 HPWL，得到总 HPWL 分别为 239551.0、442024.0、640695.5；相对于 \(\Gamma=0.15\) 的第二问结果，HPWL 分别增加 8.75%、7.79%、14.31%。所有输出布局均通过 block 边界、重叠、面积守恒和 HPWL 复算验证，terminal 越出压缩轮廓的情况作为口径敏感性诊断单独报告。
