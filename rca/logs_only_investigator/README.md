# Logs-Only Investigator

This package is a signal-first RCA investigator built around LangGraph threads, tool nodes, Elasticsearch-backed log retrieval, MongoDB-backed topology lookup, and OpenAI-generated analyst summaries.

## Runtime Layout

- `.env`
  Holds the OpenAI API key only.
- `config.yml`
  Holds application defaults plus Elasticsearch, MongoDB, topology schema, and OpenAI model settings.
- `src/logs_only_investigator/tools/log_store.py`
  Contains the Elasticsearch log store, the robust DSL builder, and the efficient PIT plus `search_after` fetch loop.
- `src/logs_only_investigator/topology_source.py`
  Loads versioned canonical topology snapshots from MongoDB and selects the best snapshot for the incident time.
- `src/logs_only_investigator/topology.py`
  Builds the in-memory topology graph from canonical `nodes + edges` documents and derives `upstream`, `downstream`, and `underlay` views in code.
- `src/logs_only_investigator/topology_converter.py`
  Materializes production topology snapshots with canonical `depends_on` edges and version metadata.
- `src/logs_only_investigator/llm.py`
  Calls the OpenAI Responses API and falls back safely if the model request fails.
- `src/logs_only_investigator/observability.py`
  Configures readable industrial-style logging with redaction and payload previews.

## Quick Start

```powershell
cd "D:\Code for tutorials\rca\logs_only_investigator"
uv sync
uv run logs-investigator --query "why did the application go down?"
```

## Temporary Streamlit UI

The Streamlit UI is intentionally separate from the core runtime so it can be removed later without touching the backend investigator.

Install the optional UI dependency:

```powershell
uv sync --extra ui
```

Run the app:

```powershell
uv run streamlit run .\streamlit_app.py
```

The UI reuses the same runtime config, `.env`, catalogs, LangGraph thread memory, and report structure as the CLI.
It also shows:

- live tool progress
- `resolve_scope` LLM request and response details
- two-layer retrieval mode badges such as `hybrid_vector`, `lexical fallback`, and `domain fallback`
- exact tool outputs after the run completes

## RAG Rebuild

Rebuild the JSON signal catalogs and per-scope vector DBs with the dedicated command:

```powershell
.\.venv\Scripts\python.exe -m logs_only_investigator.rebuild_rag --build-vector-db=yes
```

If the package entrypoint is installed in the venv, you can also run:

```powershell
logs-investigator-rebuild-rag --build-vector-db=yes
```

## Topology Rebuild

Rebuild canonical topology snapshots from `topology_data` into `agent_topology_data`:

```powershell
.\.venv\Scripts\python.exe .\scripts\materialize_agent_topology_data.py --drop-target
```

The generated MongoDB documents now use:

- canonical directional edges in MongoDB
- `depends_on` as the main service dependency relation
- version metadata for incident-time selection
- source metadata for provenance
- root-level `nodes` and `edges` only, with no duplicated nested topology payload

Optional overrides:

```powershell
uv run logs-investigator `
  --query "why was the network slow around 10:35?" `
  --organization-id demo-org `
  --service nginx `
  --thread-id incident-42 `
  --max-hops 5
```

If you reuse the same `--thread-id`, LangGraph restores the checkpointed message history and thread memory for follow-up investigation turns.

## Logging

Runtime logs are emitted to stderr with readable step-level messages for:

- runtime initialization
- tool selection and tool execution
- Elasticsearch query paging
- MongoDB topology loading
- OpenAI summary generation

Tune logging through the `logging` section in `config.yml`.

## Output Shape

The CLI prints a JSON RCA report with:

- `summary`
- `analyst_summary`
- `analyst_summary_source`
- `llm_requested_model`
- `llm_model`
- `llm_usage`
- `total_tokens_used`
- `llm_error`
- `likely_root_cause`
- `confidence`
- `classification`
- `incident_window`
- `rag_scope`
- `candidate_signals`
- `primary_entities`
- `timeline`
- `supporting_evidence`
- `contradictions`
- `unknowns`
- `raw_context`
- `next_log_checks`
- `investigation_trace`

## Notes

- Topology loading now uses canonical root-level `nodes + edges` snapshots, while the loader still accepts older legacy node-centric payloads during migration.
- Raw logs are fetched as supporting context only after the signal-first path has been validated.
- The OpenAI summary path uses the Responses API with the model configured in `config.yml`.
