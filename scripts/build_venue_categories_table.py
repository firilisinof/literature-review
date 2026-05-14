"""Generate the appendix venue-category LaTeX table from merge.csv."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAPER_REPO = REPO.parent / "literature-review-paper"

MERGE_PATH = REPO / "artifacts" / "merge.csv"
OUTPUT_PATH = PAPER_REPO / "src" / "tables" / "venue-categories.tex"
CATEGORY_COLUMN_WIDTH = "4cm"

CATEGORY_ORDER = [
    "HPC Venues",
    "Parallel and Distributed Venues",
    "Other Venues",
]

CAPTION = (
    "Publication venue families in the final corpus, grouped by the venue "
    "categories used in Section~\\ref{sec:results}."
)

VENUE_ALIASES = {
    "2024 IEEE International Conference on Cluster Computing Workshops (CLUSTER Workshops)": (
        "IEEE International Conference on Cluster Computing Workshops (CLUSTER Workshops)"
    ),
    "2025 IEEE international symposium on performance analysis of systems and software (ISPASS)": (
        "IEEE International Symposium on Performance Analysis of Systems and Software (ISPASS)"
    ),
    "2025 IEEE/SBC 37th international symposium on computer architecture and high performance computing (SBAC-PAD)": (
        "IEEE/SBC International Symposium on Computer Architecture and High Performance Computing (SBAC-PAD)"
    ),
    "High performance computing: ISC high performance 2025 international workshops, hamburg, germany, june 10\u201313, 2025, revised selected papers": (
        "ISC High Performance"
    ),
    "International Conference for High Performance Computing, Networking, Storage and Analysis, SC": (
        "International Conference for High Performance Computing, Networking, Storage and Analysis (SC)"
    ),
    "ISC high performance 2024 research paper proceedings (39th international conference)": (
        "ISC High Performance"
    ),
    "PEARC '22: Practice and Experience in Advanced Research Computing": (
        "Practice and Experience in Advanced Research Computing (PEARC)"
    ),
    "Proceedings of the 2013 IEEE 19th international symposium on high performance computer architecture (HPCA)": (
        "IEEE International Symposium on High-Performance Computer Architecture (HPCA)"
    ),
    "Proceedings of the international conference for high performance computing, networking, storage and analysis": (
        "International Conference for High Performance Computing, Networking, Storage and Analysis (SC)"
    ),
    "Proceedings of the SC '24 workshops of the international conference on high performance computing, network, storage, and analysis": (
        "International Conference for High Performance Computing, Networking, Storage and Analysis (SC)"
    ),
    "Proceedings of the SC '25 workshops of the international conference for high performance computing, networking, storage and analysis": (
        "International Conference for High Performance Computing, Networking, Storage and Analysis (SC)"
    ),
    "SC '23: International Conference for High Performance Computing, Networking, Storage and Analysis": (
        "International Conference for High Performance Computing, Networking, Storage and Analysis (SC)"
    ),
    "SC-W 2023: Workshops of The International Conference on High Performance Computing, Network, Storage, and Analysis": (
        "International Conference for High Performance Computing, Networking, Storage and Analysis (SC)"
    ),
    "SC24: International Conference for High Performance Computing, Networking, Storage and Analysis": (
        "International Conference for High Performance Computing, Networking, Storage and Analysis (SC)"
    ),
    "Supercomputing: 10th russian supercomputing days, RuSCDays 2024, moscow, russia, september 23\u201324, 2024, revised selected papers, part I": (
        "Russian Supercomputing Days (RuSCDays)"
    ),
    "2024 32nd Euromicro International Conference on Parallel, Distributed and Network-Based Processing (PDP)": (
        "Euromicro International Conference on Parallel, Distributed, and Network-Based Processing (PDP)"
    ),
    "2025 33rd euromicro international conference on parallel, distributed, and network-based processing (PDP)": (
        "Euromicro International Conference on Parallel, Distributed, and Network-Based Processing (PDP)"
    ),
    "2025 IEEE 14th International Conference on Communication Systems and Network Technologies (CSNT)": (
        "IEEE International Conference on Communication Systems and Network Technologies (CSNT)"
    ),
    "International Symposium on Computer Networks and Distributed Systems (CNDS 2013)": (
        "International Symposium on Computer Networks and Distributed Systems (CNDS)"
    ),
    "Job scheduling strategies for parallel processing: 28th international workshop, JSSPP 2025, milan, italy, june 3\u20134, 2025, revised selected papers": (
        "Workshop on Job Scheduling Strategies for Parallel Processing (JSSPP)"
    ),
    "Proceedings of the 2025 ACM symposium on cloud computing": (
        "ACM Symposium on Cloud Computing"
    ),
    "Workshop Proceedings of the 48th International Conference on Parallel Processing": (
        "International Conference on Parallel Processing Workshops (ICPP Workshops)"
    ),
    "18th International Conference on Multi-disciplinary Trends in Artificial Intelligence (MIWAI 2025)": (
        "International Conference on Multi-disciplinary Trends in Artificial Intelligence (MIWAI)"
    ),
    "2010 14th International Heat Transfer Conference": (
        "International Heat Transfer Conference"
    ),
    "2023 IEEE John Vincent Atanasoff International Symposium on Modern Computing (JVA)": (
        "IEEE John Vincent Atanasoff International Symposium on Modern Computing (JVA)"
    ),
    "2025 11th international conference on ICT for sustainability (ICT4S)": (
        "International Conference on ICT for Sustainability (ICT4S)"
    ),
    "2025 24th IEEE Intersociety Conference on Thermal and Thermomechanical Phenomena in Electronic Systems (ITherm)": (
        "IEEE Intersociety Conference on Thermal and Thermomechanical Phenomena in Electronic Systems (ITherm)"
    ),
    "2025 IEEE 4th International Conference on Safe Production and Informatization (IICSPI)": (
        "IEEE International Conference on Safe Production and Informatization (IICSPI)"
    ),
    "3rd International Conference on Applied Physics, System Science and Computers (APSAC 2018)": (
        "International Conference on Applied Physics, System Science and Computers (APSAC)"
    ),
    "Faculty Publications and Other Works - Chemical and Biomolecular Engineering Publications": (
        "Faculty Publications and Other Works"
    ),
    "ICT for Sustainability 2014, ICT4S 2014": (
        "International Conference on ICT for Sustainability (ICT4S)"
    ),
    "Information Integration and Web Intelligence: 26th International Conference (iiWAS 2024)": (
        "International Conference on Information Integration and Web Intelligence (iiWAS)"
    ),
    "NREL technical report": "NREL Technical Reports",
    "Proceedings of the 2011 IEEE International Symposium on Sustainable Systems and Technology, ISSST 2011": (
        "IEEE International Symposium on Sustainable Systems and Technology (ISSST)"
    ),
}


def canonical_venue(value: str) -> str:
    return VENUE_ALIASES.get(value, value)


def escape_latex(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def load_venues() -> tuple[int, dict[str, set[str]]]:
    venues: dict[str, set[str]] = defaultdict(set)
    row_count = 0

    with MERGE_PATH.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            row_count += 1
            category = row["venue_type"].strip()
            venue = canonical_venue(row["venue"].strip())
            if category and venue:
                venues[category].add(venue)

    unexpected = sorted(set(venues) - set(CATEGORY_ORDER))
    missing = [category for category in CATEGORY_ORDER if category not in venues]
    if unexpected or missing:
        raise ValueError(
            "Unexpected venue categories in merge.csv. "
            f"unexpected={unexpected}; missing={missing}"
        )

    return row_count, venues


def build_table(venues: dict[str, set[str]]) -> str:
    lines = [
        "% Generated by literature-review/scripts/build_venue_categories_table.py",
        "% Do not edit by hand; rerun the script to refresh.",
        r"\begingroup",
        r"\small",
        r"\captionsetup{hypcap=false}",
        rf"\captionof{{table}}{{{CAPTION}}}\label{{tab:venue-categories}}",
        r"\vspace{0.5\baselineskip}",
        r"\setlength{\LTleft}{0pt}",
        r"\setlength{\LTright}{0pt}",
        (
            r"\begin{longtable}{@{}p{"
            f"{CATEGORY_COLUMN_WIDTH}"
            r"}@{\hspace{2\tabcolsep}}p{\dimexpr\linewidth-"
            f"{CATEGORY_COLUMN_WIDTH}"
            r"-2\tabcolsep\relax}@{}}"
        ),
        r"\toprule",
        r"\textbf{Category} & \textbf{Venue} \\",
        r"\midrule",
        r"\endfirsthead",
        r"\multicolumn{2}{l}{\footnotesize\itshape (continued from previous page)} \\",
        r"\toprule",
        r"\textbf{Category} & \textbf{Venue} \\",
        r"\midrule",
        r"\endhead",
        r"\midrule",
        r"\multicolumn{2}{r}{\footnotesize\itshape (continued on next page)} \\",
        r"\endfoot",
        r"\bottomrule",
        r"\endlastfoot",
    ]

    first_category = True
    for category in CATEGORY_ORDER:
        if not first_category:
            lines.append(r"\midrule")
        first_category = False

        for venue in sorted(venues[category], key=str.casefold):
            lines.append(f"{escape_latex(category)} & {escape_latex(venue)} \\\\")

    lines.extend([
        r"\end{longtable}",
        r"\endgroup",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    row_count, venues = load_venues()
    table = build_table(venues)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(table, encoding="utf-8")

    total_unique = sum(len(values) for values in venues.values())
    print(f"Read {row_count} rows from {MERGE_PATH.relative_to(REPO)}")
    print(f"Wrote {total_unique} venues to {OUTPUT_PATH.relative_to(PAPER_REPO.parent)}")
    for category in CATEGORY_ORDER:
        print(f"{category}: {len(venues[category])}")


if __name__ == "__main__":
    main()
