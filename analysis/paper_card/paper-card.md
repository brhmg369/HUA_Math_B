# Paper Card：Modern Floorplanning Based on B*-Tree and Fast Simulated Annealing

> Source coverage: Full paper  
> Extraction confidence: Mixed, because PDF page locators are reliable but automatic figure/table extraction was weak  
> Locator mode: page-grounded  
> Primary analytical lens: methods  
> Secondary analytical lens: None  
> Context verification: Paper-only  
> Card completeness: Complete relative to supplied source

## 01 基本信息

| 字段 | 内容 |
|---|---|
| 题名 | Modern Floorplanning Based on B*-Tree and Fast Simulated Annealing |
| 作者 | Tung-Chieh Chen; Yao-Wen Chang |
| 期刊 | IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems |
| 年份 | 2006 |
| DOI | 10.1109/TCAD.2006.870076 |
| 论文类型 | [Paper] 方法/算法论文 |
| 领域 | [Paper] VLSI physical design, floorplanning |
| 主要关键词 | B*-tree, Fast-SA, fixed-outline floorplanning, bus-driven floorplanning |
| 与本题关系 | [Analysis] 本题 Q1-Q3 与论文的 B*-tree packing、Fast-SA 搜索、fixed-outline cost 直接相关；论文 BDF 部分与本题 nets/HPWL 不同，只能迁移“位置约束修复”思想。 |

## 02 一句话总结

[Paper] 论文用 B*-tree 表示非切割/切割 floorplan，并结合三阶段 Fast-SA 与固定轮廓自适应代价函数，在 fixed-outline floorplanning 和 bus-driven floorplanning 中提高可行解搜索速度与稳定性 [Paper: PDF p. 1, Abstract; PDF p. 12, Conclusion]。

## 03 研究问题

[Paper] 论文面对的问题是：现代 VLSI floorplanning 不仅要最小化面积，还要在固定 die outline、互连和位置约束下摆放模块；传统只追求 outline-free 面积最小的 floorplanning 可能无法放入给定轮廓 [Paper: PDF p. 1, Introduction]。

[Analysis] 可重构为一个方法问题：Can a compact floorplan representation and a staged annealing schedule efficiently find high-quality feasible floorplans under fixed outline and interconnect-position constraints?

## 04 研究背景与发展路径

[Paper-framed; external verification not performed] 论文将背景分为三层：

| 阶段 | 代表思路 | 优点 | 痛点 | 论文定位 |
|---|---|---|---|---|
| Classical floorplanning | 主要做 block packing 和面积最小化 | 问题相对清楚 | 不保证适配固定芯片轮廓 | 论文认为现代设计需要 fixed-outline formulation |
| Fixed-outline floorplanning | 在给定 W/H 内找可行布局 | 更贴近现代 hierarchical design | 比 outline-free 更难，惩罚函数权重难调 | 提出 adaptive Fast-SA |
| BDF | 同时考虑 bus/interconnect 和 block positions | 更早处理布线可行性 | bus alignment、overlap、fixed I/O port 共同作用 | 用 B*-tree feasibility conditions + dummy blocks |

论文还指出 sequence pair (SP) 的解空间为 `(n!)^2`，而 B*-tree 解空间阶为 `O(n! 2^(2n) / n^1.5)`，以此解释 B*-tree 搜索空间更紧凑 [Paper: PDF p. 1, Introduction]。

## 05 论文识别的核心痛点

| Pain point | Manifestation | Cause or author explanation | Evidence from the paper |
|---|---|---|---|
| Fixed outline 下单纯面积最小不够 | 面积小的 floorplan 可能不适配指定轮廓 | 轮廓宽高约束改变了可行域 | [Paper: PDF p. 1, Introduction] |
| 直接惩罚越界不稳定 | penalty 太大易困在第一个可行解，太小又难找到可行解 | 固定权重无法同时兼顾可行性和优化质量 | [Paper: PDF p. 4, Algorithm Overview] |
| Classical SA 运行时间长 | 早期接受过多劣解，搜索效率低 | 高温阶段探索过度 | [Paper: PDF p. 2-3, Fast SA] |
| bus 约束会和 block packing 相互耦合 | bus 要穿过多个模块并避免 bus 间重叠 | 模块位置直接决定 bus feasibility | [Paper: PDF p. 5-7, BDF] |

## 06 核心思想

1. Surface method: [Paper] 用 B*-tree 表示 floorplan，用 Fast-SA 扰动 B*-tree，并在固定轮廓问题中动态调节 cost weight [Paper: PDF p. 2-4]。
2. Core insight: [Analysis] 论文不是单纯“换一个优化器”，而是把表示、packing 复杂度、邻域操作、温度调度和轮廓可行性惩罚放在同一个闭环里。
3. General lesson: [Analysis] 对本题而言，先保证每个候选状态都能被快速 packing 并校验不重叠，再在此基础上优化面积/HPWL，比直接在连续坐标空间中随机移动矩形更可控。

## 07 方法总览

| 元素 | 论文方法 |
|---|---|
| 输入 | rectangular macro blocks；fixed-outline 参数；wirelength/bus constraints |
| 输出 | block 坐标、方向、floorplan area、wirelength 或 bus feasibility/cost |
| 表示 | B*-tree，每个节点对应一个 block |
| packing | root 放在左下角；left child 放在父块右侧；right child 与父块同 x 并置于上方；y 坐标由 contour structure 计算 |
| 邻域 | rotate block, move node, swap nodes, resize soft block |
| 搜索 | Fast-SA：高温随机、伪贪婪局部搜索、再升温爬坡并降温 |
| fixed-outline 扩展 | 加入 aspect-ratio penalty，动态更新面积权重 alpha |
| BDF 扩展 | 检查 B*-tree 中 bus feasibility，插入 dummy blocks 修复 falling-down 与 overlap |

输入到输出流程：

```text
blocks/nets/outline constraints
-> initialize B*-tree
-> pack by contour
-> evaluate area/wirelength/outline violation or bus feasibility
-> perturb B*-tree
-> accept/reject by SA probability
-> record best feasible floorplan
```

## 08 核心模块拆解

| Module | Function | Why it is needed | Input and output | Supporting evidence | Known or expected effect of removal |
|---|---|---|---|---|---|
| B*-tree representation | 将几何布局编码成有序二叉树 | 降低搜索空间，并允许线性/均摊线性 packing | Input: block set; Output: tree and coordinates | [Paper: PDF p. 2, Fig. 1] | [Analysis] 若直接优化坐标，非重叠约束处理更重；若用 SP，搜索空间更大 |
| Contour packing | 从 B*-tree 快速生成无重叠布局 | 每次扰动都要快速评价 | Input: B*-tree; Output: packed floorplan | [Paper: PDF p. 2, Section II] | [Analysis] packing 慢会使 SA 迭代预算不足 |
| Fast-SA schedule | 加快收敛并保持跳出局部最优能力 | classical SA 早期接受劣解过多，速度慢 | Input: cost deltas; Output: temperature sequence | [Paper: PDF p. 3, Eq. 2; PDF p. 9-10, Fig. 14-15] | [Paper] greedy alone最终 dead space 较差，classical SA 较慢 |
| Adaptive fixed-outline cost | 在可行性和面积/线长目标间动态调权 | 固定 penalty weight 对不同 aspect ratio 不稳定 | Input: recent feasible count; Output: alpha | [Paper: PDF p. 4, Eq. 5-6; PDF p. 10-11, Table III-IV] | [Paper] adaptive alpha 同时改善 success probability 和 solution quality |
| Dummy-block bus repair | 修复 bus 对齐和重叠问题 | bus constraints 可能被 packing 下落破坏 | Input: bus block set; Output: shifted blocks with dummy blocks | [Paper: PDF p. 5-8, Eq. 7-9] | [Analysis] 本题无 bus 约束，不能直接作为 Q2 主算法；可作为 Q4/位置约束扩展启发 |

## 09 关键公式与符号

| 公式 | 符号含义 | 作用 | 直觉 | Source |
|---|---|---|---|---|
| `Prob = min{1, exp(-Delta C / T)}` | `Delta C` 为新旧 cost 差，`T` 为温度 | SA 接受准则 | 温度越高越容易接受劣解 | [Paper: PDF p. 2, Eq. 1] |
| `T_1 = Delta_avg / ln P`; `T_n = T_1 <Delta_cost> / (n c)` for `2 <= n <= k`; `T_n = T_1 <Delta_cost> / n` for `n > k` | `P` 为初始接受上坡概率，`c,k` 控制伪贪婪阶段 | Fast-SA 温度调度 | 先随机，再接近贪婪，再恢复爬坡搜索 | [Paper: PDF p. 3, Eq. 2] |
| `Cost = alpha A/A_norm + (1-alpha) W/W_norm` | `A` area，`W` wirelength | 面积/线长组合目标 | 归一化后做加权 | [Paper: PDF p. 3, Eq. 3] |
| `H* = sqrt((1+Gamma) A R*)`, `W* = sqrt((1+Gamma) A / R*)` | `Gamma` 死区比例，`R* = height/width` | 固定轮廓尺寸 | 给定总面积和目标长宽比得到 outline | [Paper: PDF p. 4, Eq. 4] |
| `Phi(F) = alpha A + beta W + (1-alpha-beta)(R-R*)^2` | `R` 当前布局长宽比 | fixed-outline 代价 | 不只罚越界，还引导形状接近轮廓 | [Paper: PDF p. 4, Eq. 5] |
| `alpha = alpha_base + (1-alpha_base)(n_feasible/n)` | 最近 `n` 个候选中可行解个数 | 动态调节面积权重 | 可行解越多，越集中优化 area/wirelength | [Paper: PDF p. 4, Eq. 6] |
| `Delta_i = max(0, (y_min+t)-(y_i+h_i))` | dummy block 高度 | 修复水平 bus 对齐 | 把下落模块抬到满足 overlap range | [Paper: PDF p. 5, Eq. 7] |
| `Psi(F,U)=alpha A + beta B + gamma M` | `B` bus area，`M` unassigned buses | BDF cost | 同时惩罚面积、bus area 和未分配 bus | [Paper: PDF p. 7, Eq. 8] |
| `Psi'(F,U)=alpha A + beta B + gamma M + delta N + epsilon L` | `N` unassigned segments，`L` bends | multibend BDF cost | 把多折线 bus 的复杂度纳入目标 | [Paper: PDF p. 8, Eq. 9] |
| `T_new = lambda T_old` | classical SA cooling | 对照基线 | 固定比例降温 | [Paper: PDF p. 9, Eq. 10] |

## 10 实验设计与证据链

图表清单：

- Fig. 1：B*-tree 与 admissible placement 的对应关系 [Paper: PDF p. 2]。
- Fig. 2：classical SA、TimberWolf SA、Fast-SA 温度变化示意 [Paper: PDF p. 3]。
- Fig. 3-Fig. 4：fixed-outline cost 直觉和 adaptive SA 算法 [Paper: PDF p. 4-5]。
- Fig. 5-Fig. 13：BDF 中 bus feasibility、dummy blocks、twisted bus、multibend bus [Paper: PDF p. 6-8]。
- Fig. 14-Fig. 15：Fast-SA 收敛速度与稳定性对比 [Paper: PDF p. 9-10]。
- Table I-II：不同 SA schedule 的 dead space 与 runtime 对比 [Paper: PDF p. 8-10]。
- Table III-IV：固定 alpha 与 adaptive alpha、以及不同算法 fixed-outline success rate 对比 [Paper: PDF p. 10-11]。
- Table V：n100/n200/n300 fixed-outline wirelength 对比 [Paper: PDF p. 11]。
- Table VI：BDF dead space 与 runtime 对比 [Paper: PDF p. 13]。

| Experiment | Claim tested | Comparison and conditions | Result | Supported conclusion | Unsupported stronger conclusion | Source |
|---|---|---|---|---|---|---|
| Fast-SA convergence | Fast-SA 比 classical/TimberWolf SA 更快达到相近面积质量 | GSRC n100/n200/n300，同 B*-tree 表示、同初始温度，只改变降温 schedule | Table I 和 Fig. 14 报告 Fast-SA 显著减少达到约 5% dead space 的时间 | Fast-SA schedule 对这些 benchmark 有速度优势 | 不能证明任意组合优化问题都同等有效 | [Paper: PDF p. 8-10] |
| Greedy vs SA | 伪贪婪阶段需配合后续 hill-climbing | MCNC ami49，比较 greedy、classical SA、TimberWolf SA、Fast-SA | greedy 初期最快但最终 dead space 较差，Fast-SA 最终质量更好 | 三阶段结构比纯贪婪更适合质量导向 floorplanning | 不能证明给定参数对所有数据最优 | [Paper: PDF p. 10, Fig. 15/Table II] |
| Adaptive alpha | 动态权重比固定 alpha 更稳 | n100，Gamma=10%，R*=1,2，比较常数 alpha 和 adaptive alpha | adaptive alpha 有更高 success probability 和较低平均 dead space | 动态权重可以缓解 penalty 权重难调 | 不能直接给本题 alpha_base/n 的最优值 | [Paper: PDF p. 10-11, Table III] |
| Fixed-outline success rate | adaptive Fast-SA 能更稳定找到可行 fixed-outline floorplan | n100，不同 aspect ratio，Gamma=10%/15%，对比 GFA、Parquet SP、Parquet B*-tree | 论文报告其算法在所有测试设置下 100% success rate | 该方法适合固定轮廓可行性搜索 | 不等于对本题每次运行都必然成功 | [Paper: PDF p. 11, Table IV] |
| Fixed-outline wirelength | 在给定 outline 下优化 wirelength | GSRC n100/n200/n300，R*=1,2,3,4，对比 Parquet SP | 论文报告平均约 6% wirelength reduction 和约 11% runtime reduction | B*-tree + adaptive Fast-SA 可作为本题 Q2 的强候选框架 | 不能复用论文数值作为本题答案 | [Paper: PDF p. 11, Table V] |
| BDF | dummy-block B*-tree approach 能处理 bus constraints | MCNC 改造 benchmark，对比 Xiang et al. | Table VI 报告 hard/soft blocks 下 dead space 和 runtime 改善 | 约束修复思想对位置约束有效 | 本题 HPWL nets 不等同于 bus constraints | [Paper: PDF p. 12-13, Table VI] |

## 11 结论的正确解释

[Paper] 论文证明的是：在作者使用的 benchmark、算法实现和比较设置下，B*-tree + Fast-SA 对 fixed-outline floorplanning 与 BDF 有较好的速度、稳定性和结果质量 [Paper: PDF p. 12-13, Conclusion]。

[Analysis] 对本题可谨慎迁移的结论是：B*-tree 可以作为 Q1-Q3 的布局状态表示，Fast-SA 可以作为主搜索框架，adaptive outline penalty 可以作为 Q2/Q3 固定轮廓可行性的引导项。不可迁移的是：论文中的 `P=0.9`、`c=100`、`k=7`、`alpha_base=0.5`、`n=500` 不能无依据地照搬为本题最终参数；它们最多是论文基准设置和初始候选值。

## 12 作者明确承认的局限

No explicit author-acknowledged limitation section was found in the supplied source.

Related constraints noted by the authors:

| Constraint noted | Specific manifestation | Possible author direction | Source |
|---|---|---|---|
| BDF 主模型只允许 0-bend bus | 当 bus 经过较多 blocks 时，multibend 可能产生更好解 | 扩展为 `k`-bend bus，并增加 segment/group perturbation | [Paper: PDF p. 8, Extension to Multibend Buses] |
| fixed-outline 权重难以预先指定 | 不同 `R*` 和 `Gamma` 下最优 alpha 不同 | 用最近候选可行率动态更新 alpha | [Paper: PDF p. 4, Adaptive SA] |

## 13 批判性分析

| `[Analysis]` Observation | Potential issue or alternative explanation | Why it matters | How to test it | Basis |
|---|---|---|---|---|
| SA 仍是启发式 | 多次运行找不到更优解不等于全局最优 | 本题论文不能把 n100/n200/n300 结果写成严格全局最优 | 多随机种子、收敛曲线、小规模精确枚举、下界比较 | [Paper: PDF p. 3, SA; PDF p. 9-11, experiments] |
| 参数来自论文实验环境 | `P,c,k,alpha_base,n` 是作者实验选择 | 本题若照搬会显得人为设常数 | 用预实验、规模相关预算、稳定性分析确定或说明参数 | [Paper: PDF p. 3-4] |
| BDF 与本题 HPWL 目标不同 | BDF 要 bus 穿过 blocks；本题 nets 只计算中心/terminal 的 HPWL | 不能把 dummy block bus repair 当作 Q2 主模型 | 将 BDF 仅写入“相关工作/扩展启发”，Q2 主体用 HPWL cost | [Paper: PDF p. 5-8; 题面 Q2] |
| fixed-outline cost 中 aspect ratio penalty 不等于越界 penalty | 接近目标长宽比不必然保证不越界 | Q2/Q3 必须最终显式检查 `W<=W_chip` 和 `H<=H_chip` | 对每个输出布局逐条验算边界、重叠和 HPWL | [Paper: PDF p. 4, Eq. 5] |

## 14 学到的可迁移知识

Agent-derived knowledge candidates:

- B*-tree 将二维非重叠布局转成树结构搜索，left child/right child 分别表达“右邻”和“上方同 x”的相对关系。
- Contour packing 是高频迭代优化的关键，因为每次扰动都要快速从树恢复坐标。
- 固定轮廓问题不宜只用简单越界罚项；动态权重能根据近期可行性自动在“找可行解”和“优化目标”之间切换。
- 对竞赛论文而言，应把“算法找到可行好解”和“全局最优证明”区分开。
- 与本题 HPWL 相关的可复用目标是 `area/wirelength` 归一化组合，而不是 BDF bus area cost。

## 15 与本题的连接

| 本题部分 | 论文可复用内容 | 需要改造 | 不可直接复用 |
|---|---|---|---|
| Q1 无连接面积最小 | B*-tree packing；rotate/move/swap 邻域；面积 cost | 增加“面积相同长宽比接近 1”的词典序或二级惩罚 | fixed-outline cost 中的 outline penalty |
| Q2 固定正方形 HPWL | fixed-outline formulation；HPWL/area 组合 cost；adaptive penalty | 轮廓为正方形，`R*=1`；terminal 坐标参与 HPWL | BDF bus constraints |
| Q3 最小死区比例 | fixed-outline 可行性搜索和 adaptive alpha | 外层用二分/区间搜索死区比例，内层多次 SA 验证可行 | 单次失败即判不可行 |
| Q4 非矩形模块 | dummy block/shape adjustment 的“表示扩展”思想 | 将模块表示从单矩形改成多边形或矩形并集，重叠检测改为形状级别 | B*-tree 的矩形邻接规则原样套用 |

## 16 研究/实现候选想法

Agent-derived research candidates:

1. Candidate idea: fixed-outline feasibility-guided HPWL annealing  
   Originating observation: 固定惩罚权重不稳定 [Paper: PDF p. 4, Eq. 5-6]。  
   Core hypothesis: 若 HPWL 优化过程中根据近期可行率动态提高或降低 outline penalty，则比固定 penalty 更容易在 Q2/Q3 中获得可行且线长较短的布局。  
   Delta from paper: 将 adaptive alpha 从 area-oriented fixed-outline 扩展到本题的 HPWL-oriented fixed-square problem。  
   Validation: 与固定权重、多随机种子、相同迭代预算比较可行率、HPWL、运行时间和边界余量。  
   Possible failure modes: 权重振荡导致搜索不稳定；死区比例很小时可行域过窄，动态调权仍难进入可行域。  
   Innovation status: unverified.

2. Candidate idea: dead-space binary search with stochastic feasibility certificate  
   Originating observation: Q3 要找最小可行 dead_space_ratio，而 SA 单次运行有随机失败风险。  
   Core hypothesis: 外层二分死区比例、内层多种子可行性搜索，并用失败次数/成功率作为证据边界，比单次搜索更适合竞赛论文表达。  
   Delta from paper: 论文固定 Gamma 做 success rate，对本题需反过来搜索最小 Gamma。  
   Validation: 对每个候选 Gamma 记录成功率、最优 HPWL、约束余量和收敛轨迹。  
   Possible failure modes: 计算预算高；接近临界 Gamma 时成功率估计不稳定。  
   Innovation status: unverified.

3. Candidate idea: nonrectangular module as rectangle-union packing for Q4  
   Originating observation: Q4 将矩形模块改为 L/T 型，B*-tree 的单矩形 overlap check 不够。  
   Core hypothesis: 把每个 L/T 型模块表示为局部坐标下的若干矩形并集，并在旋转后做 pairwise rectangle-union overlap，可在保留 Q1 搜索框架的同时处理非规则形状。  
   Delta from paper: 从 rectangular B*-tree packing 扩展到 shape-aware overlap verification。  
   Validation: 4 模块实例用枚举/精确网格验证最小面积，再与启发式搜索输出对比。  
   Possible failure modes: B*-tree packing 仅保证外接矩形层面的关系，非矩形空洞利用不足；离散网格精度若与尺寸单位不一致会造成伪最优。  
   Innovation status: unverified.
