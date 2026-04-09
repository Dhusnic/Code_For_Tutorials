from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from urllib import error, parse, request


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_signal_processor_config() -> Path:
    return project_root() / "log_signal_processor" / "config.yml"


def default_correlation_engine_config() -> Path:
    return project_root() / "log_correlation_engine" / "config" / "config.yml"


def default_rules_file() -> Path:
    return project_root() / "log_correlation_engine" / "rules" / "rules.json"


def parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "null":
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value


def load_sectioned_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_section: str | None = None
    current_list_key: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped.endswith(":"):
            current_section = stripped[:-1]
            data[current_section] = {}
            current_list_key = None
            continue

        if current_section is None:
            continue

        section = data[current_section]
        if indent == 2 and ":" in stripped:
            key, raw_value = stripped.split(":", 1)
            key = key.strip()
            raw_value = raw_value.strip()
            if raw_value == "":
                section[key] = []
                current_list_key = key
            else:
                section[key] = parse_scalar(raw_value)
                current_list_key = None
            continue

        if indent >= 4 and stripped.startswith("- ") and current_list_key:
            section[current_list_key].append(parse_scalar(stripped[2:]))

    return data


def load_elasticsearch_settings(config_path: Path) -> dict[str, Any]:
    config = load_sectioned_yaml(config_path)
    elasticsearch = config.get("elasticsearch", {})
    addresses = elasticsearch.get("addresses", [])
    if not addresses:
        raise ValueError(f"No elasticsearch.addresses found in {config_path}")
    return {
        "address": str(addresses[0]).rstrip("/"),
        "username": str(elasticsearch.get("username") or ""),
        "password": str(elasticsearch.get("password") or ""),
        "api_key": str(elasticsearch.get("api_key") or ""),
        "index": str(elasticsearch.get("index") or ""),
    }


class ElasticsearchHttpClient:
    def __init__(self, address: str, username: str = "", password: str = "", api_key: str = "") -> None:
        self.address = address.rstrip("/")
        self.username = username
        self.password = password
        self.api_key = api_key

    def _headers(self, content_type: str) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": content_type,
        }
        if self.api_key:
            headers["Authorization"] = f"ApiKey {self.api_key}"
        elif self.username or self.password:
            token = base64.b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        return headers

    def request_json(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        *,
        query: dict[str, Any] | None = None,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        url = self.address + path
        if query:
            url += "?" + parse.urlencode(query)

        data: bytes | None = None
        if payload is not None:
            if content_type == "application/json":
                data = json.dumps(payload).encode("utf-8")
            else:
                data = payload.encode("utf-8")

        req = request.Request(url, data=data, method=method.upper(), headers=self._headers(content_type))
        try:
            with request.urlopen(req, timeout=30) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Elasticsearch request failed ({exc.code} {exc.reason}): {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Failed to connect to Elasticsearch at {self.address}: {exc}") from exc

        if not body:
            return {}
        return json.loads(body)

