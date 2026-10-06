"""
config.py — Infraon Agent configuration.

SECURITY NOTE (read this before editing)
------------------------------------------------------------------------------
The original copy of this file (in the Infraon monorepo, infraon-apm-agent/)
had real Elasticsearch and OpenObserve passwords hardcoded as plain strings.
That is exactly the mistake this rewrite avoids: every secret below is read
from an environment variable, with a placeholder default that will visibly
fail (or just do nothing) if you forget to set it, instead of silently
working with someone else's production credentials.

Set the real values as environment variables before running anything in this
folder. Two ways to do that:

  1. Export them in your shell (see setup.sh / setup.ps1 for examples), or
  2. Create a ".env" file next to this one (never commit it — it's in
     .gitignore) and let setup.sh / setup.ps1 load it for you.

Never put a real password back into this file. If you ever find one already
sitting here, rotate that password — assume it has leaked.
------------------------------------------------------------------------------
"""

import os


def _env(key: str, default: str = "") -> str:
    """Read an environment variable, falling back to *default* if unset."""
    return os.environ.get(key, default)


def _env_bool(key: str, default: bool) -> bool:
    """Read an environment variable as a boolean ('true'/'1'/'yes' => True)."""
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


CONFIG = {
    # Name this process reports itself as in traces/logs. Change this per
    # service — e.g. "checkout-api", "billing-worker" — so you can tell its
    # spans apart from everything else hitting the same collector.
    "service_name": _env("OTEL_SERVICE_NAME", "django-app"),

    # Where the *application* (via opentelemetry-instrument) sends its own
    # OTLP gRPC traffic. In the self-instrumentation flow (agent.py) this is
    # injected into the target process's environment. 4317 is the OTel
    # convention for the gRPC OTLP port.
    "otel_endpoint": _env("OTEL_ENDPOINT", "http://localhost:4317"),

    # ── Elasticsearch export (optional, off by default in this tutorial) ──
    "enable_elasticsearch": _env_bool("ENABLE_ELASTICSEARCH", False),
    "elasticsearch_url": _env("ELASTICSEARCH_URL", "http://localhost:9200"),
    "es_username": _env("ES_USERNAME", "elastic"),
    "es_password": _env("ES_PASSWORD", "CHANGE_ME_ES_PASSWORD"),

    # ── OpenObserve export (on by default — this is the primary backend) ──
    "enable_openobserve": _env_bool("ENABLE_OPENOBSERVE", True),
    "openobserve_url": _env("OPENOBSERVE_URL", "http://localhost:5080"),
    # The OpenObserve *organization* this collector writes into. In a real
    # multi-tenant setup this must be a real org identifier that your
    # OpenObserve user has access to — "default" only works against a fresh,
    # un-provisioned OpenObserve instance.
    "oo_org": _env("OO_ORG", "default"),
    "oo_trace_stream": _env("OO_TRACE_STREAM", "apm_traces"),
    "oo_log_stream": _env("OO_LOG_STREAM", "apm_logs"),
    "oo_username": _env("OO_USERNAME", "admin@example.com"),
    "oo_password": _env("OO_PASSWORD", "CHANGE_ME_OO_PASSWORD"),

    "log_file": _env("LOG_FILE", "logs/agent.log"),
}
