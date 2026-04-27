# PRD: Rosetta P2 — Multi-Agent Drug Discovery Pipeline

## Introduction

Build the complete multi-agent orchestration layer (P2) for Rosetta: a lead researcher agent (Opus) dispatching specialist worker agents (Sonnet) against a shared SSOT to reproduce the validated Alzheimer's target discovery pipeline (55 → 3 targets). This PRD covers Sprints 2–8 from the implementation plan — SSOT MCP tools, external data MCPs, all worker agents, Docker compute, reporting, and end-to-end AD validation.

**Prerequisite (completed):** Sprint 1 — project scaffolding, SSOT schema + hypothesis graph, GWAS analysis port. 44/44 tests passing.

**Out of scope:** Porting analysis modules from the Alzheimer pipeline (`expression.py`, `mr.py`, `prioritization.py`, `spatial.py`). Those are separate work items. This PRD covers the agent/MCP/orchestration/Docker/reporting layer only.

## Goals

- Wire SSOT Python modules into MCP tool functions callable by agents
- Build MCP servers for external bioinformatics databases (GWAS Catalog, GEO/GTEx, eQTLGen, ChEMBL, CellxGene)
- Implement lead researcher agent with 6 encoded reasoning strategies
- Implement 7 worker agents (GWAS, Expression, MR, Confound, Druggability, Spatial, Reporter)
- Build Docker compute sandbox for heavy bioinformatics (R + Python)
- Build reporting system generating Jupyter notebooks with matplotlib/seaborn plots
- Validate end-to-end by reproducing the AD pipeline's INPP5D/MS4A6A/PICALM ranking

## User Stories

### US-001: Create SSOT MCP server tools
**Description:** As the lead agent, I need SSOT operations exposed as MCP tools so that I can read and write hypothesis graph state during orchestration.

**Acceptance Criteria:**
- [ ] `rosetta/ssot/tools.py` implements 11 `@tool` functions wrapping `hypothesis_graph`, `decision_log`, and `queue` modules
- [ ] `create_ssot_mcp_server()` returns `McpSdkServerConfig` with all 11 tools registered
- [ ] Tool names: `get_hypothesis_summary`, `get_frontier`, `create_hypothesis`, `update_confidence`, `kill_hypothesis`, `log_decision`, `propagate_evidence`, `check_kill_conditions`, `get_decision_diff`, `get_queue`, `enqueue_experiment`
- [ ] Each tool has typed parameters and returns structured text (not raw YAML)
- [ ] Tests in `tests/test_tools.py` cover all 11 tools
- [ ] `uv run pytest tests/` passes

### US-002: Build GWAS Catalog MCP server
**Description:** As the GWAS worker agent, I need to query the EBI GWAS Catalog REST API so that I can retrieve study metadata, significant associations, and summary statistics URLs.

**Acceptance Criteria:**
- [ ] `rosetta/mcp_servers/gwas_catalog.py` implements 3 tools: `search_studies`, `get_associations`, `get_summary_stats_url`
- [ ] `search_studies(query)` returns study accessions + metadata (title, trait, sample size, publication)
- [ ] `get_associations(study_accession)` returns significant SNPs + mapped genes + p-values
- [ ] `get_summary_stats_url(study_accession)` returns FTP download URL for full summary stats
- [ ] Tools wrap the EBI REST API (`https://www.ebi.ac.uk/gwas/rest/api/`)
- [ ] `create_gwas_catalog_mcp_server()` returns `McpSdkServerConfig`
- [ ] Tests with mocked HTTP responses in `tests/test_gwas_catalog_mcp.py`
- [ ] `uv run pytest tests/` passes

### US-003: Write lead researcher system prompt
**Description:** As a developer, I need the lead researcher's system prompt to encode the 6 validated reasoning strategies as explicit decision procedures so that the lead agent makes scientifically sound orchestration decisions.

**Acceptance Criteria:**
- [ ] `rosetta/prompts/lead.py` contains `LEAD_SYSTEM_PROMPT` string
- [ ] Prompt encodes all 6 reasoning strategies as numbered decision procedures: (1) orthogonal evidence filtration, (2) adaptive fallback on failure, (3) multiplicative convergence scoring, (4) adversarial self-critique, (5) cost-ordered evidence cascades, (6) theory-laden weighted integration
- [ ] Prompt specifies the lead's decision loop: read SSOT → check kill conditions → get frontier → select experiment → dispatch worker → interpret result → update hypotheses → log decision → repeat
- [ ] Prompt specifies kill condition checking protocol: hard kill, soft kill/demotion, conditional pivot
- [ ] Prompt includes the worker output contract expectation (summary verdict, data table, confidence metrics, quality flags, provenance)

### US-004: Write GWAS worker agent prompt
**Description:** As a developer, I need the GWAS triage worker's system prompt so that it knows how to query the GWAS Catalog, run analysis, and return structured results.

**Acceptance Criteria:**
- [ ] `rosetta/prompts/gwas_worker.py` contains `GWAS_WORKER_PROMPT` string
- [ ] Prompt instructs the worker to: query GWAS Catalog MCP for study + associations, run `rosetta.analysis.gwas` functions, write results to SSOT via tools
- [ ] Prompt specifies the output contract: summary verdict, gene list with pathway modules, significance thresholds, quality flags, provenance (study accession, N, date)
- [ ] Prompt includes domain guidance: LD clumping parameters, significance thresholds, amyloid vs non-amyloid classification

### US-005: Build agent definitions and orchestrator
**Description:** As a developer, I need the agent factory and orchestration loop so that the lead can dispatch workers and run the pipeline.

**Acceptance Criteria:**
- [ ] `rosetta/agents.py` implements `build_worker_agents()` returning `dict[str, AgentDefinition]`
- [ ] Initially includes GWAS worker only; other workers added in later stories
- [ ] Each `AgentDefinition` specifies: description, prompt, tools list, model ("sonnet")
- [ ] `rosetta/orchestrator.py` implements `run_pipeline(disease, initial_prompt)`:
  - Creates `ClaudeSDKClient` with SSOT MCP + data MCPs + worker agents
  - Bootstraps hypothesis graph with disease specification
  - Implements continuation loop: lead query → response → check for tool calls → continue until lead signals completion
- [ ] Orchestrator handles errors gracefully (API failures, worker timeouts)
- [ ] `uv run pytest tests/` passes

### US-006: MVP integration test — lead + GWAS worker + SSOT
**Description:** As a developer, I need to verify the full cycle works: lead bootstraps → dispatches GWAS worker → worker queries API + runs analysis → writes to SSOT → lead interprets → lead picks next experiment.

**Acceptance Criteria:**
- [ ] `tests/test_integration.py` runs a controlled integration test
- [ ] After the cycle: at least one hypothesis exists in `ssot/hypotheses/`
- [ ] After the cycle: at least one decision log entry exists in `ssot/decisions.jsonl`
- [ ] After the cycle: experiment queue has been populated
- [ ] Test can run with mocked API responses (no live GWAS Catalog calls required)
- [ ] `uv run pytest tests/` passes

### US-007: Build Docker compute sandbox
**Description:** As the expression and MR workers, I need a Docker container with R + Python + bioinformatics packages so that I can run DESeq2, TwoSampleMR, Scanpy, and Squidpy analyses.

**Acceptance Criteria:**
- [ ] `docker/Dockerfile` builds a fat image with: R 4.x, Bioconductor (DESeq2, TwoSampleMR, MRInstruments), Python 3.12 (scanpy, squidpy, scipy, statsmodels, pandas, numpy, matplotlib, seaborn)
- [ ] `docker/docker-compose.yml` defines a `rosetta-compute` service with host-mounted volume at `./ssot:/data/ssot`
- [ ] `docker/scripts/` contains executable analysis scripts callable via `docker exec`
- [ ] A helper function in `rosetta/` allows workers to execute commands in the container and retrieve results
- [ ] Container builds successfully: `docker compose build` completes without errors
- [ ] A smoke test script verifies R and Python packages load correctly inside the container

### US-008: Build GEO/GTEx MCP server
**Description:** As the expression worker, I need to search and retrieve transcriptomic datasets from GEO and GTEx so that I can run differential expression analysis.

**Acceptance Criteria:**
- [ ] `rosetta/mcp_servers/geo_gtex.py` implements tools: `search_geo_datasets(query, organism, tissue)`, `get_geo_metadata(accession)`, `get_gtex_expression(gene, tissue)`
- [ ] GEO tools wrap NCBI E-utilities API
- [ ] GTEx tools wrap GTEx Portal API
- [ ] `create_geo_gtex_mcp_server()` returns `McpSdkServerConfig`
- [ ] Tests with mocked HTTP responses
- [ ] `uv run pytest tests/` passes

### US-009: Write expression worker agent prompt and wire into agents.py
**Description:** As the lead agent, I need an expression worker that can run differential expression analysis and return convergence scores.

**Acceptance Criteria:**
- [ ] `rosetta/prompts/expression_worker.py` contains `EXPRESSION_WORKER_PROMPT`
- [ ] Prompt instructs worker to: select appropriate GEO dataset via MCP, run DE analysis via Docker compute, compute multiplicative convergence scores (GWAS x Expression), write results to SSOT
- [ ] Prompt specifies output contract: DE results table (gene, log2FC, padj), convergence scores, quality flags (sample size, tissue match), provenance
- [ ] Worker added to `build_worker_agents()` in `rosetta/agents.py`
- [ ] `uv run pytest tests/` passes

### US-010: Build eQTL MCP server (eQTLGen + GTEx eQTL)
**Description:** As the MR worker, I need to query eQTL databases to retrieve instrumental variables for Mendelian randomization analysis.

**Acceptance Criteria:**
- [ ] `rosetta/mcp_servers/eqtl.py` implements tools: `get_eqtlgen_instruments(gene)`, `get_gtex_eqtls(gene, tissue)`, `check_instrument_strength(snp_list)`
- [ ] eQTLGen tools wrap eQTLGen API for blood eQTLs (31K donors)
- [ ] GTEx tools wrap GTEx API for tissue-specific eQTLs
- [ ] `create_eqtl_mcp_server()` returns `McpSdkServerConfig`
- [ ] Tests with mocked HTTP responses
- [ ] `uv run pytest tests/` passes

### US-011: Write MR worker agent prompt and wire into agents.py
**Description:** As the lead agent, I need an MR/causality worker that can run Mendelian randomization analyses and return causal estimates with instrument diagnostics.

**Acceptance Criteria:**
- [ ] `rosetta/prompts/mr_worker.py` contains `MR_WORKER_PROMPT`
- [ ] Prompt instructs worker to: retrieve instruments from eQTL MCP, run MR analysis (IVW, Egger, weighted median) via Docker compute, return causal estimates with instrument diagnostics
- [ ] Prompt includes guidance on: minimum instrument count (≥3), F-statistic thresholds, handling power failure (flag to lead for adaptive fallback)
- [ ] Prompt specifies output contract: causal estimates per gene, instrument count, F-statistics, heterogeneity Q, MR-PRESSO outlier flags, provenance (eQTL source, N donors)
- [ ] Worker added to `build_worker_agents()` in `rosetta/agents.py`
- [ ] `uv run pytest tests/` passes

### US-012: Write confound test worker agent prompt and wire into agents.py
**Description:** As the lead agent, I need a confound worker that can test whether bulk DE results are composition artifacts using snRNA-seq data (adversarial self-critique strategy).

**Acceptance Criteria:**
- [ ] `rosetta/prompts/confound_worker.py` contains `CONFOUND_WORKER_PROMPT`
- [ ] Prompt instructs worker to: retrieve snRNA-seq dataset via CellxGene or GEO MCP, run cell-type deconvolution via Docker compute, classify each gene as per-cell vs composition-driven
- [ ] Prompt specifies output contract: per-gene classification (genuine per-cell DE vs composition artifact), cell-type proportions, quality flags, provenance
- [ ] Worker added to `build_worker_agents()` in `rosetta/agents.py`
- [ ] `uv run pytest tests/` passes

### US-013: Build ChEMBL MCP server
**Description:** As the druggability worker, I need to query ChEMBL for compound data, target classifications, and clinical trial status.

**Acceptance Criteria:**
- [ ] `rosetta/mcp_servers/chembl.py` implements tools: `search_target(gene_or_protein)`, `get_compounds(target_chembl_id)`, `get_clinical_status(compound_chembl_id)`, `get_target_classification(target_chembl_id)`
- [ ] Tools wrap ChEMBL REST API
- [ ] `create_chembl_mcp_server()` returns `McpSdkServerConfig`
- [ ] Tests with mocked HTTP responses
- [ ] `uv run pytest tests/` passes

### US-014: Write druggability worker agent prompt and wire into agents.py
**Description:** As the lead agent, I need a druggability worker that can assess target druggability, existing compound landscapes, and clinical development status.

**Acceptance Criteria:**
- [ ] `rosetta/prompts/druggability_worker.py` contains `DRUGGABILITY_WORKER_PROMPT`
- [ ] Prompt instructs worker to: query ChEMBL MCP for target class + compounds + clinical status, assess BBB penetration relevance, classify target druggability tier
- [ ] Prompt specifies output contract: target classification (enzyme, receptor, transporter, etc.), compound count, best-in-class compound, clinical stage, BBB-relevant flag, druggability score, provenance
- [ ] Worker added to `build_worker_agents()` in `rosetta/agents.py`
- [ ] `uv run pytest tests/` passes

### US-015: Write spatial validation worker agent prompt and wire into agents.py
**Description:** As the lead agent, I need a spatial worker that can validate target genes against spatial transcriptomics data for niche classification and co-localization.

**Acceptance Criteria:**
- [ ] `rosetta/prompts/spatial_worker.py` contains `SPATIAL_WORKER_PROMPT`
- [ ] Prompt instructs worker to: retrieve spatial dataset (MERFISH/Visium) via MCP or pre-registered data, run spatial analysis via Docker compute (Squidpy), classify genes by spatial niche, compute co-localization scores
- [ ] Prompt specifies output contract: per-gene niche assignment, co-localization scores, spatial enrichment p-values, quality flags, provenance (dataset, technology, cell count)
- [ ] Worker added to `build_worker_agents()` in `rosetta/agents.py`
- [ ] `uv run pytest tests/` passes

### US-016: Build reporting system
**Description:** As a researcher, I need automated reports generated from SSOT state so that I can inspect results with narrative, plots, and tiered target tables.

**Acceptance Criteria:**
- [ ] `rosetta/reporting/notebook_builder.py` implements `build_report(run_id, ssot_dir)` that programmatically constructs a Jupyter notebook
- [ ] Report includes sections: hypothesis graph visualization, evidence convergence heatmap, tiered target table, decision log timeline, per-phase summaries
- [ ] Report includes matplotlib/seaborn plots: Manhattan plot (if GWAS data available), forest plot (MR results), convergence heatmap, target tier bar chart
- [ ] `render_report(run_id)` converts notebook to HTML via nbconvert
- [ ] Output saved to `reports/<run_id>/report.ipynb`, `reports/<run_id>/report.html`, `reports/<run_id>/figures/`
- [ ] Tests verify notebook structure and figure generation with fixture data
- [ ] `uv run pytest tests/` passes

### US-017: Write reporter worker agent prompt and wire into agents.py
**Description:** As the lead agent, I need a reporter worker that can generate human-readable reports from SSOT state after each major phase or at pipeline completion.

**Acceptance Criteria:**
- [ ] `rosetta/prompts/reporter_worker.py` contains `REPORTER_WORKER_PROMPT`
- [ ] Prompt instructs worker to: read SSOT state, call `notebook_builder` functions, generate narrative summaries for each completed phase
- [ ] Worker added to `build_worker_agents()` in `rosetta/agents.py`
- [ ] `uv run pytest tests/` passes

### US-018: End-to-end AD pipeline validation
**Description:** As a developer, I need to run the full pipeline against the Alzheimer's disease use case and verify it reproduces the validated results.

**Acceptance Criteria:**
- [ ] End-to-end test script (or `tests/test_e2e_ad.py`) runs the full pipeline: GWAS triage → Expression → MR (brain, then blood fallback) → Confound → Scoring → Druggability → Spatial → Report
- [ ] Final tiered target list includes INPP5D, MS4A6A, and PICALM in top 3
- [ ] Lead autonomously makes the brain → blood eQTL pivot when brain eQTLs have insufficient instruments
- [ ] Decision log contains entries evidencing all 6 reasoning strategies
- [ ] Decision log contains rationale for the eQTL source pivot
- [ ] Report generated in `reports/` with plots and narrative
- [ ] Hypothesis graph contains appropriate kill/demotion/promotion decisions

## Functional Requirements

- FR-1: SSOT tool functions must wrap existing `hypothesis_graph`, `decision_log`, and `queue` modules — no duplicated logic
- FR-2: All MCP servers must return structured data with provenance metadata (source, version, access date)
- FR-3: MCP servers must handle API rate limits and transient failures with retries
- FR-4: Workers must write results to SSOT exclusively through tool functions, never raw YAML
- FR-5: Lead must never see raw hypothesis graph YAML — only pre-digested views from tool functions
- FR-6: Lead must check kill conditions after every worker result before proceeding
- FR-7: Lead must log every decision with rationale, evidence consulted, and alternatives considered
- FR-8: Docker container must be rebuildable from `docker/Dockerfile` with all dependencies pinned
- FR-9: Workers must execute bioinformatics compute via `docker exec` on the running container
- FR-10: Reporter must generate both `.ipynb` and `.html` output formats
- FR-11: Orchestrator continuation loop must handle: worker success, worker failure, lead-initiated pivot, lead-initiated kill, pipeline completion
- FR-12: Subagents must not spawn their own subagents (SDK constraint) — lead dispatches all workers directly
- FR-13: MCP tool names follow the SDK convention: `mcp__{server_key}__{tool_name}` in `allowed_tools`

## Non-Goals

- Porting analysis modules from Alzheimer pipeline (expression, MR, prioritization, spatial) — separate work
- P3 infrastructure agent (compute orchestration, cloud migration)
- P4 multi-disease generalization
- Live web UI or dashboard (future work that reads from SSOT)
- ClinicalTrials.gov integration (deferred to druggability v2)
- Literature MCP (PubMed, Semantic Scholar) — useful but not required for AD reproduction
- Proteomic MCPs (UniProt, PDB, AlphaFold) — P3 scope
- Automatic retry/resumption of interrupted pipeline runs
- User authentication or multi-tenancy

## Design Considerations

- Reuse existing `rosetta/ssot/schema.py` Pydantic models and `hypothesis_graph.py` DAG operations — tools.py is a thin wrapper
- Worker prompts should reference the analysis module function signatures so workers know what to call
- Docker image should be built once and cached; workers assume it's running
- Report notebook structure should be modular — each phase adds cells, so partial pipelines still produce useful reports

## Technical Considerations

- **Claude Agent SDK** (`claude-agent-sdk` v0.1.44+): `ClaudeSDKClient`, `AgentDefinition`, `@tool`, `create_sdk_mcp_server()`
- **SDK constraint**: subagents cannot spawn subagents; lead dispatches all workers via `Task` tool
- **MCP tool naming**: tools become `mcp__{server_key}__{tool_name}` in `allowed_tools`
- **Docker volume mount**: `./ssot:/data/ssot` for data exchange between host and container
- **External API dependencies**: EBI GWAS Catalog, NCBI E-utilities, GTEx Portal, eQTLGen, ChEMBL — all have rate limits
- **R dependency**: DESeq2 and TwoSampleMR require R + Bioconductor inside Docker (not host Python)
- **Notebook generation**: Use `nbformat` for programmatic notebook construction, `nbconvert` for HTML rendering
- **Test strategy**: Unit tests mock HTTP responses; integration tests mock the Claude API; E2E test requires live API keys

## Success Metrics

- All 44+ existing tests continue to pass (no regression)
- MVP integration test (US-006) completes a full lead → worker → SSOT cycle
- E2E AD validation (US-018) reproduces INPP5D/MS4A6A/PICALM in top 3 targets
- Lead autonomously pivots from brain to blood eQTLs without human intervention
- Decision log contains entries for all 6 reasoning strategies
- Generated report includes hypothesis graph visualization, tiered target table, and phase summaries
- Docker image builds in under 15 minutes and all bioinformatics packages load correctly

## Open Questions

- Should the GWAS Catalog MCP download full summary statistics files, or just return the URL for the infra layer to handle?
- What timeout should workers have before the lead considers them failed?
- Should the lead have a maximum number of orchestration cycles (to prevent infinite loops)?
- How should the system handle eQTLGen API access — it may require registration or bulk file download rather than a REST API?
- Should the confound worker use CellxGene API or assume pre-downloaded snRNA-seq data in the data registry?
- What is the target model for lead (opus-4 vs opus-4-6) and workers (sonnet-4 vs sonnet-4-6)?
