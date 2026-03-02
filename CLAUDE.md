# Rosetta — Multi-Agent Drug Discovery System

## Project Overview
Multi-agent system for drug discovery using Claude Agent SDK (Python). A lead researcher agent (Opus) orchestrates specialist worker agents (Sonnet) against a shared SSOT (Single Source of Truth).

## Architecture
- **Lead agent**: `ClaudeSDKClient` with multi-turn conversation loop (`rosetta/orchestrator.py`)
- **Worker agents**: `AgentDefinition` instances dispatched via Task tool (`rosetta/agents.py`)
- **SSOT tools**: `@tool` decorator → `create_sdk_mcp_server()` in-process MCP (`rosetta/ssot/tools.py`)
- **Analysis**: Pure Python modules ported from validated Alzheimer pipeline (`rosetta/analysis/`)

## Key Conventions
- Workers write to SSOT through tool functions, never raw YAML
- Lead never sees raw hypothesis graph — only pre-digested views
- Analysis modules are agent-agnostic (pure Python, no SDK imports)
- Docker containers handle heavy bioinformatics compute

## Running Tests
```bash
uv run pytest tests/
```

## Package Structure
- `rosetta/` — main Python package
- `rosetta/ssot/` — SSOT schema, hypothesis graph, tools
- `rosetta/analysis/` — ported bioinformatics analysis modules
- `rosetta/prompts/` — agent system prompts
- `rosetta/mcp_servers/` — external data source MCP wrappers
- `ssot/` — runtime SSOT data directory (gitignored)
- `tests/` — pytest test suite
