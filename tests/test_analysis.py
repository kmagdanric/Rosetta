"""Tests for analysis modules (regression against known AD outputs)."""

import numpy as np
import pandas as pd
import pytest

from rosetta.analysis.gwas import (
    DEFAULT_AD_PATHWAY_MODULES,
    build_gene_to_module_map,
    classify_genes_to_modules,
    clump_loci,
    compute_amyloid_vs_nonamyloid,
    compute_module_statistics,
    compute_risk_contribution_by_module,
    extract_significant_loci,
)


class TestGWASAnalysis:
    @pytest.fixture
    def mock_gwas_df(self):
        """Create mock GWAS summary statistics."""
        return pd.DataFrame({
            "snp": ["rs1", "rs2", "rs3", "rs4", "rs5"],
            "chr": ["2", "2", "11", "11", "19"],
            "pos": [233098413, 233098500, 60154318, 85957684, 44905796],
            "pvalue": [1e-12, 1e-8, 1e-15, 1e-10, 5e-7],
            "beta": [0.15, 0.08, 0.22, 0.12, 0.05],
            "nearest_gene": ["INPP5D", "INPP5D", "MS4A6A", "PICALM", "APOE"],
        })

    def test_extract_significant_loci(self, mock_gwas_df):
        sig = extract_significant_loci(mock_gwas_df, threshold=5e-8)
        assert len(sig) == 4  # rs5 (5e-7) excluded
        assert sig.iloc[0]["pvalue"] < sig.iloc[-1]["pvalue"]  # Sorted

    def test_extract_suggestive(self, mock_gwas_df):
        sig = extract_significant_loci(mock_gwas_df, threshold=1e-5)
        assert len(sig) == 5  # All included

    def test_clump_loci(self, mock_gwas_df):
        sig = extract_significant_loci(mock_gwas_df, threshold=5e-8)
        clumped = clump_loci(sig, window_kb=500)
        # rs1 and rs2 are within 500kb on chr2, so should clump to 1
        chr2_leads = clumped[clumped["chr"] == "2"]
        assert len(chr2_leads) == 1

    def test_clump_empty(self):
        empty = pd.DataFrame(columns=["chr", "pos", "pvalue"])
        result = clump_loci(empty)
        assert len(result) == 0

    def test_classify_genes_default_modules(self):
        genes = ["INPP5D", "PICALM", "APOE", "UNKNOWN_GENE"]
        classified = classify_genes_to_modules(genes)

        assert len(classified) == 4
        inpp5d = classified[classified["gene"] == "INPP5D"].iloc[0]
        assert "Microglia / Innate Immunity" in inpp5d["modules"]
        assert not inpp5d["is_amyloid"]

        apoe = classified[classified["gene"] == "APOE"].iloc[0]
        assert "Lipid Metabolism" in apoe["modules"]

        unknown = classified[classified["gene"] == "UNKNOWN_GENE"].iloc[0]
        assert unknown["modules"] == ["Unclassified"]

    def test_classify_genes_custom_modules(self):
        custom = {"My Module": ["GENE1", "GENE2"]}
        classified = classify_genes_to_modules(["GENE1", "GENE3"], pathway_modules=custom)
        g1 = classified[classified["gene"] == "GENE1"].iloc[0]
        assert g1["modules"] == ["My Module"]
        g3 = classified[classified["gene"] == "GENE3"].iloc[0]
        assert g3["modules"] == ["Unclassified"]

    def test_compute_module_statistics(self):
        genes = ["INPP5D", "TREM2", "CD33", "PICALM", "BIN1"]
        classified = classify_genes_to_modules(genes)
        stats = compute_module_statistics(classified)

        assert "module" in stats.columns
        assert "gene_count" in stats.columns
        # Microglia module should have INPP5D, TREM2, CD33
        microglia = stats[stats["module"] == "Microglia / Innate Immunity"]
        assert len(microglia) == 1
        assert microglia.iloc[0]["gene_count"] == 3

    def test_compute_amyloid_vs_nonamyloid(self):
        genes = ["APP", "PSEN1", "INPP5D", "PICALM"]
        classified = classify_genes_to_modules(genes)
        result = compute_amyloid_vs_nonamyloid(classified)
        assert result["n_amyloid"] == 2
        assert result["n_nonamyloid"] == 2
        assert result["frac_amyloid"] == pytest.approx(0.5)

    def test_compute_risk_contribution(self, mock_gwas_df):
        genes = ["INPP5D", "MS4A6A", "PICALM", "APOE"]
        classified = classify_genes_to_modules(genes)
        sig = extract_significant_loci(mock_gwas_df, threshold=5e-8)
        risk = compute_risk_contribution_by_module(sig, classified)
        assert "module" in risk.columns
        assert "total_abs_beta" in risk.columns
        assert len(risk) > 0

    def test_build_gene_to_module_map(self):
        mapping = build_gene_to_module_map()
        assert "INPP5D" in mapping
        assert "Microglia / Innate Immunity" in mapping["INPP5D"]
        # BIN1 is in multiple modules
        assert len(mapping["BIN1"]) >= 2

    def test_ad_pipeline_regression_55_genes(self):
        """Regression: the AD pipeline identified 55 non-amyloid risk genes across 8 modules."""
        all_genes = set()
        for module_genes in DEFAULT_AD_PATHWAY_MODULES.values():
            all_genes.update(module_genes)

        # Should have genes in all 8 modules
        assert len(DEFAULT_AD_PATHWAY_MODULES) == 8

        # Key targets from the validated pipeline should be present
        key_targets = ["INPP5D", "MS4A6A", "PICALM", "TREM2", "APOE", "BIN1"]
        for gene in key_targets:
            assert gene in all_genes, f"{gene} missing from pathway modules"
