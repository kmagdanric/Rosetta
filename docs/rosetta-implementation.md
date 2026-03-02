Rosetta: Multi-Agent Drug Discovery System — Implementation Plan                                                                   │
│                                                                                                                                    │
│ Context                                                                                                                            │
│                                                                                                                                    │
│ Building a multi-agent system for drug discovery using the Claude Agent SDK (Python). A lead researcher agent (Opus) orchestrates  │
│ specialist worker agents (Sonnet) against a shared Single Source of Truth (SSOT). The architecture is based on a validated         │
│ Alzheimer's pipeline (55 → 3 targets, 2 days) from /Users/joseph/programming/kmagdanric/Alzheimer.                                 │
│                                                                                                                                    │
│ Design decisions are documented in /Users/joseph/programming/kmagdanric/Rosetta/docs/clarify.md.                                   │
│                                                                                                                                    │
│ ---                                                                                                                                │
│ Project Structure                                                                                                                  │
│                                                                                                                                    │
│ Rosetta/                                                                                                                           │
│   rosetta/                             # Main Python package                                                                       │
│     __init__.py                                                                                                                    │
│     orchestrator.py                    # Lead researcher: ClaudeSDKClient main loop                                                │
│     agents.py                          # AgentDefinition factories for all workers                                                 │
│     prompts/                                                                                                                       │
│       __init__.py                                                                                                                  │
│       lead.py                          # Lead system prompt (6 reasoning strategies)                                               │
│       gwas_worker.py                   # GWAS triage worker prompt                                                                 │
│       expression_worker.py                                                                                                         │
│       mr_worker.py                                                                                                                 │
│       confound_worker.py                                                                                                           │
│       druggability_worker.py                                                                                                       │
│       spatial_worker.py                                                                                                            │
│       reporter_worker.py                                                                                                           │
│                                                                                                                                    │
│     ssot/                              # SSOT Python layer                                                                         │
│       __init__.py                                                                                                                  │
│       schema.py                        # Pydantic models: Hypothesis, Evidence, Edge, KillCondition                                │
│       hypothesis_graph.py              # DAG ops: create, update, kill, propagate, frontier, index                                 │
│       decision_log.py                  # JSONL append-only log                                                                     │
│       queue.py                         # Experiment queue                                                                          │
│       tools.py                         # @tool definitions → create_ssot_mcp_server()                                              │
│                                                                                                                                    │
│     analysis/                          # Ported from Alzheimer (pure Python, no agent coupling)                                    │
│       __init__.py                                                                                                                  │
│       gwas.py                          # From src/gwas_analysis.py                                                                 │
│       expression.py                    # From src/expression_analysis.py                                                           │
│       mr.py                            # From src/mr_analysis.py                                                                   │
│       prioritization.py                # From src/target_prioritization.py                                                         │
│       spatial.py                       # From src/spatial_analysis.py                                                              │
│                                                                                                                                    │
│     mcp_servers/                       # External data source MCP wrappers                                                         │
│       __init__.py                                                                                                                  │
│       gwas_catalog.py                  # GWAS Catalog REST API                                                                     │
│                                                                                                                                    │
│     reporting/                                                                                                                     │
│       __init__.py                                                                                                                  │
│       notebook_builder.py              # Programmatic Jupyter notebook construction                                                │
│                                                                                                                                    │
│   ssot/                                # Runtime SSOT data (gitignored except schema examples)                                     │
│     hypotheses/                                                                                                                    │
│     data_registry/                                                                                                                 │
│     decisions.jsonl                                                                                                                │
│     queue.yaml                                                                                                                     │
│                                                                                                                                    │
│   reports/                             # Generated reports (<run_id>/report.ipynb, .html, figures/)                                │
│   docker/                                                                                                                          │
│     Dockerfile                         # Fat bioinformatics image (R + Python)                                                     │
│     docker-compose.yml                                                                                                             │
│     scripts/                           # Analysis scripts callable via docker exec                                                 │
│   tests/                                                                                                                           │
│     conftest.py                                                                                                                    │
│     test_ssot.py                                                                                                                   │
│     test_hypothesis_graph.py                                                                                                       │
│     test_analysis.py                                                                                                               │
│     test_tools.py                                                                                                                  │
│     fixtures/                                                                                                                      │
│                                                                                                                                    │
│   pyproject.toml                                                                                                                   │
│   CLAUDE.md                                                                                                                        │
│   .env.example                                                                                                                     │
│   .gitignore                                                                                                                       │
│                                                                                                                                    │
│ ---                                                                                                                                │
│ Architecture → SDK Mapping                                                                                                         │
│                                                                                                                                    │
│ ┌────────────────────────┬────────────────────────────────────────────────────────────┐                                            │
│ │   Architecture Layer   │                     SDK Implementation                     │                                            │
│ ├────────────────────────┼────────────────────────────────────────────────────────────┤                                            │
│ │ Lead Researcher (Opus) │ ClaudeSDKClient with multi-turn conversation loop          │                                            │
│ ├────────────────────────┼────────────────────────────────────────────────────────────┤                                            │
│ │ Worker Agents (Sonnet) │ AgentDefinition instances, dispatched via Task tool        │                                            │
│ ├────────────────────────┼────────────────────────────────────────────────────────────┤                                            │
│ │ SSOT tools             │ @tool decorator → create_sdk_mcp_server() (in-process MCP) │                                            │
│ ├────────────────────────┼────────────────────────────────────────────────────────────┤                                            │
│ │ External data MCPs     │ create_sdk_mcp_server() per data source                    │                                            │
│ ├────────────────────────┼────────────────────────────────────────────────────────────┤                                            │
│ │ Compute sandbox        │ Docker container, workers call via Bash tool               │                                            │
│ └────────────────────────┴────────────────────────────────────────────────────────────┘                                            │
│                                                                                                                                    │
│ Key SDK constraints:                                                                                                               │
│ - Subagents cannot spawn their own subagents — lead dispatches all workers directly                                                │
│ - Custom tools are implemented as in-process MCP servers via create_sdk_mcp_server()                                               │
│ - Workers share the same filesystem as the lead (host-mounted volumes for Docker)                                                  │
│                                                                                                                                    │
│ ---                                                                                                                                │
│ Implementation Order                                                                                                               │
│                                                                                                                                    │
│ Sprint 1: Foundation (SSOT + Analysis Port)                                                                                        │
│                                                                                                                                    │
│ Step 1a: Project scaffolding                                                                                                       │
│ - pyproject.toml (uv, Python 3.12, deps: claude-agent-sdk, pyyaml, pydantic)                                                       │
│ - .gitignore, .env.example, CLAUDE.md                                                                                              │
│ - Package structure: rosetta/__init__.py and all subpackages                                                                       │
│                                                                                                                                    │
│ Step 1b: SSOT schema + hypothesis graph — no dependencies                                                                          │
│ - rosetta/ssot/schema.py — Pydantic models: Hypothesis, Evidence, Edge, KillCondition                                              │
│ - rosetta/ssot/hypothesis_graph.py — Core DAG ops:                                                                                 │
│   - create_hypothesis(), load_hypothesis(), save_hypothesis()                                                                      │
│   - update_confidence(), kill_hypothesis()                                                                                         │
│   - propagate_evidence() — cascade through DAG edges                                                                               │
│   - get_hypothesis_summary() — pre-digested text for the lead (NOT raw YAML)                                                       │
│   - get_frontier() — ranked by uncertainty × impact                                                                                │
│   - check_kill_conditions() — scan all active hypotheses                                                                           │
│   - regenerate_index() — auto-generate _index.yaml                                                                                 │
│ - rosetta/ssot/decision_log.py — JSONL append-only: log_decision()                                                                 │
│ - rosetta/ssot/queue.py — enqueue_experiment(), dequeue_experiment()                                                               │
│ - Tests: tests/test_ssot.py, tests/test_hypothesis_graph.py                                                                        │
│                                                                                                                                    │
│ Step 1c: Port GWAS analysis — parallel with 1b                                                                                     │
│ - rosetta/analysis/gwas.py — copy from Alzheimer/src/gwas_analysis.py                                                              │
│ - Refactor: make PATHWAY_MODULES a parameter instead of hardcoded constant                                                         │
│ - Keep: extract_significant_loci(), clump_loci(), classify_genes_to_modules(), compute_module_statistics()                         │
│ - Test: regression test against known AD outputs                                                                                   │
│                                                                                                                                    │
│ Sprint 2: SSOT Tools + First Agent Wiring                                                                                          │
│                                                                                                                                    │
│ Step 2a: SSOT MCP server — depends on 1b                                                                                           │
│ - rosetta/ssot/tools.py — 11 @tool functions wrapping hypothesis_graph + decision_log + queue                                      │
│ - create_ssot_mcp_server() returns McpSdkServerConfig                                                                              │
│ - Tool names: get_hypothesis_summary, get_frontier, create_hypothesis, update_confidence, kill_hypothesis, log_decision,           │
│ propagate_evidence, check_kill_conditions, get_decision_diff, get_queue, enqueue_experiment                                        │
│                                                                                                                                    │
│ Step 2b: GWAS Catalog MCP — no dependencies                                                                                        │
│ - rosetta/mcp_servers/gwas_catalog.py — 3 tools wrapping EBI REST API:                                                             │
│   - search_studies(query) → study accessions + metadata                                                                            │
│   - get_associations(study_accession) → significant SNPs + genes                                                                   │
│   - get_summary_stats_url(study_accession) → FTP download URL                                                                      │
│                                                                                                                                    │
│ Step 2c: GWAS worker agent + lead skeleton — depends on 2a, 2b                                                                     │
│ - rosetta/prompts/gwas_worker.py — worker prompt with domain instructions                                                          │
│ - rosetta/prompts/lead.py — lead system prompt encoding 6 reasoning strategies + decision protocol                                 │
│ - rosetta/agents.py — build_worker_agents() returning dict[str, AgentDefinition] (GWAS only initially)                             │
│ - rosetta/orchestrator.py — run_pipeline():                                                                                        │
│   - Creates ClaudeSDKClient with SSOT MCP + GWAS MCP + worker agents                                                               │
│   - Bootstraps hypothesis graph with initial prompt                                                                                │
│   - Implements continuation loop: after each result, prompt lead to check kill conditions → get frontier → dispatch next worker    │
│                                                                                                                                    │
│ Sprint 3: MVP Integration Test                                                                                                     │
│                                                                                                                                    │
│ - Wire everything: lead + SSOT tools + GWAS worker + GWAS Catalog MCP                                                              │
│ - Run full cycle: lead bootstraps → dispatches GWAS worker → worker queries API + runs analysis → writes to SSOT → lead interprets │
│  → lead picks next experiment                                                                                                      │
│ - Success criterion: hypotheses created in ssot/hypotheses/, decision log populated                                                │
│                                                                                                                                    │
│ Sprint 4: Expression Phase                                                                                                         │
│                                                                                                                                    │
│ - Port rosetta/analysis/expression.py from Alzheimer/src/expression_analysis.py                                                    │
│ - rosetta/prompts/expression_worker.py + add to agents.py                                                                          │
│ - Docker setup: docker/Dockerfile (R + Python + DESeq2 + scanpy), docker-compose.yml                                               │
│ - Worker runs DE analysis via docker exec + Bash tool                                                                              │
│                                                                                                                                    │
│ Sprint 5: MR + Integrated Scoring                                                                                                  │
│                                                                                                                                    │
│ - Port rosetta/analysis/mr.py (IVW, Egger, weighted median, MR-PRESSO)                                                             │
│ - Port rosetta/analysis/prioritization.py (weighted multiplicative scoring)                                                        │
│ - MR worker agent + prompt                                                                                                         │
│ - eQTL MCP server (eQTLGen + GTEx access)                                                                                          │
│                                                                                                                                    │
│ Sprint 6: Adversarial Testing + Extended MR                                                                                        │
│                                                                                                                                    │
│ - Confound test worker (Phase 5 — snRNA-seq composition artifact check)                                                            │
│ - Extended MR with blood eQTLs (Phase 6 — adaptive fallback test)                                                                  │
│ - Key validation: lead correctly pivots from brain → blood eQTLs                                                                   │
│                                                                                                                                    │
│ Sprint 7: Drug Landscape + Spatial + Reports                                                                                       │
│                                                                                                                                    │
│ - Druggability worker + ChEMBL MCP                                                                                                 │
│ - Spatial worker                                                                                                                   │
│ - Reporter worker + rosetta/reporting/notebook_builder.py                                                                          │
│                                                                                                                                    │
│ Sprint 8: Full AD Pipeline Validation                                                                                              │
│                                                                                                                                    │
│ - End-to-end run reproducing the validated pipeline                                                                                │
│ - Success criteria: reproduces INPP5D/MS4A6A/PICALM ranking, lead makes correct brain→blood eQTL pivot autonomously                │
│ - Decision log audit: verify all 6 reasoning strategies appear                                                                     │
│                                                                                                                                    │
│ ---                                                                                                                                │
│ Key Design Decisions                                                                                                               │
│                                                                                                                                    │
│ 1. ClaudeSDKClient for lead (not query()) — lead needs multi-turn conversation with state across the full pipeline                 │
│ 2. In-process MCP servers for SSOT and data tools — SDK's recommended pattern via @tool + create_sdk_mcp_server()                  │
│ 3. Workers write via SSOT tools (not raw YAML) — tool layer enforces schema, auto-regenerates index, clamps confidence             │
│ 4. Lead never sees raw graph — interacts through pre-digested views (get_hypothesis_summary, get_frontier, check_kill_conditions)  │
│ 5. Docker for compute — workers run bioinformatics via docker exec through Bash tool                                               │
│                                                                                                                                    │
│ ---                                                                                                                                │
│ Reusable Code from Alzheimer Pipeline                                                                                              │
│                                                                                                                                    │
│ ┌────────────────────────────────────────┬────────────────────────────────────┬────────┬────────────────────────────────────────┐  │
│ │                 Source                 │               Target               │ Reuse  │             Changes needed             │  │
│ │                                        │                                    │   %    │                                        │  │
│ ├────────────────────────────────────────┼────────────────────────────────────┼────────┼────────────────────────────────────────┤  │
│ │ Alzheimer/src/gwas_analysis.py         │ rosetta/analysis/gwas.py           │ 100%   │ Make PATHWAY_MODULES configurable      │  │
│ ├────────────────────────────────────────┼────────────────────────────────────┼────────┼────────────────────────────────────────┤  │
│ │ Alzheimer/src/expression_analysis.py   │ rosetta/analysis/expression.py     │ 95%    │ Parameterize metadata column names     │  │
│ ├────────────────────────────────────────┼────────────────────────────────────┼────────┼────────────────────────────────────────┤  │
│ │ Alzheimer/src/mr_analysis.py           │ rosetta/analysis/mr.py             │ 95%    │ Parameterize column names              │  │
│ ├────────────────────────────────────────┼────────────────────────────────────┼────────┼────────────────────────────────────────┤  │
│ │ Alzheimer/src/target_prioritization.py │ rosetta/analysis/prioritization.py │ 90%    │ Externalize druggability annotations   │  │
│ │                                        │                                    │        │ to YAML                                │  │
│ ├────────────────────────────────────────┼────────────────────────────────────┼────────┼────────────────────────────────────────┤  │
│ │ Alzheimer/src/spatial_analysis.py      │ rosetta/analysis/spatial.py        │ 80%    │ Parameterize gene signatures           │  │
│ └────────────────────────────────────────┴────────────────────────────────────┴────────┴────────────────────────────────────────┘  │
│                                                                                                                                    │
│ ---                                                                                                                                │
│ Verification                                                                                                                       │
│                                                                                                                                    │
│ 1. Unit tests: SSOT operations, analysis function regression against AD pipeline outputs                                           │
│ 2. Integration test: One full lead → worker → SSOT cycle with GWAS data                                                            │
│ 3. E2E validation: Full AD pipeline reproduction — compare final targets and decision log against human-validated results          │
│ 4. Decision log audit: Every dispatch/kill/pivot has logged rationale; all 6 reasoning strategies evidenced                        │

