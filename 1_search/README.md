# 1 — Search and merge

Raw database exports plus the merged, deduplicated BibTeX library that feeds screening.

| File | Source |
| ---- | ------ |
| `acm.bib` | ACM Digital Library |
| `ieee.bib` | IEEE Xplore |
| `scopus.bib` | Scopus |
| `papers.bib` | Merged and deduplicated across the three sources |

`papers.bib` and `../artifacts/all_papers.csv` are produced manually from the three raw exports. `all_papers.csv` is the input to every downstream phase and uses columns `id`, `canonical_id`, `title`, `abstract`.

See the search string, databases, and yield figures in the top-level `README.md`.
