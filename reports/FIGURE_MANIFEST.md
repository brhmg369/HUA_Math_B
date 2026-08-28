# FIGURE MANIFEST

## 问题一

| Figure ID | 类型 | 任务 | 图片来源 | 源数据 | 绘图代码 | Caption | Lead-in | Interpretation | 状态与 QA |
|---|---|---|---|---|---|---|---|---|---|
| Q1-F1 | RESULT | 同时保留 n100、n200 的真实细长比例与局部模块分布 | `results/q1/figures/q1_slender_overview_segments.pdf`（另有 SVG、PNG） | `results/q1/layouts/n100_q1_layout.csv`、`n200_q1_layout.csv` | `src/q1_layout_figures.py` | n100 与 n200 的真实比例总览及分段展开 | 由两组较低冗余率与极端长短边比的对照引出 | 说明面积较紧凑的布局仍可能形成极细长轮廓 | ready；冻结坐标直接绘制、真实比例总览、连续分段展开、低饱和配色、矢量输出、正文先引用 |
| Q1-F2 | RESULT | 展示 n300 的近方形轮廓及模块间空隙 | `results/q1/figures/q1_n300_balanced_layout.pdf`（另有 SVG、PNG） | `results/q1/layouts/n300_q1_layout.csv` | `src/q1_layout_figures.py` | n300 的真实比例布局 | 由 n300 的长短边比和面积冗余率引出 | 与前两组共同说明面积紧凑性和轮廓均衡性存在竞争 | ready；冻结坐标直接绘制、低饱和配色、矢量输出、正文先引用 |

问题一未额外加入算法流程图：求解主线可由正文直接表达，版面集中用于展示跨实例的面积—形状关系。

## 问题二

| Figure ID | 类型 | 任务 | 图片来源 | 源数据 | 绘图代码 | Caption | Lead-in | Interpretation | 状态与 QA |
|---|---|---|---|---|---|---|---|---|---|
| Q2-F1 | RESULT | 比较 n100、n200 在固定正方形轮廓内的模块分布与主要网络外接框 | `results/q2/figures/n100_q2_layout.png`、`n200_q2_layout.png` | `results/q2/layouts/n100_q2_layout.csv`、`n200_q2_layout.csv`，以及题目 `.nets/.pl` | `src/q2_fixed_outline_hpwl.py` | 问题二 n100 与 n200 在死区率 0.15 下的固定轮廓 HPWL 布局 | 由主结果和候选对照引出模块分布及线长压力 | 说明固定边界、终端和多引脚网络共同限制模块位置 | ready；源图与最终 PDF 版面均已核对，双图、图题和图后分析清晰可辨 |
| Q2-F2 | RESULT | 展示 n300 在更大模块与网络规模下的固定轮廓可行布局 | `results/q2/figures/n300_q2_layout.png` | `results/q2/layouts/n300_q2_layout.csv`，以及题目 `.nets/.pl` | `src/q2_fixed_outline_hpwl.py` | 问题二 n300 在连续边长 560.487 的正方形轮廓内所得 HPWL 布局 | 由 n300 的数据规模和最终 HPWL 引出 | 说明断点局部搜索在保持可行性的同时降低总 HPWL | ready；源图与最终 PDF 版面均已核对，轮廓、模块空隙、图题及分析清晰可辨 |
| Q2-F3 | COMPARE | 比较三组实例在几何合法化后与局部重插入后的 HPWL | `results/q2/figures/q2_hpwl_before_after.png`、`q2_hpwl_before_after.svg` | `results/q2/q2_summary.csv` | `src/q2_fixed_outline_hpwl.py` | 三组实例在几何合法化后与局部重插入后的 HPWL 对比 | 由表 6 的初始与最终 HPWL 引出 | 三组数据均继续下降，说明合法化后仍存在局部线长优化空间 | ready；使用同一 HPWL 口径，精确值与改善率均由结果文件直接生成，颜色与纹理冗余编码 |

问题二未新增算法流程图：正文已用二次松弛、合法化、候选筛选和局部重插入四个层次说明求解流程，主文优先保留直接回答题目的布局结果图。

## 问题三

| Figure ID | 类型 | 任务 | 图片来源 | 源数据 | 绘图代码 | Caption | Lead-in | Interpretation | 状态与 QA |
|---|---|---|---|---|---|---|---|---|---|
| Q3-F1 | RESULT | 比较 n100、n200 在首个构造可行边长下的紧轮廓布局 | `results/q3/figures/n100_q3_layout.png`、`n200_q3_layout.png` | `results/q3/layouts/n100_q3_layout.csv`、`n200_q3_layout.csv`，以及题目 `.nets/.pl` | `src/q3_min_deadspace.py`、`src/q2_fixed_outline_hpwl.py` | 问题三 n100 与 n200 在首个构造可行边长下的硬模块布局 | 由轮廓压缩、搜索日志和 HPWL 增量引出布局结构 | 说明 Terminal 保持原坐标参与 HPWL，但不作为硬模块轮廓判据 | ready；源图与最终 PDF 组合版均已检查，模块、外框、图题和图后解释清晰可辨 |
| Q3-F2 | RESULT | 展示 n300 在死区率 5.5639% 下的紧轮廓布局 | `results/q3/figures/n300_q3_layout.png` | `results/q3/layouts/n300_q3_layout.csv`，以及题目 `.nets/.pl` | `src/q3_min_deadspace.py`、`src/q2_fixed_outline_hpwl.py` | 问题三 n300 在边长 537、死区率 5.5639% 下的硬模块布局 | 由 n300 最大的 HPWL 相对增量引出 | 说明更高布局密度与有限移动空间对应更大的线长代价 | ready；源图与最终 PDF 尺寸均已检查，轮廓、模块、图题和结论清晰可辨 |
| Q3-F3 | COMPARE | 直接呈现问题二到问题三的死区率下降与 HPWL 上升 | `results/q3/figures/q3_tradeoff_q2_q3.pdf`、`.svg`、`.png` | `results/q3/q3_summary.csv` | `src/plot_q3_tradeoff.py` | 问题二到问题三的死区率压缩与 HPWL 增长关系 | 由主结果表引出面积利用率与互连代价的同步变化 | 三组死区率均由 15% 降至 5.5639%--7.3649%，而 HPWL 同时上升 7.79%--14.31%，构成明确 trade-off | ready；无双 Y 轴，颜色与 marker 冗余编码，矢量/400 DPI 输出，数值与结果表一致 |

## 问题四

| Figure ID | 类型 | 任务 | 图片来源 | 源数据 | 绘图代码 | Caption | Lead-in | Interpretation | 状态与 QA |
|---|---|---|---|---|---|---|---|---|---|
| Q4-F1 | RESULT/MECH | 展示四个模块如何利用 b1 凹槽形成零死区满铺，并直观支撑构造性最优证明 | `results/q4/figures/q4_optimal_layout.png`、`results/q4/figures/q4_optimal_layout.svg` | `results/q4/q4_layout.csv`、`results/q4/q4_grid.txt` | `src/q4_nonrect_floorplanning.py` | 四个模块利用 b1 凹槽形成的 $6\times4$ 全局最优形状级布局 | 在坐标表后先以“总面积下界 $24$ + 面积为 $24$ 的可行构造”完成最优性证明，再用该图解释等号如何达到 | b2 的右下短臂和旋转后的 b3 分别进入 b1 外接框的左右下凹槽；矩形外接框碰撞模型会错误排除该零死区布局 | ready；已采用固定低饱和配色和模块直标，删除重复内标题，明确标出 $6\times4$ 尺寸及 b1 虚线外接框；源数据、PNG/SVG 与正文数值一致，缩小后标签和边界仍清晰可辨 |
