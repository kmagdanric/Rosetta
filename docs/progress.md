# Rosetta Implementation Progress

## Completed

### Sprint 1a: Project Scaffolding ✅
- `pyproject.toml` — Python 3.12, deps: claude-agent-sdk, pydantic, pyyaml, pandas, numpy, scipy, statsmodels, requests, python-dotenv. Dev extras: pytest, pytest-asyncio, ruff. Bio extras for heavy bioinformatics.
- `.gitignore` — ignores runtime SSOT data, reports, venv, pycache
- `.env.example` — ANTHROPIC_API_KEY, model overrides, SSOT dir, Docker image
- `CLAUDE.md` — project overview, architecture summary, conventions, test command
- All `__init__.py` files created for: `rosetta/`, `rosetta/prompts/`, `rosetta/ssot/`, `rosetta/analysis/`, `rosetta/mcp_servers/`, `rosetta/reporting/`, `tests/`
- Directory structure: `ssot/hypotheses/`, `ssot/data_registry/`, `reports/`, `docker/scripts/`, `tests/fixtures/`
- `.gitkeep` files in empty SSOT dirs

### Sprint 1b: SSOT Schema + Hypothesis Graph ✅
- `rosetta/ssot/schema.py` — Pydantic models: `Hypothesis`, `Evidence`, `Edge`, `KillCondition`, plus enums `EdgeType`, `HypothesisStatus`, `KillOutcome`
- `rosetta/ssot/hypothesis_graph.py` — Full DAG operations:
  - `create_hypothesis()`, `load_hypothesis()`, `save_hypothesis()`, `load_all_hypotheses()`, `next_hypothesis_id()`
  - `update_confidence()` — clamps 0-1, reduces uncertainty
  - `kill_hypothesis()` — hard kill (confidence=0, KILLED) or soft kill (demoted)
  - `add_edge()` — typed edges with dedup
  - `propagate_evidence()` — cascades through DAG edges (supports/contradicts/depends_on)
  - `get_hypothesis_summary()` — pre-digested text view for lead (NOT raw YAML)
  - `get_frontier()` — ranked by uncertainty × impact
  - `check_kill_conditions()` — scans all active hypotheses
  - `regenerate_index()` — auto-generates `_index.yaml`
- `rosetta/ssot/decision_log.py` — JSONL append-only: `log_decision()`, `read_decisions()`, `get_decision_diff()`
- `rosetta/ssot/queue.py` — `enqueue_experiment()`, `dequeue_experiment()`, `get_queue()`, `complete_experiment()`
- Tests: `tests/test_ssot.py` (5 tests), `tests/test_hypothesis_graph.py` (28 tests)

### Sprint 1c: Port GWAS Analysis ✅
- `rosetta/analysis/gwas.py` — Ported from `Alzheimer/src/gwas_analysis.py`
  - Key change: `PATHWAY_MODULES` → `DEFAULT_AD_PATHWAY_MODULES` (configurable parameter)
  - Added `build_gene_to_module_map(pathway_modules=None)` — accepts custom modules
  - `classify_genes_to_modules()` now takes optional `pathway_modules` parameter
  - Removed print statements (replaced with pure returns)
  - All original functions preserved: `extract_significant_loci()`, `clump_loci()`, `classify_genes_to_modules()`, `compute_module_statistics()`, `compute_amyloid_vs_nonamyloid()`, `compute_risk_contribution_by_module()`
- Tests: `tests/test_analysis.py` (11 tests including AD pipeline regression)

### Test Results: 44/44 passing ✅
Run with: `uv run python -m pytest tests/ -v`

---

## Not Started

### Sprint 2a: SSOT MCP Server Tools
- `rosetta/ssot/tools.py` — 11 `@tool` functions wrapping hypothesis_graph + decision_log + queue
- `create_ssot_mcp_server()` returning `McpSdkServerConfig`

### Sprint 2b: GWAS Catalog MCP
- `rosetta/mcp_servers/gwas_catalog.py` — 3 tools wrapping EBI REST API

### Sprint 2c: GWAS Worker Agent + Lead Skeleton + Orchestrator
- `rosetta/prompts/gwas_worker.py`, `rosetta/prompts/lead.py`
- `rosetta/agents.py` — `build_worker_agents()`
- `rosetta/orchestrator.py` — `run_pipeline()` with ClaudeSDKClient

### Sprints 3-8: See implementation plan in the conversation or docs/

---

## Key SDK Details (from research)

Package: `claude-agent-sdk` (v0.1.44+, PyPI, MIT license)

```python
from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions, AgentDefinition,
    tool, create_sdk_mcp_server,
    AssistantMessage, TextBlock, ResultMessage,
)
```

- **Lead**: `ClaudeSDKClient` with multi-turn `client.query()` / `client.receive_response()` loop
- **Workers**: `AgentDefinition(description=..., prompt=..., tools=[...], model="sonnet")` — invoked via `Task` tool
- **Custom tools**: `@tool("name", "desc", {"param": type})` → `create_sdk_mcp_server("name", tools=[...])`
- **Tool naming**: MCP tools become `mcp__{server_key}__{tool_name}` in `allowed_tools`
- **Constraint**: Subagents cannot spawn subagents (no `Task` in their tools list)

---

## Files Created

```
pyproject.toml
.gitignore
.env.example
CLAUDE.md
rosetta/__init__.py
rosetta/prompts/__init__.py
rosetta/ssot/__init__.py
rosetta/ssot/schema.py
rosetta/ssot/hypothesis_graph.py
rosetta/ssot/decision_log.py
rosetta/ssot/queue.py
rosetta/analysis/__init__.py
rosetta/analysis/gwas.py
rosetta/mcp_servers/__init__.py
rosetta/reporting/__init__.py
tests/__init__.py
tests/conftest.py
tests/test_ssot.py
tests/test_hypothesis_graph.py
tests/test_analysis.py
ssot/hypotheses/.gitkeep
ssot/data_registry/.gitkeep
```
