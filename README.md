# HUA Math B - VLSI Floorplanning

This repository contains the current work for the 2026 HUA Math Cup B problem,
including the first three subproblems:

- Q1: outline-free hard-block floorplanning with area-first optimisation.
- Q2: fixed-square-outline HPWL optimisation with `dead_space_ratio = 0.15`.
- Q3: minimum feasible dead-space ratio search, followed by HPWL optimisation
  at the minimum square side length.

## Main Files

- `src/q1_floorplanning.py`: Q1 solver.
- `src/q2_fixed_outline_hpwl.py`: Q2 solver.
- `src/q3_min_deadspace.py`: Q3 minimum-deadspace solver.
- `docs/q1_paper_writer_sync.md`: paper-writing guide for Q1.
- `docs/q2_paper_writer_sync.md`: paper-writing guide for Q2.
- `docs/q3_paper_writer_sync.md`: paper-writing guide for Q3.
- `results/q1/`: Q1 summary, layouts, figures and validation report.
- `results/q2/`: Q2 summary, candidate comparisons, layouts, figures and validation report.
- `results/q3/`: Q3 summary, minimum-side search log, layouts, figures and validation report.
- `analysis/`: problem and reference-paper reading notes.

## Reproduce

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run Q1:

```powershell
python src\q1_floorplanning.py --output-dir results\q1
```

Run Q2:

```powershell
python src\q2_fixed_outline_hpwl.py --output-dir results\q2 --refine-passes 2 --refine-top 3 --refine-method mixed
```

Run Q3:

```powershell
python src\q3_min_deadspace.py --output-dir results\q3 --refine-passes 2 --refine-top 3 --refine-method fast
```
