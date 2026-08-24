# 第三问论文手同步文档：最小可行死区率与对应 HPWL 布图

> 任务状态：第三问已完成程序实现、三组芯片最小死区率搜索、最小边长下 HPWL 更新、布局图、搜索日志、候选对照表和完整可行性验证。<br>
> 主程序：`src/q3_min_deadspace.py`<br>
> 主结果目录：`results/q3`

## 0. 一句话主张

第三问在第二问 fixed square outline 的基础上，把死区率从给定值变成待优化目标。本文采用词典序优化：

```text
第一层目标：在硬模块不重叠、均位于正方形轮廓内，且 terminal 固定坐标也位于轮廓内的条件下，最小化正方形边长 L，也即最小化死区率 Gamma(L)。
第二层目标：在已证明的最小边长 L* 下，尽量降低总 HPWL。
```

在本文的 terminal 坐标解释下，三组芯片均在理论下界边长处构造出可行布局。因此第三问对“最小可行死区率”可以写成已全局确定；但对“最小边长下的 HPWL”只能写成当前算法预算下得到的高质量可行解，不能写成 HPWL 全局最优。

## 1. 术语表

全文统一下列术语，避免前后叫法漂移：

| 术语 | 建议写法 | 说明 |
|---|---|---|
| 死区率 | dead-space ratio, \(\Gamma\) | \(\Gamma=(A_{\mathrm{outline}}-A_{\mathrm{blocks}})/A_{\mathrm{blocks}}\) |
| 最小可行边长 | minimum feasible side length, \(L^*\) | 第三问第一层目标 |
| 理论下界边长 | theoretical lower bound, \(L_{\mathrm{lb}}\) | 由面积、最大模块边、terminal 坐标共同给出 |
| 固定正方形轮廓 | fixed square outline | block 必须位于 \([0,L]\times[0,L]\) |
| 固定外部终端 | fixed terminal | `.pl` 给定，坐标不缩放 |
| 构造可行性证明 | constructive feasibility certificate | 在 \(L_{\mathrm{lb}}\) 上给出无重叠布局 |
| 半周长线长 | HPWL, half-perimeter wirelength | 第一次出现写全称，之后写 HPWL |
| 词典序优化 | lexicographic optimization | 先优化 \(\Gamma\)，再在该 \(\Gamma\) 下优化 HPWL |

## 2. 题意拆解与依赖关系

第三问依赖第二问，但不是简单重复第二问。第二问给定 \(\Gamma=0.15\)，目标是在对应正方形边长内优化 HPWL；第三问则需要回答“死区率还能压到多小”，因此必须在外层搜索正方形边长。

| 子任务 | 输入 | 输出 | 与前问关系 | 成功判据 |
|---|---|---|---|---|
| Q3a 最小死区率 | hard blocks、terminal 坐标、netlist | \(L^*\)、\(\Gamma^*\) | 复用 Q2 的几何约束和死区率公式 | 证明任何更小 \(L\) 不可行，并在 \(L^*\) 构造可行布局 |
| Q3b 最小边长下线长 | \(L^*\)、Q2 HPWL 求解器 | \(L^*\) 下的布局和 HPWL | 复用 Q2 的解析松弛、合法化与 refinement | 布局无越界、无重叠，HPWL 复算一致 |
| Q3c 对 Q2 的代价分析 | Q2 与 Q3 summary | HPWL 增量、边长压缩、死区率压缩 | 解释面积压缩和线长变差的权衡 | 同一数据口径、同一 HPWL 定义 |

论文中建议把第三问写成：

```text
Q2 提供一个已知可行上界 L_0.15；
Q3 先从理论下界 L_lb 到 L_0.15 做整数边长可行性搜索；
若 L_lb 已可行，则 L*=L_lb，不需要再尝试任何更小边长；
最后在 L* 固定后优化 HPWL，并与 Q2 的 HPWL 做对比。
```

## 3. 关键建模边界

### 3.1 Terminal 坐标不缩放且必须位于轮廓内

本文沿用第二问的数据解释：`.pl` 中 terminal 坐标是固定外部连接端位置，不随芯片边长变化而缩放。第三问进一步采用如下硬约束：

\[
0\le X_t\le L,\qquad 0\le Y_t\le L,\qquad \forall t\in T.
\]

这是第三问能证明最小边长的关键。原因是三组数据中 terminal 坐标的最大值分别大于仅由面积给出的下界，所以 terminal 坐标成为主导下界。

必须在论文里说明：

- terminal 不参与模块面积和不重叠约束；
- terminal 参与 HPWL；
- terminal 坐标必须落在正方形轮廓内；
- 若另一种题意解释允许 terminal 位于芯片轮廓外，则本问的下界和最小死区率会改变，本文结果只适用于 fixed terminal inside-outline 的解释。

### 3.2 边长按整数处理

附件中的 block 尺寸和布局坐标按整数网格输出；程序按整数边长 \(L\) 搜索。死区率不是按任意小数步长扫描，而是由整数 \(L\) 唯一决定：

\[
\Gamma(L)=\frac{L^2-A_{\mathrm{blocks}}}{A_{\mathrm{blocks}}}.
\]

因此第三问不设置人为的 \(\Gamma\) 步长，也不使用“每次降低 0.01”这类没有依据的搜索常数。

### 3.3 旋转假设

hard block 允许旋转 90 度。若论文前文已经在 Q1/Q2 假设中写过，此处可简要引用；若未写，需要在第三问模型假设中补上：

\[
(w_i(r_i),h_i(r_i))=
\begin{cases}
(w_i,h_i), & r_i=0,\\
(h_i,w_i), & r_i=1.
\end{cases}
\]

## 4. 数学模型

### 4.1 输入集合和参数

- \(B=\{1,\ldots,n\}\)：hard block 集合；
- \(T\)：terminal 集合；
- \(E\)：net 集合；
- \(w_i,h_i\)：block \(i\) 的原始宽高；
- \(A_{\mathrm{blocks}}=\sum_i w_i h_i\)：所有 block 面积之和；
- \((X_t,Y_t)\)：terminal \(t\) 的固定坐标；
- \(L\)：正方形芯片边长。

### 4.2 决策变量

对每个 block \(i\)：

\[
x_i,y_i\in \mathbb{Z}_{\ge 0},\qquad r_i\in\{0,1\}.
\]

其中 \((x_i,y_i)\) 为 block 左下角坐标，\(r_i\) 为旋转变量。block pin 使用几何中心：

\[
c_i=\left(x_i+\frac{w_i(r_i)}{2},\ y_i+\frac{h_i(r_i)}{2}\right).
\]

### 4.3 硬约束

边界约束：

\[
0\le x_i,\quad 0\le y_i,\quad
x_i+w_i(r_i)\le L,\quad
y_i+h_i(r_i)\le L,\qquad \forall i\in B.
\]

不重叠约束：

\[
x_i+w_i(r_i)\le x_j
\;\vee\;
x_j+w_j(r_j)\le x_i
\;\vee\;
y_i+h_i(r_i)\le y_j
\;\vee\;
y_j+h_j(r_j)\le y_i,\qquad \forall i<j.
\]

terminal 边界约束：

\[
0\le X_t\le L,\qquad 0\le Y_t\le L,\qquad \forall t\in T.
\]

### 4.4 第一层目标：最小死区率

因为 \(A_{\mathrm{blocks}}\) 固定，最小化 \(\Gamma(L)\) 等价于最小化 \(L\)：

\[
\min L,
\qquad
\Gamma(L)=\frac{L^2-A_{\mathrm{blocks}}}{A_{\mathrm{blocks}}}.
\]

### 4.5 第二层目标：最小边长下 HPWL

在 \(L=L^*\) 固定后，令 net \(e\) 的所有 pin 坐标集合为 \(\mathcal{P}_e\)，则：

\[
\operatorname{HPWL}(e)=
\max_{p\in\mathcal{P}_e} X_p-\min_{p\in\mathcal{P}_e} X_p+
\max_{p\in\mathcal{P}_e} Y_p-\min_{p\in\mathcal{P}_e} Y_p.
\]

第二层目标为：

\[
\min \sum_{e\in E}\operatorname{HPWL}(e),
\qquad \text{s.t. } L=L^* \text{ and all geometric constraints hold.}
\]

这部分是 NP-hard fixed-outline floorplanning 中的线长优化，本文只称“得到当前候选池和 refinement 预算下的最小 HPWL”，不要写“证明 HPWL 最优”。

## 5. 理论下界与全局最小死区率证明

第三问最重要的论文亮点是：不靠试错步长，而是先给出 \(L\) 的理论下界。

任何可行正方形边长 \(L\) 必须同时满足三类必要条件：

### 5.1 面积下界

所有 block 互不重叠并放入正方形内，因此：

\[
L^2\ge A_{\mathrm{blocks}},
\qquad
L\ge \left\lceil \sqrt{A_{\mathrm{blocks}}}\right\rceil.
\]

### 5.2 最大模块边长下界

任意 block 无论是否旋转，其较长边必须能被正方形容纳：

\[
L\ge \max_i \max(w_i,h_i).
\]

### 5.3 Terminal 坐标下界

在 fixed terminal inside-outline 的解释下：

\[
L\ge \left\lceil \max_{t\in T}\{\max(X_t,Y_t)\}\right\rceil.
\]

### 5.4 合并下界

因此：

\[
L_{\mathrm{lb}}=
\max\left\{
\left\lceil \sqrt{A_{\mathrm{blocks}}}\right\rceil,\,
\max_i \max(w_i,h_i),\,
\left\lceil \max_{t\in T}\max(X_t,Y_t)\right\rceil
\right\}.
\]

若在 \(L_{\mathrm{lb}}\) 上构造出满足全部硬约束的布局，则：

\[
L^*=L_{\mathrm{lb}},
\qquad
\Gamma^*=\frac{L_{\mathrm{lb}}^2-A_{\mathrm{blocks}}}{A_{\mathrm{blocks}}}.
\]

这是一个“下界 + 构造”的证明结构。论文可以写：

> 由于任何小于 \(L_{\mathrm{lb}}\) 的边长至少违反面积、模块尺寸或 terminal 坐标三类必要条件之一，而本文在 \(L_{\mathrm{lb}}\) 上构造出通过重叠、边界和 terminal 校验的布局，因此 \(L_{\mathrm{lb}}\) 即为第三问第一层目标的全局最优边长。

## 6. 候选方案比较

建议放在“模型选择”或“问题分析”中。

| 方案 | 思路 | 优点 | 风险 | 本文取舍 |
|---|---|---|---|---|
| A：MILP 精确模型 | 用 0-1 变量表达每对 block 的相对方向，用 Big-M 处理析取约束 | 理论上可给最优性 gap | \(O(n^2)\) 相对位置变量和约束，n300 规模下求解风险高 | 作为理论模型说明，不作为主求解器 |
| B：整数边长搜索 + packing 可行性构造 | 从 \(L_{\mathrm{lb}}\) 到 Q2 可行边长逐一检验 | 不需要任意 \(\Gamma\) 步长；若下界可行，可直接证明最小死区率 | 可行性构造器不保证在任意边长上完备 | 作为第三问第一层目标主方法 |
| C：B*-tree / Fast-SA / 遗传算法 | 在固定轮廓下搜索布局结构 | 适合 VLSI floorplanning 传统表达 | 参数较多，随机性强；对“最小死区率证明”帮助有限 | 可作为扩展，不用于主结论 |
| D：Q2 解析松弛 + 合法化 + 局部改进 | 在给定 \(L\) 下优化 HPWL | 复用 Q2 代码，结果可复现 | 不证明 HPWL 全局最优 | 作为第二层 HPWL 更新方法 |

写作要点：第三问的创新不在于“用了很多算法”，而在于把第一层可证的最小边长与第二层启发式线长优化分开。

## 7. 求解算法

### 7.1 总流程

建议论文配一个算法流程图，节点如下：

```text
读取 blocks / nets / pl
-> 计算 A_blocks、最大模块边、最大 terminal 坐标
-> 得到理论下界 L_lb
-> 读取 Q2 的 Gamma=0.15 可行边长作为搜索上界
-> 从 L_lb 开始做整数边长可行性搜索
-> 若某个 L 可行，则得到最小可行边长 L*
-> 在 L* 下调用 Q2 的 HPWL 求解器
-> 输出布局、HPWL、Gamma*、验证报告和图
```

### 7.2 外层搜索为什么不用二分或小数步长

\(\Gamma(L)\) 随整数 \(L\) 单调增加；真正的离散决策是边长 \(L\)，不是小数死区率。因此本文直接在整数边长上搜索：

\[
L=L_{\mathrm{lb}},L_{\mathrm{lb}}+1,\ldots,L_{0.15}.
\]

其中 \(L_{0.15}\) 是第二问在 \(\Gamma=0.15\) 下得到的可行边长。因为本次三组芯片都在 \(L_{\mathrm{lb}}\) 上立即可行，所以搜索日志每组只有一个 tested side。

### 7.3 可行性构造器

第一层只需要证明“存在一个可行 packing”，不需要该 packing 的 HPWL 最优。因此程序使用 `rectpack` 的 MaxRects 变体快速构造可行布局：

```text
MaxRectsBssf / MaxRectsBaf / MaxRectsBlsf
× SORT_AREA / SORT_LSIDE / SORT_SSIDE / SORT_RATIO
```

一旦某个组合在候选边长 \(L\) 内成功放入全部 block，程序记录该边长可行，并保存 search log。

### 7.4 最小边长下的 HPWL 更新

确定 \(L^*\) 后，程序重新调用第二问的目标引导求解器。该求解器包含：

1. quadratic wirelength relaxation：得到 block 的目标中心；
2. 多种确定性初值：degree/area/target/shelf 等；
3. fixed-outline legalisation：保证 block 不重叠且在边界内；
4. fast HPWL-breakpoint refinement：在 HPWL 分段断点与可行空隙中做局部改进；
5. 复算 HPWL 与可行性验证。

本次正式运行命令为：

```powershell
python src\q3_min_deadspace.py --output-dir results\q3 --refine-passes 2 --refine-top 3 --refine-method fast
```

### 7.5 伪代码

论文可直接放如下伪代码：

```text
Algorithm Q3 Minimum-Deadspace Fixed-outline Floorplanning
Input: hard blocks, nets, fixed terminal coordinates, Q2 feasible side L_0.15
Output: minimum feasible dead-space ratio Gamma*, placement at L*, HPWL

1. Compute total block area A_blocks.
2. Compute lower bounds:
      L_area = ceil(sqrt(A_blocks)),
      L_block = max_i max(w_i, h_i),
      L_terminal = ceil(max_t max(X_t, Y_t)).
3. Set L_lb = max(L_area, L_block, L_terminal).
4. For L from L_lb to L_0.15:
      4.1 Try deterministic MaxRects packing variants with rotation.
      4.2 If all blocks are placed without overlap inside the L by L square,
          set L* = L and stop.
5. Compute Gamma* = (L*^2 - A_blocks) / A_blocks.
6. Fix L = L* and run the Q2 HPWL optimiser.
7. Recompute HPWL from the output coordinates.
8. Verify missing/duplicate blocks, boundary, overlap, area conservation,
   terminal boundary and HPWL consistency.
```

## 8. 第三问主结果

这张表建议放在“结果与分析”的主文中。

| 芯片 | \(A_{\mathrm{blocks}}\) | 面积下界 | 最大模块边下界 | terminal 下界 | \(L^*\) | \(\Gamma^*\) | Q2 边长 | Q2 HPWL | Q3 HPWL | HPWL 增量 | 增量比例 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| n100 | 179501 | 424 | 67 | 444 | 444 | 0.09824458 | 455 | 222139.5 | 235824.5 | 13685.0 | 6.160543% |
| n200 | 175696 | 420 | 48 | 438 | 438 | 0.09190875 | 450 | 409845.0 | 433383.0 | 23538.0 | 5.743147% |
| n300 | 273170 | 523 | 48 | 548 | 548 | 0.09933009 | 561 | 565977.5 | 613636.5 | 47659.0 | 8.420653% |

正文解释建议：

- n100/n200/n300 的 terminal 下界均大于面积下界，因此最小边长由 terminal 固定坐标主导；
- 三组芯片都在 \(L_{\mathrm{lb}}\) 上构造出可行 packing，所以 \(\Gamma^*\) 是第一层目标的全局最小值；
- 相比 Q2 的 \(\Gamma=0.15\)，第三问显著压缩了芯片轮廓，但 HPWL 分别增加约 6.16%、5.74%、8.42%，说明面积压缩带来了线长代价；
- HPWL 绝对值随 nets、pins 和 block 数量增加而上升，不能直接跨芯片比较“哪个布局更好”，应主要看同一芯片 Q2/Q3 对比。

## 9. 搜索日志与下界达成证据

这张表建议放在“最小边长证明”段落后，或作为附表：

| 芯片 | tested side | \(L_{\mathrm{lb}}\) | \(\Gamma(L)\) | 是否可行 | 构造方法 | 搜索时间/s |
|---|---:|---:|---:|---|---|---:|
| n100 | 444 | 444 | 0.0982445780 | 是 | rectpack:MaxRectsBssf:SORT_AREA | 0.0239 |
| n200 | 438 | 438 | 0.0919087515 | 是 | rectpack:MaxRectsBssf:SORT_AREA | 0.1635 |
| n300 | 548 | 548 | 0.0993300875 | 是 | rectpack:MaxRectsBssf:SORT_AREA | 0.5850 |

写法提醒：

> 上表不是在证明 MaxRects 对所有边长完备，而是说明它在理论下界处给出了一个构造性可行证书。由于更小边长已被理论下界排除，构造器在下界处成功即可完成第一层最优性证明。

## 10. 最小边长下候选 HPWL 对照

主文可放每组最优候选，附录放完整 `q3_candidate_runs.csv`。若篇幅允许，建议放如下压缩表：

| 芯片 | 候选方法 | 初值 HPWL | refinement 后 HPWL | 接受移动数 | 说明 |
|---|---|---:|---:|---:|---|
| n100 | shelf_bfd:native | 237874.0 | 235824.5 | 54 | Q3 最优 |
| n100 | shelf_bfd:wide | 246784.5 | 244919.5 | 49 | 可行但线长更高 |
| n100 | shelf_bfd:narrow | 249706.0 | 245866.0 | 42 | 可行但线长更高 |
| n200 | shelf_bfd:narrow | 445560.5 | 433383.0 | 112 | Q3 最优 |
| n200 | shelf_bfd:native | 451018.5 | 448543.0 | 98 | 可行但线长更高 |
| n200 | shelf_bfd:wide | 457365.0 | 450772.0 | 84 | 可行但线长更高 |
| n300 | shelf_bfd:wide | 635755.5 | 613636.5 | 107 | Q3 最优 |
| n300 | maxrects:area_degree+wire | 614647.5 | 614482.0 | 25 | 初值好，但 refinement 后略差 |
| n300 | shelf:max_side+narrow | 645980.5 | 635712.0 | 88 | 可行但线长更高 |

可解释结论：

- 最小边长处空间极紧，许多 Q2 中可行的 MaxRects 目标引导合法化候选会失败，这是正常现象；
- shelf_bfd 行带构造在极紧边界下更容易给出可行初值；
- n300 中 `maxrects:area_degree+wire` 的初值 HPWL 接近最优，说明目标引导合法化仍有价值，但最终局部搜索后 `shelf_bfd:wide` 更优；
- refinement 后 HPWL 均下降，说明最小边长下仍存在局部线长改善空间。

## 11. 可行性验证表

论文建议给一个简化验证表：

| 芯片 | 越界 block 数 | 重叠对数 | terminal 越界数 | 面积守恒 | HPWL 复算一致 | 下界达成 | valid |
|---|---:|---:|---:|---|---|---|---|
| n100 | 0 | 0 | 0 | 是 | 是 | 是 | true |
| n200 | 0 | 0 | 0 | 是 | 是 | 是 | true |
| n300 | 0 | 0 | 0 | 是 | 是 | 是 | true |

正文可写：

> 程序对输出布局逐一检查 block 名称完整性、边界约束、不重叠约束、面积守恒、terminal 边界以及 HPWL 复算一致性。三组芯片均无越界、无重叠，摆放面积与输入 block 总面积一致，重新计算的 HPWL 与结果表完全一致。

完整验证文件为 `results/q3/q3_validation.json`。

## 12. 图表安排

### 12.1 主文图

建议至少放三张 Q3 布局图：

- 图 Q3-1：n100 在最小可行死区率下的布局；
- 图 Q3-2：n200 在最小可行死区率下的布局；
- 图 Q3-3：n300 在最小可行死区率下的布局。

对应文件：

- `results/q3/figures/n100_q3_layout.png`
- `results/q3/figures/n200_q3_layout.png`
- `results/q3/figures/n300_q3_layout.png`

同目录下有 SVG 版本，更适合论文排版。

图注建议包含：

- 外黑框：最小可行正方形轮廓；
- 彩色矩形：hard blocks；
- 黑色点：固定 terminal；
- 淡红色框：HPWL 较大的若干 nets 的外接框；
- 标题或图注中标明 \(L^*\)、\(\Gamma^*\)、HPWL。

### 12.2 对比图

建议论文手另做两张柱状图或折线图：

1. Q2 与 Q3 的边长/死区率对比：展示从 \(\Gamma\approx 0.15\) 压缩到约 0.09-0.10；
2. Q2 与 Q3 的 HPWL 对比：展示更紧版图导致 HPWL 上升。

数据直接来自 `results/q3/q3_summary.csv`。如果篇幅紧，这两张可以合并为双轴图，但不要让双轴误导读者；更稳妥的是两个并排小图。

### 12.3 主文表

建议主文至少放四张表：

1. 理论下界分解表；
2. 第三问主结果表；
3. Q2/Q3 权衡对比表；
4. 可行性验证表。

候选 HPWL 对照表可以放附录，正文只保留一句“候选对照见附表”。

## 13. 论文各章节该写什么

### 13.1 问题分析

重点写三件事：

1. 第三问的目标从固定死区率变为最小死区率；
2. 正方形边长是第一层核心决策变量，HPWL 是第二层目标；
3. terminal 固定坐标给出不可忽略的边长下界。

段落骨架：

> 第三问要求在满足 fixed-outline floorplanning 硬约束的前提下进一步压缩芯片轮廓。由于死区率 \(\Gamma\) 与正方形边长 \(L\) 单调对应，问题可转化为最小化整数边长 \(L\)。同时，HPWL 仍是布图质量的重要指标，但若将死区率和 HPWL 简单加权，会引入无物理依据的权重。因此本文采用词典序优化：先确定最小可行边长，再在该边长下优化 HPWL。

### 13.2 模型假设

建议列 5 条，并说明作用：

| 假设 | 用途 | 影响 |
|---|---|---|
| hard block 尺寸固定，可旋转 90 度 | 定义旋转变量和几何约束 | 若不允许旋转，可行边长可能变大 |
| block pin 位于几何中心 | 计算 HPWL | 与题目缺少内部 pin 偏移数据相匹配 |
| terminal 坐标固定且不缩放 | 保持 `.pl` 物理连接位置 | 形成 terminal 边长下界 |
| terminal 必须位于正方形轮廓内 | 保证 fixed outline 对所有连接端有效 | 若允许 terminal 在轮廓外，最小死区率需重算 |
| 死区率以 block 总面积为分母 | 与 fixed-outline 公式一致 | 整数边长导致实际 \(\Gamma\) 是离散值 |

### 13.3 模型建立

建议结构：

1. 定义 \(A_{\mathrm{blocks}}\)、\(L\)、\(\Gamma(L)\)；
2. 写 block 边界、不重叠、terminal 边界约束；
3. 写理论下界 \(L_{\mathrm{lb}}\)；
4. 写第一层目标 \(\min L\)；
5. 写第二层 HPWL 目标。

不要先写算法再补公式。第三问的说服力来自公式下界。

### 13.4 模型求解

建议分为四小节：

1. `理论下界计算`：面积、最大模块边、terminal 三个下界；
2. `边长可行性搜索`：整数 \(L\) 枚举，MaxRects 构造可行 packing；
3. `最小边长下 HPWL 优化`：复用 Q2 的解析线长松弛、合法化和局部改进；
4. `验证与输出`：写 CSV、图、JSON，复算约束和 HPWL。

### 13.5 结果与分析

先回答最小死区率，再分析 HPWL 代价。建议顺序：

1. 主结果表；
2. 下界达成说明；
3. Q2/Q3 对比；
4. 三张布局图；
5. 候选对照与 refinement 说明。

可用解释语句：

> 三组芯片的最小可行边长分别为 444、438、548，对应最小死区率分别为 0.09824458、0.09190875、0.09933009。由于这些边长均等于理论下界，本文完成了第三问第一层目标的最优性证明。与第二问相比，轮廓压缩导致 HPWL 分别上升 6.16%、5.74%、8.42%，反映出面积紧缩与线长优化之间的典型权衡。

### 13.6 验证与稳健性

建议写三层验证：

1. 理论验证：下界不可突破；
2. 构造验证：在下界处给出可行 layout；
3. 程序验证：越界、重叠、面积、terminal、HPWL 复算。

若论文篇幅足够，可以补充：

- 将 terminal 下界去掉作为“解释差异”情景，但必须重新求解，现阶段不要编造；
- 增加 `refine_passes` 或 `refine_top` 的计算预算敏感性，但也需要实际运行后再写。

## 14. 结果证据分配

按论文主线建议这样分配：

| 证据 | 功能 | 放置位置 |
|---|---|---|
| \(L_{\mathrm{lb}}\) 公式 | 核心证明 | 模型建立 |
| 三个下界数值 | 必要支持 | 结果主表 |
| \(L_{\mathrm{lb}}\) 可行搜索日志 | 构造性证明 | 主文简表或附表 |
| Q3 HPWL | 第二层结果 | 主结果表 |
| Q2/Q3 HPWL 差值 | 权衡解释 | 结果分析 |
| 候选方法完整列表 | 算法稳健性/对照 | 附录 |
| JSON 验证细节 | 可复现性 | 附录或代码说明 |
| block 坐标全表 | 输出交付 | 附录或结果文件说明 |

## 15. 不要写过头的话

不要写：

- “第三问 HPWL 达到全局最优。”
- “本文证明了 MaxRects 算法对任意边长都能判定可行性。”
- “死区率连续下降到某一阈值。”
- “terminal 坐标可随边长缩放。”
- “最小死区率与 HPWL 同时全局最优。”

推荐写：

- “在 fixed terminal inside-outline 解释下，最小可行边长等于理论下界。”
- “通过在理论下界处构造出满足全部硬约束的布局，确定了第一层目标的全局最小死区率。”
- “在最小边长下，本文复用 Q2 的目标引导合法化和局部 HPWL refinement 得到高质量可行布局。”
- “相比 \(\Gamma=0.15\) 的第二问结果，第三问以 HPWL 上升为代价换取更小轮廓面积。”

## 16. 边界情况与审稿风险

### 16.1 Terminal 在边界上的点

若 terminal 坐标等于 \(L\)，视为在闭区间 \([0,L]\) 内，允许存在。程序验证条件为 \(X_t>L\) 或 \(Y_t>L\) 才判定越界。

### 16.2 坐标若为小数

理论下界必须写上取整：

\[
L_{\mathrm{terminal}}=\left\lceil \max_{t\in T}\max(X_t,Y_t)\right\rceil.
\]

代码已按上取整处理，避免小数坐标被向下取整。

### 16.3 如果不要求 terminal 在轮廓内

则第三项下界 \(L_{\mathrm{terminal}}\) 不成立，最小边长可能下降到面积下界附近。本文没有在该替代解释下重新求解，不能把当前结果推广过去。

### 16.4 如果不允许 block 旋转

当前可行构造依赖旋转选项。若题面解释为不可旋转，需要重新运行并重写下界和结果。

### 16.5 线长和面积的矛盾

最小死区率会挤压模块位置自由度，因此 HPWL 增大并不表示算法失败，而是第一层目标优先级导致的合理代价。论文中应主动解释这个 trade-off。

## 17. 交付文件清单

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

## 18. 复现命令

在项目根目录运行：

```powershell
python src\q3_min_deadspace.py --output-dir results\q3 --refine-passes 2 --refine-top 3 --refine-method fast
```

验证语法：

```powershell
python -m py_compile src\q2_fixed_outline_hpwl.py src\q3_min_deadspace.py
```

若只想快速检查某一个芯片：

```powershell
python src\q3_min_deadspace.py --chips n100 --output-dir results\q3_n100_check
```

## 19. 摘要可用句

第三问摘要建议这样写：

> 针对最小死区率问题，本文将固定轮廓面积压缩转化为整数正方形边长的词典序优化。首先由模块总面积、最大模块边长和 fixed terminal 坐标推导理论下界，再在该下界处构造可行 packing，从而确定 n100、n200、n300 的最小边长分别为 444、438、548，对应最小死区率分别为 0.09824458、0.09190875、0.09933009。在上述最小边长下进一步优化 HPWL，得到总 HPWL 分别为 235824.5、433383.0、613636.5；相对于 \(\Gamma=0.15\) 的第二问结果，HPWL 分别增加 6.16%、5.74%、8.42%，说明更紧凑轮廓会带来可量化的线长代价。所有输出布局均通过边界、重叠、面积守恒、terminal 边界和 HPWL 复算验证。
