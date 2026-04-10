# Searches

Databases:

- Scopus
- ACM DL
- IEEE Xplore

## Search strings

### Scopus

```
(
    TITLE-ABS-KEY("high-performance computing" OR supercomputing OR supercomputer OR HPC) 
    AND 
    TITLE-ABS-KEY("sustainability" OR "sustainable" OR "ecological" OR "footprint" OR "environmental impact" OR "carbon emission" OR "greenhouse gas" OR "water consumption" OR "water usage" OR "lifecycle assessment" OR "LCA" OR "embodied carbon" OR "e-waste" OR "electronic waste" OR "material depletion" OR "resource consumption" OR "rare earth")
)
```

### ACM

```
(
  Title:("high-performance computing" OR supercomputing OR supercomputer OR HPC) OR
  Abstract:("high-performance computing" OR supercomputing OR supercomputer OR HPC) OR
  Keyword:("high-performance computing" OR supercomputing OR supercomputer OR HPC)
)
AND
(
  Title:("sustainability" OR "sustainable" OR "ecological" OR "footprint" OR "environmental impact" OR "carbon emission" OR "greenhouse gas" OR "water consumption" OR "water usage" OR "lifecycle assessment" OR "LCA" OR "embodied carbon" OR "e-waste" OR "electronic waste" OR "material depletion" OR "resource consumption" OR "rare earth") OR
  Abstract:("sustainability" OR "sustainable" OR "ecological" OR "footprint" OR "environmental impact" OR "carbon emission" OR "greenhouse gas" OR "water consumption" OR "water usage" OR "lifecycle assessment" OR "LCA" OR "embodied carbon" OR "e-waste" OR "electronic waste" OR "material depletion" OR "resource consumption" OR "rare earth") OR
  Keyword:("sustainability" OR "sustainable" OR "ecological" OR "footprint" OR "environmental impact" OR "carbon emission" OR "greenhouse gas" OR "water consumption" OR "water usage" OR "lifecycle assessment" OR "LCA" OR "embodied carbon" OR "e-waste" OR "electronic waste" OR "material depletion" OR "resource consumption" OR "rare earth")
)
```

### IEEE Xplore

```
(
  ("Document Title":"high-performance computing" OR "Document Title":"supercomputing" OR "Document Title":"supercomputer" OR "Document Title":"HPC") OR
  ("Abstract":"high-performance computing" OR "Abstract":"supercomputing" OR "Abstract":"supercomputer" OR "Abstract":"HPC") OR
  ("Index Terms":"high-performance computing" OR "Index Terms":"supercomputing" OR "Index Terms":"supercomputer" OR "Index Terms":"HPC")
)
AND
(
  ("Document Title":"sustainability" OR "Document Title":"sustainable" OR "Document Title":"ecological" OR "Document Title":"footprint" OR "Document Title":"environmental impact" OR "Document Title":"carbon emission" OR "Document Title":"greenhouse gas" OR "Document Title":"water consumption" OR "Document Title":"water usage" OR "Document Title":"lifecycle assessment" OR "Document Title":"LCA" OR "Document Title":"embodied carbon" OR "Document Title":"e-waste" OR "Document Title":"electronic waste" OR "Document Title":"material depletion" OR "Document Title":"resource consumption" OR "Document Title":"rare earth") OR
  ("Abstract":"sustainability" OR "Abstract":"sustainable" OR "Abstract":"ecological" OR "Abstract":"footprint" OR "Abstract":"environmental impact" OR "Abstract":"carbon emission" OR "Abstract":"greenhouse gas" OR "Abstract":"water consumption" OR "Abstract":"water usage" OR "Abstract":"lifecycle assessment" OR "Abstract":"LCA" OR "Abstract":"embodied carbon" OR "Abstract":"e-waste" OR "Abstract":"electronic waste" OR "Abstract":"material depletion" OR "Abstract":"resource consumption" OR "Abstract":"rare earth") OR
  ("Index Terms":"sustainability" OR "Index Terms":"sustainable" OR "Index Terms":"ecological" OR "Index Terms":"footprint" OR "Index Terms":"environmental impact" OR "Index Terms":"carbon emission" OR "Index Terms":"greenhouse gas" OR "Index Terms":"water consumption" OR "Index Terms":"water usage" OR "Index Terms":"lifecycle assessment" OR "Index Terms":"LCA" OR "Index Terms":"embodied carbon" OR "Index Terms":"e-waste" OR "Index Terms":"electronic waste" OR "Index Terms":"material depletion" OR "Index Terms":"resource consumption" OR "Index Terms":"rare earth")
)
```

Bibtex files:

- ACM: `acm.bib`
- IEEE: `ieee.bib`
- Scopus: `scopus.bib`

## Results

| Database    | Papers found |
| -------- | ------- |
| ACM | 532 |
| IEEE | 1505 |
| Scopus | 2775 |

# Preprocessing

## Formatting the bibtex files

Tool: `bibtex-tidy`

Command: `bibtex-tidy --curly --numeric --sort --drop-all-caps --strip-enclosing-braces --sort-fields --strip-comments --remove-empty-fields --remove-dupe-fields`

### Scopus problem

Scopus bibtex file was badly formatted. What I did:

1. Fixed invalid citation keys that contained spaces.
    - Example: `Anirudh Bharadwaj20251052` -> `AnirudhBharadwaj20251052`

2. Fixed citation keys that started with digits by prefixing them with `ref`.
    - Example: `2025` -> `ref2025`

3. Fixed duplicate citation keys by appending numeric suffixes.
    - Example: repeated `Bahmani2025` entries became `Bahmani2025_2`, `Bahmani2025_3`, `Bahmani2025_4`

4. Converted accented and special characters in keys to ASCII so the keys are safer and more portable.
    - Examples:
        - `d’Onofrio2025` -> `dOnofrio2025`
        - `Gómez202412564` -> `Gomez202412564`
        - `Świętochowski2024` -> `Swietochowski2024`

5. Removed punctuation that can confuse BibTeX parsers when it appeared inside keys.
    - Examples:
        - `O'Hegarty2021` -> `OHegarty2021`
        - `D'Angelo2014` -> `DAngelo2014`

6. Removed embedded spaces from multi-word surnames in keys.
    - Examples:
        - `De Vita2026` -> `DeVita2026`
        - `Van Ho2025` -> `VanHo2025`
        - `Rajiv Gandhi20241833` -> `RajivGandhi20241833`

7. Fixed one malformed abstract with unbalanced braces in the `Zhang20079503` entry.
The broken fragment around `H(Pc...<sub>4</sub>}` was corrected to balanced braces: `H{Pc...<sub>4</sub>}`

## Removing duplicates

Merging the files: `cat acm.bib ieee.bib scopus.bib > papers.bib`

Command: `bibtex-tidy --duplicates --merge=first papers.bib`

## Results

| Stage | Number of papers |
| -------- | ------- |
| After the searches | 4812 |
| After removing duplicates | 3788 |
