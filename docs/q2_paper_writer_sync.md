# 第二问论文手同步文档：固定正方形轮廓下的 HPWL 优化

> 任务状态：第二问已完成程序实现、三组芯片结果、布局图、候选对照表和可行性验证。  
> 主程序：`src/q2_fixed_outline_hpwl.py`  
> 主结果目录：`results/q2`

## 0. 写作总判断

第二问是一个固定轮廓 VLSI floorplanning 问题。它不是预测、评价或统计拟合，而是带几何硬约束的组合优化问题：

```text
输入：hard blocks 尺寸、netlist、terminal 固定坐标、dead_space_ratio=0.15
决策：每个 block 的左下角坐标与是否旋转
硬约束：所有 block 不重叠，且全部落在正方形芯片轮廓内
目标：最小化所有 nets 的 HPWL 总和
输出：每组芯片的布局坐标、总 HPWL、正方形边长、可视化和约束验证
```

论文中不能写“求得全局最优”。n100/n200/n300 均为大规模矩形非重叠布图，属于 NP-hard 组合优化。本文结果应表述为：

> 在固定死区率 0.15 的正方形轮廓下，本文算法得到并验证了高质量可行布局；这些布局给出当前搜索预算下的 HPWL 可行上界。

## 1. 术语表

论文中统一使用下列写法，不要混用：

| 术语 | 建议写法 | 说明 |
|---|---|---|
| 半周长线长 | HPWL, half-perimeter wirelength | 第一次出现写全称，之后用 HPWL |
| 硬模块 | hard block | `.blocks` 中的 block，尺寸固定，可旋转 |
| 外部终端 | terminal | `.pl` 给定固定坐标，不参与面积与重叠 |
| 固定轮廓 | fixed square outline | 第二问芯片为正方形 |
| 死区率 | dead-space ratio | 本文采用 `Gamma=(A_outline-A_blocks)/A_blocks` |
| 解析线长松弛 | quadratic wirelength relaxation | 用来得到 block 的目标中心 |
| 合法化 | legalisation | 将连续目标位置转为无重叠、在边界内的矩形布局 |
| 断点局部改进 | HPWL-breakpoint refinement | 大规模实例使用的快速局部搜索 |

## 2. 数据口径与边界

### 2.1 输入文件

| 芯片 | hard blocks | terminals | nets | pins | 用到的文件 |
|---|---:|---:|---:|---:|---|
| n100 | 100 | 334 | 885 | 1873 | `n100.blocks/.nets/.pl` |
| n200 | 200 | 564 | 1585 | 3599 | `n200.blocks/.nets/.pl` |
| n300 | 300 | 569 | 1893 | 4358 | `n300.blocks/.nets/.pl` |

### 2.2 Terminal 坐标处理

`.pl` 中 terminal 坐标被视为题目给定的固定外部连接端位置，程序不缩放 terminal 坐标。原因：

1. 题面给出 `.pl` 的作用是提供 terminal 坐标；
2. 第二问改变的是 block 可摆放的正方形轮廓大小；
3. 擅自缩放 terminal 会改变 netlist 的物理连接边界，属于额外假设。

需要在论文“数据预处理”中注明：terminal 只参与 HPWL，不参与模块面积、不参与重叠约束。

## 3. 固定轮廓面积公式

本文沿用题干理解文档和英文论文 fixed-outline 公式的死区率口径：

\[
\Gamma=\frac{A_{\mathrm{outline}}-A_{\mathrm{blocks}}}{A_{\mathrm{blocks}}},
\qquad
A_{\mathrm{outline}}\ge (1+\Gamma)A_{\mathrm{blocks}} .
\]

第二问固定为正方形，因此：

\[
L=\left\lceil \sqrt{(1+\Gamma)A_{\mathrm{blocks}}}\right\rceil,
\qquad
A_{\mathrm{outline}}=L^2 .
\]

由于边长取整数上取整，实际死区率会略大于 0.15。结果如下：

| 芯片 | 模块总面积 \(A_{\mathrm{blocks}}\) | 边长 \(L\) | 轮廓面积 \(L^2\) | 实际死区率 |
|---|---:|---:|---:|---:|
| n100 | 179501 | 455 | 207025 | 0.15333619 |
| n200 | 175696 | 450 | 202500 | 0.15255897 |
| n300 | 273170 | 561 | 314721 | 0.15210675 |

这里不要写“实际死区率等于 0.15”，应写“按 0.15 设定并取整数边长后，实际死区率分别为……”

## 4. 数学模型

### 4.1 决策变量

对第 \(i\) 个 block：

- \(r_i\in\{0,1\}\)：旋转变量，\(r_i=1\) 表示旋转 90 度；
- \((x_i,y_i)\)：旋转后矩形左下角坐标；
- 旋转后宽高为 \((w_i(r_i),h_i(r_i))\)。

block 的 pin 位于几何中心：

\[
c_i=(x_i+\frac{w_i(r_i)}{2},\; y_i+\frac{h_i(r_i)}{2}).
\]

terminal \(p\) 的坐标 \((X_p,Y_p)\) 由 `.pl` 给定。

### 4.2 不越界约束

\[
0\le x_i,\quad 0\le y_i,\quad
x_i+w_i(r_i)\le L,\quad y_i+h_i(r_i)\le L.
\]

### 4.3 不重叠约束

任意两个不同模块 \(i,j\) 必须满足至少一个方向分离：

\[
x_i+w_i(r_i)\le x_j
\;\vee\;
x_j+w_j(r_j)\le x_i
\;\vee\;
y_i+h_i(r_i)\le y_j
\;\vee\;
y_j+h_j(r_j)\le y_i .
\]

写作时提醒论文手：这是析取约束，直接精确求解会引入 0-1 变量和 Big-M，规模到 n300 后很难在竞赛时间内求全局最优，因此采用结构化启发式。

### 4.4 HPWL 目标函数

设 net \(e\) 的 pin 坐标集合为 \(\mathcal{P}_e\)，其中 block pin 用模块中心 \(c_i\)，terminal pin 用固定坐标。该 net 的 HPWL 为：

\[
\operatorname{HPWL}(e)=
\max_{p\in\mathcal{P}_e} X_p-\min_{p\in\mathcal{P}_e} X_p+
\max_{p\in\mathcal{P}_e} Y_p-\min_{p\in\mathcal{P}_e} Y_p .
\]

第二问目标为：

\[
\min \sum_{e\in E}\operatorname{HPWL}(e)
\]

subject to 上述边界约束和不重叠约束。

## 5. 候选模型比较

这一段建议放在“问题分析”或“模型选择”中。

| 方案 | 思路 | 优点 | 风险 | 本文处理 |
|---|---|---|---|---|
| A：MILP 精确模型 | 用 Big-M 表达不重叠，直接最小化 HPWL | 有理论全局最优框架 | 变量和析取约束约 \(O(n^2)\)，n300 很难求解 | 只作为理论基准，不作为主求解器 |
| B：B*-tree + Fast-SA | 论文中的 fixed-outline floorplanning 框架 | 搜索表达紧凑，适合固定轮廓 | 实现与调参成本较高，参数不能照搬 | 迁移“轮廓可行性 + HPWL 搜索”的思想 |
| C：解析线长松弛 + 合法化 + 局部改进 | 先求连续目标位置，再几何合法化 | 不用空间网格步长，复现稳定，能直接输出可行解 | 不能证明全局最优 | 作为第二问主方法 |

英文论文可迁移内容：

- fixed-outline 尺寸公式；
- 每个候选布局都要快速 packing 并显式检查边界；
- 不能只用固定罚项，应把“找可行解”和“优化线长”分开处理；
- 对大规模 floorplanning 只能谨慎称为高质量可行解。

英文论文不可直接迁移内容：

- bus-driven floorplanning 的 dummy block 不是本题 HPWL nets；
- 论文中的 SA 参数不能作为本题无依据常数照搬；
- 论文表格里的 wirelength 数值不能作为本题答案。

## 6. 求解算法

建议在“模型求解”中按下列 5 个模块写。

### 6.1 模块一：解析线长松弛

为了让合法化有物理方向，先忽略不重叠约束，把 HPWL 用二次线长近似。对每条 degree 为 \(d_e\) 的 net，将其 pin 两两连成 clique，权重取：

\[
\omega_e=\frac{1}{d_e-1}.
\]

求解 block 中心目标：

\[
\min_{\{z_i\}}
\sum_{e\in E}\sum_{\substack{u<v\\u,v\in e}}
\omega_e\|z_u-z_v\|_2^2 ,
\]

其中 terminal 的 \(z_p=(X_p,Y_p)\) 固定。该式形成图 Laplacian 线性方程，程序用 `numpy.linalg.solve` 求解；若遇到数值奇异，则用极小正则化的最小二乘作为数值稳定回退。输出是每个 block 的目标中心 \(\hat c_i\)。

论文中强调：这个松弛解不是最终布局，只用于给启发式提供“往哪儿靠”的目标。

### 6.2 模块二：目标引导合法化

主合法化器使用 MaxRects 思想维护当前空矩形集合。每插入一个 block 时，候选坐标来自：

- 当前空矩形的边界和中心；
- 解析目标中心 \(\hat c_i\)；
- 已放置相邻 net pin 和 terminal 的坐标；
- 这些 pin 坐标的中位数；
- floor/ceil 到整数坐标。

这点很重要：程序没有用人为网格步长扫描平面。坐标候选来自 HPWL 分段线性目标的断点和当前几何空矩形。

插入候选按三种模式比较：

- `wire`：优先降低已知局部 HPWL；
- `target`：优先靠近解析目标中心；
- `fit`：优先减少空矩形碎片。

### 6.3 模块三：可行初值族

程序生成多种确定性初值，而不是只跑一次：

- `degree_area`：高连线权重、大面积模块优先；
- `area_degree`：大面积模块优先；
- `target_xy` / `target_yx`：按解析目标坐标排序；
- `max_side`：大边长模块优先；
- `serpentine_x/y`：按目标位置蛇形排序；
- `shelf_bfd`：Best-Fit-Decreasing 行带基线。

写作时可将其表述为“多初值候选池”，不是随机种子。

### 6.4 模块四：局部 HPWL 改进

对初始 HPWL 最小的前 3 个候选布局进行局部改进。这里的“3”是计算预算，不是几何步长；候选坐标仍然由 HPWL 断点和空矩形/边界产生。

两类 refinement：

| 适用规模 | refinement | 说明 |
|---|---|---|
| n100 | `exact_maxrect_reinsert` | 移除一个 block，重建可行空矩形，用精确 HPWL 贡献选择重插位置 |
| n200/n300 | `fast_hpwl_breakpoint` | 枚举 HPWL 断点候选坐标并检查非重叠，速度更适合大规模 |

论文可写为：小规模实例使用更强局部重插入，大规模实例使用断点局部搜索以保证可复现时间。

### 6.5 模块五：可行性和 HPWL 复算验证

每个输出布局都做以下检查：

1. block 名称无重复、无缺失；
2. 所有 block 坐标非负且不超过 \(L\)；
3. 任意两个 block 不重叠；
4. 摆放面积之和等于 `.blocks` 总面积；
5. 用输出坐标重新计算 HPWL，与 summary 中 HPWL 一致。

验证结果保存在 `results/q2/q2_validation.json`。

## 7. 第二问主结果

主结果表可直接放在论文“结果与分析”：

| 芯片 | 边长 L | 实际死区率 | 总 HPWL | 初值 HPWL | refinement 后改善 | 主方法 | 局部改进 | 运行时间/s |
|---|---:|---:|---:|---:|---:|---|---|---:|
| n100 | 455 | 0.15333619 | 222139.5 | 225147.0 | 1.335794% | maxrects:degree_area+wire | exact_maxrect_reinsert | 52.71 |
| n200 | 450 | 0.15255897 | 409845.0 | 411409.0 | 0.380157% | maxrects:target_yx+wire | fast_hpwl_breakpoint | 62.70 |
| n300 | 561 | 0.15210675 | 565977.5 | 571290.0 | 0.929913% | maxrects:target_xy+wire | fast_hpwl_breakpoint | 120.55 |

注意 HPWL 可能出现 `.5`，因为 block 中心坐标含半整数。

## 8. 候选对照与消融证据

这张表建议放在“算法有效性分析”或附录中，证明不是只报告一次运行。

| 芯片 | 候选方法 | 初值 HPWL | refinement 后 HPWL | 接受移动数 | refinement |
|---|---|---:|---:|---:|---|
| n100 | maxrects:degree_area+wire | 225147.0 | 222139.5 | 44 | exact_maxrect_reinsert |
| n100 | maxrects:area_degree+wire | 225879.5 | 224419.0 | 35 | exact_maxrect_reinsert |
| n100 | maxrects:area_degree+target | 242157.5 | 234921.5 | 34 | exact_maxrect_reinsert |
| n200 | maxrects:target_yx+wire | 411409.0 | 409845.0 | 22 | fast_hpwl_breakpoint |
| n200 | maxrects:degree_area+wire | 413289.0 | 412680.5 | 27 | fast_hpwl_breakpoint |
| n200 | maxrects:area_degree+wire | 419002.0 | 417138.5 | 44 | fast_hpwl_breakpoint |
| n300 | maxrects:target_xy+wire | 571290.0 | 565977.5 | 38 | fast_hpwl_breakpoint |
| n300 | maxrects:target_yx+wire | 581871.5 | 574935.5 | 60 | fast_hpwl_breakpoint |
| n300 | maxrects:degree_area+wire | 600378.5 | 599882.0 | 32 | fast_hpwl_breakpoint |

可解释结论：

- `wire` 模式在三组主结果中均优于 `target/fit`，说明 HPWL 局部信息比单纯靠近解析目标更直接；
- 解析目标排序在 n200/n300 中成为最优初值，说明随着规模增大，线长松弛对全局方向更有帮助；
- refinement 均降低 HPWL，但幅度有限，说明初始合法化质量对最终结果影响较大。

## 9. 验证表

论文建议给一个简化验证表：

| 芯片 | 越界数 | 重叠数 | 面积守恒 | HPWL 复算一致 | valid |
|---|---:|---:|---|---|---|
| n100 | 0 | 0 | 是 | 是 | true |
| n200 | 0 | 0 | 是 | 是 | true |
| n300 | 0 | 0 | 是 | 是 | true |

正文写法建议：

> 对每个输出布局，程序逐一检查模块是否越界、任意两个模块是否重叠，并将所有模块面积累加后与输入总面积比较；同时用输出坐标重新计算 HPWL。三组数据均通过上述验证。

## 10. 图表安排

### 主文图

建议放三张布局图，标题写成：

- 图 1：n100 在死区率 0.15 下的固定正方形 HPWL 布局
- 图 2：n200 在死区率 0.15 下的固定正方形 HPWL 布局
- 图 3：n300 在死区率 0.15 下的固定正方形 HPWL 布局

对应文件：

- `results/q2/figures/n100_q2_layout.png`
- `results/q2/figures/n200_q2_layout.png`
- `results/q2/figures/n300_q2_layout.png`

图注说明：

- 黑色点：`.pl` 给定 terminal；
- 彩色矩形：hard blocks；
- 淡红色框：HPWL 最大的若干 nets 的外接框，用于展示线长压力；
- 外黑框：固定正方形芯片轮廓。

### 主文表

建议至少放四张表：

1. 数据规模与固定轮廓参数表；
2. 第二问主结果表；
3. 候选方法对照表；
4. 可行性验证表。

候选方法对照表如果正文篇幅不够，可放附录，但主文至少保留一句“候选对照见附表”。

## 11. 论文各章节该写什么

### 问题分析

写清楚：

- 第二问和第一问不同，面积不再是目标，而是由死区率固定轮廓；
- 连接关系通过 nets 进入 HPWL；
- terminal 坐标固定，block pin 在中心；
- 核心难点是“不重叠 + 固定边界 + HPWL 最小化”同时存在。

建议段落骨架：

> 第二问在固定正方形芯片轮廓内优化互连线长。与第一问不同，芯片面积由模块总面积和死区率直接确定，布局评价不再是外接面积，而是所有 net 的 HPWL 总和。因此需要在满足不越界和不重叠的前提下，使连接关系紧密的模块尽量靠近对应 terminal 或其他模块。

### 模型假设

可写 4 条：

1. hard block 尺寸固定，允许 90 度旋转；
2. block pin 位于模块几何中心；
3. terminal 坐标由 `.pl` 固定，不随轮廓上取整缩放；
4. dead-space ratio 以模块总面积为分母。

每条后面说明用途。不要写“忽略所有布线拥塞”，因为题目本来只要求 HPWL，不应把未建模内容写成现实假设。

### 符号说明

至少包括：

\[
i,j:\text{模块索引};\quad e:\text{net 索引};\quad
L:\text{正方形边长};\quad \Gamma:\text{死区率};
\]

\[
x_i,y_i,r_i,w_i(r_i),h_i(r_i),c_i,\mathcal{P}_e,\operatorname{HPWL}(e).
\]

### 模型建立

按本文第 4 节公式写即可。注意先写约束，再写目标；因为 HPWL 优化必须建立在可行布局上。

### 模型求解

建议用一个算法流程图。流程图节点：

```text
读取 blocks/nets/pl
-> 计算 A_blocks 和 L
-> 构建 net-block-terminal 图
-> 解二次线长松弛，得到目标中心
-> 多初值合法化
-> 选 top-3 候选局部改进
-> 计算 HPWL
-> 可行性验证
-> 输出 CSV 和布局图
```

伪代码建议：

```text
Algorithm Q2 Fixed-outline HPWL Floorplanning
Input: blocks, nets, terminal coordinates, Gamma=0.15
Output: feasible placements and total HPWL
1. Compute L=ceil(sqrt((1+Gamma) * total block area)).
2. Build a weighted clique model for every net and solve the quadratic wirelength relaxation.
3. Generate deterministic placement orders from degree, area and relaxed target coordinates.
4. For each order and placement mode, legalise blocks inside the L by L square.
5. Sort feasible candidates by HPWL and refine the best three candidates.
6. Select the feasible layout with the smallest recomputed HPWL.
7. Verify boundary, non-overlap, area conservation and HPWL consistency.
```

### 结果与分析

先放主结果表，再放图。文字不要复述每个 block 坐标，重点解释：

- 三组都满足固定轮廓；
- HPWL 随 net/pin 数和模块规模增大而增大；
- n100 使用 exact 重插入得到更低 HPWL；
- n200/n300 使用 fast 断点 refinement 在合理时间内获得可行优化结果。

### 验证与稳健性

可写三层：

1. 内部正确性：越界、重叠、面积、HPWL 复算；
2. 候选对照：多种构造顺序和合法化模式；
3. 局部改进消融：初值 HPWL 与 refinement 后 HPWL 对比。

如果论文篇幅允许，可补充“增加 refine_top 或 refine_passes 的敏感性实验”。但现阶段不要编造未运行结果。

## 12. 不要写过头的话

不要写：

- “本文求得全局最优解。”
- “死区率严格等于 0.15。”
- “terminal 被缩放到新边界。”
- “B*-tree/Fast-SA 完全复现了英文论文算法。”
- “该算法一定优于所有其他方法。”

推荐写：

- “得到经完整约束校验的可行布局。”
- “实际死区率因整数边长上取整略高于 0.15。”
- “算法借鉴 fixed-outline floorplanning 的思想，但针对本题 HPWL 目标进行了解析松弛和合法化改造。”
- “在当前候选池和局部搜索预算下取得的最小 HPWL 为……”

## 13. 交付文件清单

代码：

- `src/q2_fixed_outline_hpwl.py`
- `requirements.txt`

主结果：

- `results/q2/q2_summary.csv`
- `results/q2/q2_candidate_runs.csv`
- `results/q2/q2_validation.json`

坐标：

- `results/q2/layouts/n100_q2_layout.csv`
- `results/q2/layouts/n200_q2_layout.csv`
- `results/q2/layouts/n300_q2_layout.csv`

图：

- `results/q2/figures/n100_q2_layout.png`
- `results/q2/figures/n200_q2_layout.png`
- `results/q2/figures/n300_q2_layout.png`
- 同目录下还有 SVG 版本，可用于论文排版。

## 14. 复现命令

在项目根目录运行：

```powershell
python src\q2_fixed_outline_hpwl.py --output-dir results\q2 --refine-passes 2 --refine-top 3 --refine-method mixed
```

验证语法：

```powershell
python -m py_compile src\q2_fixed_outline_hpwl.py
```

若机器时间紧，可先跑某一个芯片：

```powershell
python src\q2_fixed_outline_hpwl.py --chips n100 --output-dir results\q2_n100_check
```

## 15. 后续接第三问的接口

第三问会搜索最小可行死区率。第二问已经提供了可复用接口：

- `--deadspace-ratio` 可改成任意候选 \(\Gamma\)；
- 程序会自动计算对应 \(L\)；
- `q2_validation.json` 可作为“该 \(\Gamma\) 下是否找到可行布局”的判据；
- 但第三问不能把“单次失败”写成“不可行”，需要外层二分或枚举、多初值、多预算验证。

