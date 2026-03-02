# PRD: Sprint 2–3 — SSOT Tools, GWAS Catalog MCP, Agent Wiring & MVP Integration

## Introduction

Wire up the first working multi-agent cycle for the Rosetta drug discovery system. Sprint 1 built the foundation: SSOT schema, hypothesis graph, decision log, experiment queue, and GWAS analysis port (44/44 tests passing). This PRD covers the next two sprints: exposing SSOT operations as MCP tools, building the GWAS Catalog MCP server, creating the lead researcher and GWAS worker agents, building the orchestrator, setting up Docker compute infrastructure, and running a full end-to-end integration test.

The success criterion is: the lead agent bootstraps hypotheses from a GWAS study, dispatches a GWAS worker, the worker queries the GWAS Catalog API and runs analysis, writes results to SSOT, and the lead interprets results and picks the next experiment — all with a populated decision log.

## Goals

- Expose all SSOT operations (hypothesis graph, decision log, queue) as `@tool` functions via `create_sdk_mcp_server()`
- Build a GWAS Catalog MCP server wrapping the EBI REST API with real HTTP calls
- Create the lead researcher agent system prompt encoding the 6 validated reasoning strategies
- Create the GWAS triage worker agent with domain-specific instructions
- Build the orchestrator (`run_pipeline()`) with `ClaudeSDKClient` multi-turn conversation loop
- Set up Docker compute infrastructure (Dockerfile, docker-compose, host-mounted volumes)
- Pass a full lead → worker → SSOT → lead cycle end-to-end with real API calls

## User Stories

### US-001: Create SSOT MCP tool functions
**Description:** As a developer, I need the SSOT hypothesis graph, decision log, and experiment queue operations exposed as `@tool`-decorated functions so agents can call them via MCP.

**Acceptance Criteria:**
- [ ] `rosetta/ssot/tools.py` created with 11 `@tool` functions:
  - `get_hypothesis_summary(hypothesis_id: str) -> str`
  - `get_frontier(top_n: int = 10) -> str`
  - `create_hypothesis(title: str, description: str, confidence: float, impact: float, gene: str, module: str, phase_created: int) -> str`
  - `update_confidence(hypothesis_id: str, new_confidence: float, evidence_source: str, evidence_phase: int, evidence_direction: str, evidence_strength: float, evidence_summary: str) -> str`
  - `kill_hypothesis(hypothesis_id: str, reason: str, hard: bool) -> str`
  - `propagate_evidence(hypothesis_id: str, evidence_source: str, evidence_phase: int, evidence_direction: str, evidence_strength: float, evidence_summary: str) -> str`
  - `check_kill_conditions() -> str`
  - `log_decision(action: str, rationale: str, hypothesis_id: str, phase: int) -> str`
  - `get_decision_diff(since: str) -> str`
  - `get_queue() -> str`
  - `enqueue_experiment(experiment_type: str, description: str, hypothesis_id: str, priority: int) -> str`
- [ ] Each tool function wraps the corresponding `hypothesis_graph`, `decision_log`, or `queue` module function
- [ ] Each tool returns a string (agents receive text, not raw objects)
- [ ] `create_ssot_mcp_server()` function returns a configured MCP server with all 11 tools
- [ ] Tools use a configurable SSOT directory (from env var `ROSETTA_SSOT_DIR` or parameter)
- [ ] `tests/test_tools.py` with at least 11 tests (one per tool function), all passing
- [ ] `uv run pytest tests/ -v` passes with 0 failures

### US-002: Create GWAS Catalog MCP server
**Description:** As a GWAS worker agent, I need to query the EBI GWAS Catalog REST API to search for studies, retrieve associations, and get summary statistics download URLs.

**Acceptance Criteria:**
- [ ] `rosetta/mcp_servers/gwas_catalog.py` created with 3 `@tool` functions:
  - `search_studies(query: str) -> str` — searches GWAS Catalog for studies matching a disease/trait query, returns study accessions + metadata (trait, sample size, publication)
  - `get_associations(study_accession: str) -> str` — retrieves significant SNP associations for a study, returns SNP IDs, p-values, mapped genes, risk alleles
  - `get_summary_stats_url(study_accession: str) -> str` — returns the FTP/HTTP URL for downloading full summary statistics
- [ ] All tools make real HTTP requests to `https://www.ebi.ac.uk/gwas/rest/api/`
- [ ] Responses are parsed and formatted as human-readable text summaries (not raw JSON)
- [ ] Error handling: clear error messages for network failures, 404s, rate limiting
- [ ] `create_gwas_catalog_mcp_server()` function returns a configured MCP server
- [ ] `tests/test_gwas_catalog.py` with at least 3 tests using real API calls (marked with `@pytest.mark.network` for optional skipping)
- [ ] `uv run pytest tests/ -v` passes with 0 failures (network tests can be skipped via `-m "not network"`)

### US-003: Create lead researcher system prompt
**Description:** As the orchestrator, I need a lead researcher system prompt that encodes the 6 validated reasoning strategies and decision protocol so the lead agent makes scientifically sound decisions.

**Acceptance Criteria:**
- [ ] `rosetta/prompts/lead.py` created with a `LEAD_SYSTEM_PROMPT` string constant
- [ ] Prompt encodes all 6 reasoning strategies from the validated AD pipeline:
  1. Orthogonal evidence filtration — each phase adds an independent evidence layer
  2. Adaptive fallback — detect power failures and pivot to alternative data sources
  3. Multiplicative convergence scoring — combine GWAS, expression, causality, druggability
  4. Adversarial self-critique — schedule confound tests against own results
  5. Cost-ordered evidence cascades — cheapest/fastest evidence first
  6. Theory-laden weighted integration — causality weighted 1.5x, druggability reshuffles rankings
- [ ] Prompt includes a decision protocol: after each worker result, the lead must (1) check kill conditions, (2) update hypothesis graph, (3) log decision with rationale, (4) get frontier, (5) dispatch next worker or conclude
- [ ] Prompt instructs the lead to use SSOT tools (never raw YAML) and to write structured rationales in the decision log
- [ ] Prompt references available worker agents and their capabilities
- [ ] `uv run pytest tests/ -v` passes with 0 failures

### US-004: Create GWAS worker agent prompt and agent definitions
**Description:** As the orchestrator, I need agent definitions for the GWAS triage worker (and a factory function for building all worker agents) so the lead can dispatch workers via the Task tool.

**Acceptance Criteria:**
- [ ] `rosetta/prompts/gwas_worker.py` created with a `GWAS_WORKER_PROMPT` string constant
- [ ] GWAS worker prompt instructs the agent to:
  1. Query the GWAS Catalog MCP for study data
  2. Parse and extract significant loci
  3. Run `rosetta.analysis.gwas` functions (via Bash or direct Python) to classify genes into pathway modules
  4. Write results to SSOT: create hypotheses for top genes, add evidence, log decisions
  5. Return a structured summary (not raw data) to the lead
- [ ] `rosetta/agents.py` created with `build_worker_agents()` function returning `dict[str, AgentDefinition]`
- [ ] GWAS worker `AgentDefinition` includes: description, prompt, model ("sonnet"), and tool list (GWAS Catalog MCP + SSOT MCP tools)
- [ ] Workers do NOT have access to the `Task` tool (cannot spawn sub-agents — SDK constraint)
- [ ] `tests/test_agents.py` with tests verifying agent definitions are correctly constructed
- [ ] `uv run pytest tests/ -v` passes with 0 failures

### US-005: Build the orchestrator with ClaudeSDKClient
**Description:** As a user, I need to run the full pipeline via a `run_pipeline()` function that creates the lead agent, wires up all MCP servers and worker agents, and runs the multi-turn conversation loop.

**Acceptance Criteria:**
- [ ] `rosetta/orchestrator.py` created with `run_pipeline(disease: str, study_accession: str | None = None, ssot_dir: str | None = None, max_turns: int = 20) -> None`
- [ ] Creates `ClaudeSDKClient` with:
  - Lead system prompt from `rosetta/prompts/lead.py`
  - SSOT MCP server from `rosetta/ssot/tools.py`
  - GWAS Catalog MCP server from `rosetta/mcp_servers/gwas_catalog.py`
  - Worker agent definitions from `rosetta/agents.py`
  - Model: "opus" for lead (configurable via env var `ROSETTA_LEAD_MODEL`)
- [ ] Bootstraps the conversation with an initial prompt containing the disease specification
- [ ] Implements a continuation loop: `client.query()` → process response → `client.receive_response()` → repeat until lead signals completion or `max_turns` reached
- [ ] Loads `.env` file for `ANTHROPIC_API_KEY` and other configuration
- [ ] Can be run as a script: `uv run python -m rosetta.orchestrator` with CLI args
- [ ] `uv run pytest tests/ -v` passes with 0 failures

### US-006: Set up Docker compute infrastructure
**Description:** As a developer, I need a Docker setup with a fat bioinformatics image (R + Python + common packages) and host-mounted volumes so worker agents can execute heavy compute jobs.

**Acceptance Criteria:**
- [ ] `docker/Dockerfile` created with:
  - Base: `python:3.12-slim` with R installed (`r-base`)
  - Python packages: pandas, numpy, scipy, statsmodels, scanpy, anndata, matplotlib, seaborn
  - R packages: BiocManager, DESeq2, TwoSampleMR (install from Bioconductor)
  - Working directory: `/workspace`
  - Volume mount point: `/data` (maps to host `ssot/` directory)
- [ ] `docker/docker-compose.yml` created with:
  - Service: `rosetta-compute`
  - Build context: `docker/`
  - Volume: `../ssot:/data`
  - Keep container running: `command: tail -f /dev/null`
- [ ] `docker/scripts/` directory with a sample script `run_analysis.py` that demonstrates reading from `/data` and writing results back
- [ ] `docker build -t rosetta-compute docker/` completes successfully
- [ ] `docker-compose -f docker/docker-compose.yml up -d` starts the container
- [ ] `docker exec rosetta-compute python -c "import pandas; print('OK')"` succeeds
- [ ] `uv run pytest tests/ -v` passes with 0 failures (Docker tests can be marked `@pytest.mark.docker`)

### US-007: MVP integration test — full lead-worker-SSOT cycle
**Description:** As a developer, I need an integration test that verifies the full cycle: lead bootstraps → dispatches GWAS worker → worker queries API + runs analysis → writes to SSOT → lead interprets → lead picks next experiment.

**Acceptance Criteria:**
- [ ] `tests/test_integration.py` created with at least one integration test
- [ ] Test wires up: lead + SSOT tools + GWAS worker + GWAS Catalog MCP
- [ ] After the test run, verify:
  - Hypotheses exist in `ssot/hypotheses/` (at least 1 created)
  - Decision log `ssot/decisions.jsonl` is populated (at least 1 entry)
  - The lead's responses reference SSOT tool calls (not raw file manipulation)
- [ ] Test is marked `@pytest.mark.integration` (skippable for fast unit test runs)
- [ ] Test uses a real `ANTHROPIC_API_KEY` (from env) — this is a live integration test
- [ ] `uv run pytest tests/ -v -m "not integration"` passes with 0 failures (unit tests still green)
- [ ] `uv run pytest tests/test_integration.py -v` passes when API key is available

## Functional Requirements

- FR-1: All SSOT tool functions must accept and return strings only (agents communicate via text, not Python objects)
- FR-2: SSOT tools must use the `@tool` decorator from `claude_agent_sdk` with name, description, and parameter schema
- FR-3: `create_ssot_mcp_server()` must return an `McpSdkServerConfig` using `create_sdk_mcp_server()`
- FR-4: GWAS Catalog MCP tools must make real HTTP GET requests to `https://www.ebi.ac.uk/gwas/rest/api/`
- FR-5: GWAS Catalog responses must be parsed from JSON and formatted as readable text (not raw API JSON)
- FR-6: The lead system prompt must reference SSOT tools by their MCP-namespaced names (`mcp__ssot__<tool_name>`)
- FR-7: Worker agents must not have the `Task` tool in their tool list (SDK constraint: no sub-agent spawning)
- FR-8: The orchestrator must use `ClaudeSDKClient` (not `query()`) for multi-turn conversation state
- FR-9: The orchestrator continuation loop must handle: `AssistantMessage` with tool calls, `TextBlock` responses, and `ResultMessage` completion
- FR-10: Docker containers must use host-mounted volumes (not Docker volumes) for SSOT data exchange
- FR-11: The Docker image must include both R and Python with the bioinformatics packages listed in `pyproject.toml[bio]`
- FR-12: All new code must follow existing patterns: type hints, docstrings matching the style in `schema.py`/`hypothesis_graph.py`, ruff-clean

## Non-Goals

- No frontend/UI in this sprint — agents run via CLI only
- No Expression, MR, Confound, Druggability, or Spatial workers yet (those are Sprints 4–7)
- No report generation or notebook building
- No cloud deployment (Docker runs locally only)
- No authentication/rate-limiting for the GWAS Catalog MCP (simple wrapper)
- No persistent agent memory across pipeline runs
- No multi-disease support — this sprint is AD-only validation

## Technical Considerations

- **SDK imports**: `from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AgentDefinition, tool, create_sdk_mcp_server, AssistantMessage, TextBlock, ResultMessage`
- **MCP tool naming**: When tools are registered via `create_sdk_mcp_server("ssot", tools=[...])`, they become `mcp__ssot__get_hypothesis_summary`, `mcp__ssot__create_hypothesis`, etc. in the agent's `allowed_tools` list
- **SSOT directory**: All SSOT operations use `ROSETTA_SSOT_DIR` env var (default `./ssot`). Tests use `tmp_ssot_dir` fixture from `conftest.py`
- **GWAS Catalog API**: Base URL `https://www.ebi.ac.uk/gwas/rest/api/`. Key endpoints: `/studies/search/findByDiseaseTrait`, `/studies/{accession}/associations`, `/studies/{accession}`. Pagination via `page` and `size` params. Response format: HAL+JSON
- **Existing code to reuse**: `rosetta.ssot.hypothesis_graph` (all graph operations), `rosetta.ssot.decision_log` (logging), `rosetta.ssot.queue` (experiment queue), `rosetta.analysis.gwas` (GWAS analysis functions)
- **Test markers**: Use `@pytest.mark.network` for tests requiring internet, `@pytest.mark.integration` for full agent tests, `@pytest.mark.docker` for container tests. Register markers in `pyproject.toml`
- **Docker base considerations**: R + Bioconductor install is slow (~15 min). Consider multi-stage build or pre-built base image. DESeq2 alone pulls in 80+ R dependencies

## Success Metrics

- All 11 SSOT tools callable by agents and returning useful text summaries
- GWAS Catalog MCP successfully queries the EBI API for Alzheimer's studies and returns parsed results
- Lead agent autonomously dispatches GWAS worker and interprets results within 20 turns
- Decision log shows at least: `create_hypothesis`, `dispatch_worker`, `update_confidence` entries
- Hypothesis graph populated with gene-level hypotheses from GWAS triage
- All unit tests pass (`uv run pytest tests/ -v -m "not integration and not network and not docker"`)
- Docker image builds and can execute Python + R scripts

## Open Questions

- Should the GWAS Catalog MCP include pagination for large result sets, or is truncation to top N results sufficient for the first pass?
- What is the exact `claude-agent-sdk` import path for `McpSdkServerConfig`? (May need to verify against latest SDK version)
- Should the integration test use a specific GWAS study accession (e.g., `GCST90027158` — Bellenguez 2022) or let the lead discover it?
- How many turns should the integration test allow before timing out? (API cost consideration)
