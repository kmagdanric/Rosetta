"""GWAS signal processing and pathway module classification.

Processes GWAS summary statistics:
- Extract genome-wide significant loci
- Classify risk genes into biological pathway modules
- Compute per-module statistics

Ported from the validated Alzheimer pipeline (Alzheimer/src/gwas_analysis.py).
PATHWAY_MODULES is now a parameter rather than a hardcoded constant.
"""

import numpy as np
import pandas as pd

# ============================================================
# Default AD Risk Gene Pathway Modules
# ============================================================
# Curated from Bellenguez 2022, Wightman 2021, Jansen 2019, Kunkle 2019

DEFAULT_AD_PATHWAY_MODULES: dict[str, list[str]] = {
    "Amyloid Processing": [
        "APP", "PSEN1", "PSEN2", "BACE1", "ADAM10", "APH1B", "NCSTN",
    ],
    "Tau / Cytoskeleton": [
        "MAPT", "FERMT2", "CELF1", "BIN1", "KANSL1", "NSF",
        "FMNL2", "SPPL2A",
    ],
    "Microglia / Innate Immunity": [
        "TREM2", "CD33", "MS4A4A", "MS4A6A", "MS4A4E", "MS4A2",
        "INPP5D", "ABI3", "PLCG2", "SPI1", "LILRB5",
        "SCIMP", "PILRA", "SIGLEC11", "TSPAN14",
        "GRN", "TYROBP", "HLA-DRB1", "HLA-DRB5",
        "EPHA1", "MEF2C", "IKZF1",
    ],
    "Lipid Metabolism": [
        "APOE", "CLU", "ABCA7", "ABCA1", "APOC1", "APOC2",
        "SOAT1", "OSBPL6", "HESX1", "BLNK",
        "TRIB1", "WWOX",
    ],
    "Endolysosomal Trafficking": [
        "BIN1", "PICALM", "SORL1", "CD2AP", "RIN3",
        "SNX1", "WDR81", "GRN", "TMEM106B",
        "AP4E1", "AP4M1", "SORT1",
    ],
    "Synaptic Function": [
        "ICA1", "ICA1L", "DOC2A", "DGKQ", "PTK2B",
        "ZCWPW1", "ECHDC3", "NCALD",
        "LIME1", "SHARPIN",
    ],
    "Complement System": [
        "C4A", "C4B", "CR1", "C3", "CLU", "C1S",
        "CFHR1", "CFH",
    ],
    "Vascular / BBB": [
        "ACE", "NOTCH3", "COL4A1", "COL4A2",
        "HBEGF", "ADAMTS4", "FLT1",
    ],
}

# All known AD risk genes with approximate genomic positions (GRCh38)
AD_RISK_GENES_POSITIONS: dict[str, dict[str, str | int]] = {
    # Amyloid
    "APP": {"chr": "21", "pos": 25880550},
    "PSEN1": {"chr": "14", "pos": 73136418},
    "PSEN2": {"chr": "1", "pos": 226870594},
    "ADAM10": {"chr": "15", "pos": 58700079},
    "APH1B": {"chr": "15", "pos": 63276248},
    # Tau
    "MAPT": {"chr": "17", "pos": 45894382},
    "FERMT2": {"chr": "14", "pos": 52924962},
    "CELF1": {"chr": "11", "pos": 47571198},
    "KANSL1": {"chr": "17", "pos": 46058285},
    # Microglia / Immunity
    "TREM2": {"chr": "6", "pos": 41126742},
    "CD33": {"chr": "19", "pos": 51225574},
    "MS4A4A": {"chr": "11", "pos": 60219012},
    "MS4A6A": {"chr": "11", "pos": 60154318},
    "INPP5D": {"chr": "2", "pos": 233098413},
    "ABI3": {"chr": "17", "pos": 49217694},
    "PLCG2": {"chr": "16", "pos": 81751851},
    "SPI1": {"chr": "11", "pos": 47376409},
    "PILRA": {"chr": "7", "pos": 100348164},
    "EPHA1": {"chr": "7", "pos": 143383055},
    "MEF2C": {"chr": "5", "pos": 88717117},
    "IKZF1": {"chr": "7", "pos": 50304837},
    "GRN": {"chr": "17", "pos": 44345086},
    "HLA-DRB1": {"chr": "6", "pos": 32546547},
    # Lipid
    "APOE": {"chr": "19", "pos": 44905796},
    "CLU": {"chr": "8", "pos": 27454414},
    "ABCA7": {"chr": "19", "pos": 1040101},
    "ABCA1": {"chr": "9", "pos": 104903678},
    "APOC1": {"chr": "19", "pos": 44912383},
    "SOAT1": {"chr": "1", "pos": 179150949},
    "TRIB1": {"chr": "8", "pos": 125461846},
    "WWOX": {"chr": "16", "pos": 78099398},
    # Endolysosomal
    "BIN1": {"chr": "2", "pos": 127048200},
    "PICALM": {"chr": "11", "pos": 85957684},
    "SORL1": {"chr": "11", "pos": 121322891},
    "CD2AP": {"chr": "6", "pos": 47445035},
    "RIN3": {"chr": "14", "pos": 92536833},
    "SNX1": {"chr": "15", "pos": 64122625},
    "WDR81": {"chr": "17", "pos": 1746698},
    "TMEM106B": {"chr": "7", "pos": 12229894},
    # Synaptic
    "ICA1": {"chr": "7", "pos": 8084977},
    "ICA1L": {"chr": "2", "pos": 203394030},
    "DOC2A": {"chr": "16", "pos": 29945775},
    "DGKQ": {"chr": "4", "pos": 961893},
    "PTK2B": {"chr": "8", "pos": 27168698},
    "NCALD": {"chr": "8", "pos": 101511381},
    # Complement
    "CR1": {"chr": "1", "pos": 207496157},
    "C4A": {"chr": "6", "pos": 31949833},
    "CFH": {"chr": "1", "pos": 196621008},
    # Vascular
    "ACE": {"chr": "17", "pos": 63477061},
    "ADAMTS4": {"chr": "1", "pos": 161141943},
    # Other well-known
    "TREML2": {"chr": "6", "pos": 41163186},
    "SCIMP": {"chr": "17", "pos": 5205967},
    "SPPL2A": {"chr": "15", "pos": 50711875},
    "NSF": {"chr": "17", "pos": 46573059},
    "SORT1": {"chr": "1", "pos": 109274971},
}

# Non-amyloid biomarker proteins of interest
NON_AMYLOID_BIOMARKERS = [
    "SMOC1", "GPNMB", "MDK", "VGF", "NPTX2",
    "NEFL", "GFAP", "VILIP1", "sTREM2", "YKL40",
]

# Significance thresholds
GWS_THRESHOLD = 5e-8
SUGGESTIVE_THRESHOLD = 1e-5


def build_gene_to_module_map(
    pathway_modules: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Build a gene -> module(s) lookup from pathway module definitions.

    Parameters
    ----------
    pathway_modules : dict, optional
        Mapping of module name to gene list. Defaults to AD modules.

    Returns
    -------
    dict mapping gene symbol to list of module names.
    """
    if pathway_modules is None:
        pathway_modules = DEFAULT_AD_PATHWAY_MODULES

    gene_to_module: dict[str, list[str]] = {}
    for module, genes in pathway_modules.items():
        for gene in genes:
            gene_to_module.setdefault(gene, []).append(module)
    return gene_to_module


def extract_significant_loci(
    gwas_df: pd.DataFrame,
    pvalue_col: str = "pvalue",
    threshold: float = GWS_THRESHOLD,
) -> pd.DataFrame:
    """Extract genome-wide significant loci from GWAS summary stats.

    Parameters
    ----------
    gwas_df : pd.DataFrame
        GWAS summary statistics.
    pvalue_col : str
        Column name for p-values.
    threshold : float
        Significance threshold (default: 5e-8).

    Returns
    -------
    pd.DataFrame of significant SNPs, sorted by p-value.
    """
    sig = gwas_df[gwas_df[pvalue_col] < threshold].copy()
    sig = sig.sort_values(pvalue_col)
    return sig


def clump_loci(
    sig_df: pd.DataFrame,
    chr_col: str = "chr",
    pos_col: str = "pos",
    pvalue_col: str = "pvalue",
    window_kb: int = 500,
) -> pd.DataFrame:
    """Simple LD-naive clumping: keep lead SNP per locus (distance-based).

    Groups SNPs within `window_kb` kilobases and keeps the most significant.

    Parameters
    ----------
    sig_df : pd.DataFrame
        Significant SNPs (pre-filtered).
    window_kb : int
        Clumping window in kilobases.

    Returns
    -------
    pd.DataFrame of lead SNPs per independent locus.
    """
    if sig_df.empty:
        return sig_df

    df = sig_df.sort_values(pvalue_col).copy()
    window_bp = window_kb * 1000
    leads = []
    used: set = set()

    for idx, row in df.iterrows():
        if idx in used:
            continue
        leads.append(row)
        same_chr = df[df[chr_col] == row[chr_col]]
        nearby = same_chr[abs(same_chr[pos_col] - row[pos_col]) < window_bp]
        used.update(nearby.index)

    result = pd.DataFrame(leads)
    return result


def classify_genes_to_modules(
    genes: list[str],
    pathway_modules: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """Classify a list of genes into pathway modules.

    Parameters
    ----------
    genes : list of str
        Gene symbols.
    pathway_modules : dict, optional
        Module definitions. Defaults to AD pathway modules.

    Returns
    -------
    pd.DataFrame with columns: gene, modules, is_amyloid, primary_module
    """
    gene_to_module = build_gene_to_module_map(pathway_modules)

    records = []
    for gene in genes:
        modules = gene_to_module.get(gene, ["Unclassified"])
        is_amyloid = "Amyloid Processing" in modules
        primary = modules[0] if modules else "Unclassified"
        records.append(
            {
                "gene": gene,
                "modules": modules,
                "primary_module": primary,
                "is_amyloid": is_amyloid,
            }
        )
    return pd.DataFrame(records)


def compute_module_statistics(
    classified_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute summary statistics per pathway module.

    Parameters
    ----------
    classified_df : pd.DataFrame
        Output of classify_genes_to_modules().

    Returns
    -------
    pd.DataFrame with columns: module, gene_count, fraction, genes
    """
    rows = []
    for _, row in classified_df.iterrows():
        for mod in row["modules"]:
            rows.append({"gene": row["gene"], "module": mod})
    exploded = pd.DataFrame(rows)

    stats = (
        exploded.groupby("module")
        .agg(gene_count=("gene", "nunique"), genes=("gene", lambda x: sorted(set(x))))
        .reset_index()
    )
    total = classified_df["gene"].nunique()
    stats["fraction"] = stats["gene_count"] / total
    stats = stats.sort_values("gene_count", ascending=False)

    return stats


def compute_amyloid_vs_nonamyloid(classified_df: pd.DataFrame) -> dict:
    """Compute the fraction of risk genes in amyloid vs. non-amyloid modules.

    Returns
    -------
    dict with keys: n_amyloid, n_nonamyloid, n_total, frac_amyloid, frac_nonamyloid
    """
    total = len(classified_df)
    n_amyloid = classified_df["is_amyloid"].sum()
    n_nonamyloid = total - n_amyloid

    return {
        "n_amyloid": int(n_amyloid),
        "n_nonamyloid": int(n_nonamyloid),
        "n_total": total,
        "frac_amyloid": n_amyloid / total if total > 0 else 0,
        "frac_nonamyloid": n_nonamyloid / total if total > 0 else 0,
    }


def compute_risk_contribution_by_module(
    gwas_df: pd.DataFrame,
    classified_df: pd.DataFrame,
    gene_col: str = "nearest_gene",
    beta_col: str = "beta",
) -> pd.DataFrame:
    """Estimate genetic risk contribution per module using effect sizes.

    Sums absolute beta values per module as a proxy for genetic risk.

    Returns
    -------
    pd.DataFrame with columns: module, total_abs_beta, n_loci, mean_abs_beta
    """
    merged = gwas_df.merge(
        classified_df, left_on=gene_col, right_on="gene", how="inner"
    )

    rows = []
    for _, r in merged.iterrows():
        for mod in r["modules"]:
            rows.append({"module": mod, "abs_beta": abs(r[beta_col])})

    if not rows:
        return pd.DataFrame(columns=["module", "total_abs_beta", "n_loci", "mean_abs_beta"])

    exploded = pd.DataFrame(rows)
    stats = (
        exploded.groupby("module")
        .agg(
            total_abs_beta=("abs_beta", "sum"),
            n_loci=("abs_beta", "count"),
            mean_abs_beta=("abs_beta", "mean"),
        )
        .reset_index()
        .sort_values("total_abs_beta", ascending=False)
    )
    return stats
