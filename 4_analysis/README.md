# 4 — Analysis and outputs

Scripts and notebooks that produce the paper-facing tables and figures from the coding artifacts.

## Scripts

```sh
uv run python scripts/build_merge.py                    # ../artifacts/merge.csv
uv run python scripts/build_presence_matrix.py          # ../tables/presence-matrix.tex
uv run python scripts/build_venue_categories_table.py   # ../tables/venue-categories.tex
```

- `build_merge.py` — joins `metadata.csv`, `extraction.csv`, `others.csv` (only `research_type`), and the four facet assignments inverted from `scheme.json`. Output: `../artifacts/merge.csv`.
- `build_presence_matrix.py` — emits a multi-page `longtable` showing every report against each of the 14 facet categories.
- `build_venue_categories_table.py` — emits the appendix venue/category table.

## Notebooks

`uv run jupyter lab notebooks/plots.ipynb` — reads `../artifacts/merge.csv`, writes all paper figures into `../figures/`. Uses `notebooks/mystyle.mplstyle` for shared styling.

## Decoupling from the paper repository

Everything in this phase writes to `../tables/` or `../figures/`. The paper repository copies those files in when it builds; nothing here writes across project boundaries.
