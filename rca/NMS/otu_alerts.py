import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3
import xmltodict
from requests.auth import HTTPBasicAuth

# ============================================================
# Configuration
# ============================================================
TIMEOUT = 20
VERIFY_SSL = False

EMS_IP_ADDR = "172.16.192.89"
LOGIN_PROFILE: Dict[str, Any] = {
    "type": "http",
    "port": 80,
    "username": "admin",
    "password": "password",
}

# POST /events returns only new events for the authenticated user.
# Keep it off by default unless you explicitly want that behavior.
FETCH_NEW_EVENTS = False

SCRIPT_DIR = Path(__file__).resolve().parent
RAW_DIR = SCRIPT_DIR / "raw_output"
ALARM_FILTER_JSON_FILE = SCRIPT_DIR / "alarm_filter.json"

PARSED_ALARMS_FILE = SCRIPT_DIR / "alarms_parsed.json"
PARSED_EVENTS_FILE = SCRIPT_DIR / "events_parsed.json"
FINAL_OUTPUT_FILE = SCRIPT_DIR / "onmsi_alarm_output.json"

DEFAULT_ALARM_FILTER_PAYLOAD: Dict[str, Any] = {
    "minimalSeverity": "MINOR",
    "page": 1,
    "pageSize": 50,
    "cleared": False,
    "qualityOfServiceLink": True,
    "nonQualityOfService": False,
    "qualityOfServiceCableRoute": False,
    "dateFilter": "RAISED",
    "dateFrom": "2025-05-04",
    "dateTo": "2025-11-14",
}


# ============================================================
# Helpers
# ============================================================
def decryptConfig(value: Any) -> Any:
    # Replace this with your real decryptConfig import if needed.
    return value


def log_info(message: str) -> None:
    print(f"[INFO] {message}")


def log_error(message: str) -> None:
    print(f"[ERROR] {message}")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_json_file(path: Path, content: Any) -> None:
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")


def strip_namespace(key: str) -> str:
    if not isinstance(key, str):
        return key
    return key.split(":")[-1]


def normalize_keys(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {strip_namespace(k): normalize_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_keys(i) for i in obj]
    return obj


def ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def parse_raw_response(raw_text: str, content_type: str = "") -> Tuple[Any, str]:
    raw_text = raw_text.strip()
    if not raw_text:
        return None, "text"

    try:
        return normalize_keys(json.loads(raw_text)), "json"
    except Exception:
        pass

    try:
        return normalize_keys(xmltodict.parse(raw_text)), "xml"
    except Exception:
        pass

    return raw_text, "text"


def save_api_result(file_stem: str, result: Dict[str, Any]) -> Dict[str, Any]:
    extension = result["detected_format"] if result["detected_format"] != "text" else "txt"
    raw_path = RAW_DIR / f"{file_stem}.{extension}"
    write_text_file(raw_path, result["raw_text"])
    result["raw_file"] = str(raw_path)
    return result


def load_alarm_filter_payload(path: Path) -> Dict[str, Any]:
    if not path.exists():
        log_info("alarm_filter.json not found; using the default sample alarm filter payload")
        return dict(DEFAULT_ALARM_FILTER_PAYLOAD)

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        log_info("alarm_filter.json is empty; using the default sample alarm filter payload")
        return dict(DEFAULT_ALARM_FILTER_PAYLOAD)

    return json.loads(content)


def extract_alarm_items(parsed: Any) -> List[Any]:
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return parsed
    if not isinstance(parsed, dict):
        return []

    if "Alarms" in parsed:
        container = parsed["Alarms"]
        if isinstance(container, dict):
            if "alarm" in container:
                return ensure_list(container["alarm"])
            if "Alarm" in container:
                return ensure_list(container["Alarm"])
        return ensure_list(container)

    for key in ("alarm", "Alarm", "alarms", "items", "content"):
        if key in parsed:
            return ensure_list(parsed[key])

    return []


def extract_event_items(parsed: Any) -> List[Any]:
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return parsed
    if not isinstance(parsed, dict):
        return []

    if "Events" in parsed:
        container = parsed["Events"]
        if isinstance(container, dict):
            if "event" in container:
                return ensure_list(container["event"])
            if "Event" in container:
                return ensure_list(container["Event"])
        return ensure_list(container)

    for key in ("event", "Event", "events", "items", "content"):
        if key in parsed:
            return ensure_list(parsed[key])

    return []


# ============================================================
# ONMSi Client
# ============================================================
class OnmsiAlarmClient:
    def __init__(self, ems_ip_addr: str, login_profile: Dict[str, Any]) -> None:
        self.ems_ip_addr = ems_ip_addr

        self.session = requests.Session()
        protocol = login_profile.get("type", "https")
        port = login_profile.get("port", 443)
        self.base_url = f"{protocol}://{self.ems_ip_addr}:{port}"

        username = login_profile.get("username", "").strip()
        password = str(decryptConfig(login_profile.get("password", "")))
        self.session.auth = HTTPBasicAuth(username, password)

        self.timeout = int(login_profile.get("timeout", TIMEOUT))
        self.verify_ssl = bool(login_profile.get("verify_ssl", VERIFY_SSL))

        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def request_api(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        content_type: Optional[str] = None,
        accept: str = "application/json, application/xml, text/xml, */*",
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"Accept": accept}
        if content_type:
            headers["Content-Type"] = content_type

        response = self.session.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
            headers=headers,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        response.raise_for_status()

        parsed, detected_format = parse_raw_response(response.text, response.headers.get("Content-Type", ""))
        return {
            "url": response.url,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "raw_text": response.text,
            "parsed": parsed,
            "detected_format": detected_format,
        }

    def fetch_alarms_by_filter(self, filter_payload: Dict[str, Any]) -> Dict[str, Any]:
        log_info("Fetching alarms using POST /rs/alarms/filter")
        result = self.request_api(
            "POST",
            "/rs/alarms/filter",
            json_body=filter_payload,
            content_type="application/json",
        )
        result["used_endpoint"] = "/rs/alarms/filter"
        result["used_method"] = "POST"
        result["used_non_idempotent"] = False
        return save_api_result("alarms_filter_response", result)

    def fetch_new_events(self) -> Dict[str, Any]:
        log_info("Fetching events using POST /rs/events")
        result = self.request_api(
            "POST",
            "/rs/events",
            content_type="application/json",
        )
        result["used_endpoint"] = "/rs/events"
        result["used_method"] = "POST"
        result["used_non_idempotent"] = True
        return save_api_result("events_response", result)


# ============================================================
# Main
# ============================================================
def main() -> None:
    ensure_dir(RAW_DIR)
    client = OnmsiAlarmClient(EMS_IP_ADDR, LOGIN_PROFILE)

    try:
        log_info(f"Connecting to ONMSi at {client.base_url}")

        filter_payload = load_alarm_filter_payload(ALARM_FILTER_JSON_FILE)
        alarms_result = client.fetch_alarms_by_filter(filter_payload)
        alarms = extract_alarm_items(alarms_result["parsed"])

        write_json_file(
            PARSED_ALARMS_FILE,
            {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "base_url": client.base_url,
                "used_endpoint": alarms_result.get("used_endpoint"),
                "used_method": alarms_result.get("used_method"),
                "request_payload": filter_payload,
                "raw_file": alarms_result["raw_file"],
                "detected_format": alarms_result["detected_format"],
                "alarm_count_extracted": len(alarms),
                "parsed": alarms_result["parsed"],
            },
        )
        log_info(f"Extracted {len(alarms)} alarm record(s)")

        events_output: Optional[Dict[str, Any]] = None
        if FETCH_NEW_EVENTS:
            events_result = client.fetch_new_events()
            events = extract_event_items(events_result["parsed"])
            events_output = {
                "used_endpoint": events_result.get("used_endpoint"),
                "used_method": events_result.get("used_method"),
                "used_non_idempotent": events_result.get("used_non_idempotent", False),
                "raw_file": events_result["raw_file"],
                "detected_format": events_result["detected_format"],
                "event_count_extracted": len(events),
                "parsed": events_result["parsed"],
            }
            write_json_file(PARSED_EVENTS_FILE, events_output)
            log_info(f"Extracted {len(events)} event record(s)")

        final_output = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "ems_ip_addr": EMS_IP_ADDR,
            "base_url": client.base_url,
            "read_only_alarm_mode": True,
            "used_alarm_endpoint": "/rs/alarms/filter",
            "used_events_endpoint": "/rs/events" if FETCH_NEW_EVENTS else None,
            "events_call_enabled": FETCH_NEW_EVENTS,
            "events_call_non_idempotent": FETCH_NEW_EVENTS,
            "raw_output_directory": str(RAW_DIR),
            "alarm_filter_file": str(ALARM_FILTER_JSON_FILE),
            "total_alarms_extracted": len(alarms),
            "alarms_file": str(PARSED_ALARMS_FILE),
            "events_file": str(PARSED_EVENTS_FILE) if FETCH_NEW_EVENTS else None,
            "events_summary": events_output,
        }
        write_json_file(FINAL_OUTPUT_FILE, final_output)
        log_info(f"Alarm output saved to {FINAL_OUTPUT_FILE}")

    except requests.HTTPError as exc:
        log_error(f"HTTP error: {exc}")
        if exc.response is not None:
            log_error(f"Response body: {exc.response.text}")
    except requests.ConnectionError as exc:
        log_error(f"Connection error: {exc}")
        log_error("Check EMS IP, protocol, port, routing, and firewall access.")
    except Exception as exc:
        log_error(f"Unhandled exception: {exc}")


if __name__ == "__main__":
    main()
