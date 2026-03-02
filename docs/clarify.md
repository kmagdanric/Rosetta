# Architecture Clarifications

Responses to clarifying questions on the Rosetta architecture document (v0.1).

---

## 1 & 2. Scope and SDK Choice

**User response:** Using the Claude Agent SDK (Python) rather than Claude Code subagents. The system will grow into a UI-rich app showing agent processes.

**Interpretation:**
- Starting at **P2 (Agents)** — multi-agent orchestration with lead + workers — rather than a monolithic single-session approach.
- The orchestration layer will be built with the **Claude Agent SDK** (`claude_agent_sdk` Python package), calling the Anthropic API programmatically.
- This gives a proper Python backend that can later expose agent state, SSOT, hypothesis graph, and decision logs to a frontend (web UI, dashboard, etc.).
- The Agent SDK's native tool-use and multi-turn conversation capabilities map well to the lead researcher dispatching workers and interpreting results.
- **P1 (monolith) is skipped entirely.** Starting directly at P2 with multi-agent orchestration.

---

## 3. SSOT Storage

**User response:** SSOT should be human-readable and easy for agents to slot work into. Database choice doesn't matter — retrieval speed is not a concern. However, humans need to inspect results with proper reports, matplotlib plots, and generated documents.

**Interpretation:**
- **Two-layer design**: SSOT (machine layer) + Reports (human layer).
- **SSOT stays structured YAML/JSONL** in a `ssot/` directory:
  - `ssot/hypotheses/` — one YAML file per hypothesis node (H001.yaml, etc.)
  - `ssot/data_registry/` — one YAML file per registered dataset/result
  - `ssot/decisions.jsonl` — append-only decision log (one JSON object per line)
  - `ssot/queue.yaml` — experiment queue
- **Agents never touch files directly** — they call Python tool functions (`create_hypothesis()`, `update_confidence()`, `log_decision()`) that handle serialization and structural consistency. This abstraction layer also controls context window loading.
- **Reports are a separate rendered output** generated from SSOT state:
  - `reports/<run_id>/report.ipynb` — Jupyter notebook with narrative + matplotlib/seaborn plots
  - `reports/<run_id>/report.html` — rendered via nbconvert for non-technical stakeholders
  - `reports/<run_id>/figures/` — exported PNGs
- Report content includes: hypothesis graph visualizations, evidence convergence heatmaps, Manhattan plots, forest plots, tiered target tables, decision log timelines.
- A **Reporter worker agent** (or Python module) can be invoked by the lead after each major step or at pipeline completion.
- This same SSOT data can later power the live UI dashboard.

---

## 4. MCP Servers — Build or Existing?

**User response:** Just starting out — not sure what databases are available or which already have MCP support. Most won't. Want to build custom MCP servers where possible.

**Interpretation:**
- **Building MCP servers is in scope** and will be a significant chunk of the work.
- Most bioinformatics databases (GWAS Catalog, GEO, GTEx, ChEMBL, etc.) do not have existing MCP servers — these will need to be built as custom wrappers around their REST APIs or bulk data downloads.
- A practical approach: **build MCP servers incrementally as the pipeline demands them**, not all 20+ upfront. The execution flow (GWAS Triage → Expression → MR → Confound → Scoring → Druggability/Spatial) gives a natural build order.
- First MCP servers to build would be: GWAS Catalog, GEO/GTEx (for expression), eQTLGen (for MR) — these cover steps 1–3.
- Each MCP server should normalize the external API into clean tool interfaces that worker agents can call.
- Before building each one, worth a quick check for any community MCP servers that already exist.

---

## 5. Compute Sandbox

**User response:** Docker containers. A running container with a host-mounted directory for data exchange. Dependencies installed as needed, container rebuilt if necessary. Should be amenable to future cloud migration (e.g., Cloud Run).

**Interpretation:**
- **Docker-based compute sandbox** with host-mounted volume for SSOT ↔ container data I/O.
- **Pre-baked base image(s)** with heavy dependencies (R + Bioconductor, Python + scanpy, etc.) to avoid slow/non-reproducible runtime installs.
- Jobs execute via `docker exec` on a running container.
- Lightweight runtime installs only as a fallback for rare edge cases — default is to **update Dockerfile and rebuild** when new tools are needed.
- Start with a single image; split into domain-specific images later if needed:
  - `rosetta-compute/Dockerfile` — fat image with R + Python + all common packages
  - Potential future split: `Dockerfile.r` (DESeq2, TwoSampleMR), `Dockerfile.python` (Scanpy, Squidpy)
- The infra agent manages container lifecycle: starting, executing jobs, collecting results, cleanup.
- **Cloud migration path**: swap host mount for cloud storage bucket, swap `docker exec` for Cloud Run job — agent code stays largely the same.

---

## 6. The Validated AD Pipeline

**User response:** Full reference pipeline lives in `/Users/joseph/programming/kmagdanric/Alzheimer` — 8-phase pipeline with code (`src/`, `notebooks/`), reports (`reports/`), and an Obsidian knowledge vault (`mindmaps/`).

**Interpretation (from reading the reports):**

The validated pipeline is a complete 8-phase AD target discovery run (55 → 3 targets in ~2 days):

| Phase | Method | Data Source | Key Output |
|-------|--------|-------------|------------|
| 1 | GWAS Triage | Bellenguez 2022 (GCST90027158, N≈788K) | 55 non-amyloid risk genes across 8 pathway modules |
| 2 | Expression Filter | GSE125583 (bulk RNA-seq, fusiform gyrus, 289 samples) | 36/55 DE genes; multiplicative convergence scores |
| 3 | Brain eQTL MR | GTEx v8 Brain Cortex (~250 donors) | **POWER FAILURE** — 0 genes with ≥3 instruments |
| 4 | Integrated Scoring | Phases 1-3 + curated druggability | Tier 1: INPP5D (100), TREM2 (81.2), APOE (73.4) |
| 5 | snRNA-seq Confound | GSE138852 (Grubman 2019, entorhinal, 11.8K nuclei) | Oligodendrocyte expansion artifact flagged |
| 6 | Blood eQTL MR | eQTLGen (31,684 donors) | 11/17 causal hits; MS4A6A top (FDR=1.85e-19) |
| 7 | Drug Landscape | ChEMBL, ClinicalTrials.gov | INPP5D/SHIP1: 24 compounds, 0 AD trials |
| 8 | Spatial Validation | SEA-AD MERFISH (1.9M cells) + Visium GSE220442 | 52/83 genes in PIG niche; all Tier 1 spatially confirmed |

**Final 3 targets:** MS4A6A (strongest causal MR), INPP5D (highest convergence + druggability), PICALM (strong causal + endolysosomal pivot). Independently converges with $11.3M NIH program.

**Six reasoning strategies observed in the pipeline:**
1. **Orthogonal evidence filtration** — each phase adds an independent evidence layer; only genes surviving all layers are nominated
2. **Adaptive fallback** — Phase 3 brain eQTL failure → Phase 6 pivot to blood eQTLs (125× more samples), justified because immune genes share eQTL architecture across blood/brain
3. **Multiplicative convergence scoring** — GWAS × Expression in Phase 2; weighted integration in Phase 4 (GWAS 25%, Expression 25%, Causality 37.5%, Druggability 12.5%)
4. **Adversarial self-critique** — Phase 5 deliberately tested whether bulk DE results were composition artifacts via snRNA-seq; flagged but didn't kill targets due to limited evidence
5. **Cost-ordered evidence cascades** — cheapest/fastest evidence first (GWAS triage), expensive compute last (spatial, docking)
6. **Theory-laden weighted integration** — causality weighted 1.5× because hardest to obtain and most actionable; druggability reshuffled rankings (BIN1 #2→#7, INPP5D #3→#1)

**Key decision/pivot points for the system to replicate:**
- Phase 3→6 eQTL source pivot (brain underpowered → blood proxy)
- Phase 5 composition artifact assessment (flag but don't kill on limited evidence)
- Druggability-driven reshuffling in Phase 4 (enzymes/receptors up, adaptors down)

---

## 7. Kill Conditions

**User response:** Kill conditions are the lead's decision rules for managing the hypothesis graph. They apply to hypothesis nodes — marking them as killed, demoted, or pivoted — not to running code or containers.

**Interpretation:**
- Kill conditions are **per-hypothesis rules** pre-declared when the lead creates a hypothesis node.
- When a worker returns a result, the lead checks whether any kill conditions are triggered.
- Three outcomes: **hard kill** (hypothesis dead), **soft kill / demotion** (confidence drops, deprioritized), or **conditional pivot** ("kill UNLESS fallback X is available" — e.g., Phase 3→6).
- The AD pipeline mostly used soft kills and conditional pivots; pure hard kills were rare.
- Kill condition checking is **Python-computed, LLM-judged** — Python checks thresholds, the lead decides whether context warrants overriding.

---

## 8. Hypothesis Graph Representation (emerged from Q7 discussion)

**Key design decision:** The hypothesis graph is a **DAG with typed edges**, not a tree.

- **Nodes** = hypotheses (claims like "INPP5D is a viable AD target")
- **Edges** = typed relationships: `supports`, `contradicts`, `depends_on`, `derived_from`
- **Multiple incoming edges** per node (convergent evidence, shared assumptions)
- Example: "blood eQTLs are valid proxy for brain immune genes" feeds into multiple downstream gene hypotheses. If the assumption is killed, all dependents are flagged.

**Storage:**
- Individual YAML files per hypothesis node (detailed evidence, kill conditions, edges)
- Auto-generated `_index.yaml` with compact adjacency list (node summaries + edge list)

**Critical architectural decision: the lead never sees raw graph YAML.**

The SSOT tool layer is a **reasoning support layer**, not just file I/O. Python computes; the LLM reasons.

| Task | Who does it |
|------|------------|
| Traverse edges, propagate confidence | Python |
| Count supporting/contradicting evidence | Python |
| Check kill condition thresholds | Python |
| Sort hypotheses by information gain | Python |
| Decide what to investigate next | Lead agent (LLM) |
| Interpret whether a result is meaningful | Lead agent (LLM) |
| Decide whether to pivot or kill | Lead agent (LLM) |
| Write rationale for decision log | Lead agent (LLM) |

**Key tool functions the lead calls instead of reading raw YAML:**
- `get_hypothesis_summary(id)` — focused view of one node + its neighborhood
- `get_frontier()` — hypotheses with highest uncertainty × impact (what to investigate next)
- `propagate_evidence(result)` — Python updates confidence scores downstream, returns a diff for the lead to review
- `check_kill_conditions()` — returns triggered or near-triggered conditions
- `get_decision_diff(since=last_cycle)` — what changed since the lead last looked

This design ensures the lead makes scientific judgments while Python handles graph bookkeeping — encoding the scientific method as infrastructure.
