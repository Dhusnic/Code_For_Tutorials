"""Tests for automatic rule learning from unclassified critical logs."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.config.settings import RuleLearningConfig
from src.rule_learning.auto_rule_learner import AutoRuleLearner


def _fallback_signal() -> dict[str, object]:
    return {
        "signal": "nginx_unclassified_failure",
        "level": "critical",
        "tags": ["fallback", "unclassified", "critical"],
    }


def test_writes_suggestions_to_separate_folder(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    suggestions_dir = tmp_path / "rules" / "suggestions"
    config = RuleLearningConfig(
        enabled=True,
        mode="suggest",
        output_directory=str(suggestions_dir),
        min_occurrences=2,
        max_candidates_per_service=10,
        min_keyword_count=2,
        max_keywords_per_signal=4,
    )
    learner = AutoRuleLearner(
        config=config,
        rules_directory=str(rules_dir),
        service_rule_files={"nginx": "nginx.yml"},
    )

    learner.observe(
        "nginx",
        {"message": "upstream sent no valid HTTP/1.0 header while reading response header from upstream"},
        _fallback_signal(),
    )
    learner.observe(
        "nginx",
        {"message": "upstream sent no valid HTTP/1.0 header while reading response header from upstream, client: 10.0.0.5"},
        _fallback_signal(),
    )

    written = learner.flush()
    assert written == {"nginx": 1}

    path = suggestions_dir / "nginx.yml"
    assert path.exists()

    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert payload["service"] == "nginx"
    assert len(payload["rules"]) == 1

    rule = payload["rules"][0]
    assert rule["signal_key"].startswith("nginx_auto_")
    assert rule["level"] == "critical"
    assert rule["condition"]["field"] == "message"
    assert rule["condition"]["op"] == "contains"
    assert "upstream" in rule["condition"]["value"]

    # Same pattern should not be emitted repeatedly across flushes.
    learner.observe(
        "nginx",
        {"message": "upstream sent no valid HTTP/1.1 header while reading response header from upstream"},
        _fallback_signal(),
    )
    learner.observe(
        "nginx",
        {"message": "upstream sent no valid HTTP/1.1 header while reading response header from upstream"},
        _fallback_signal(),
    )
    written_again = learner.flush()
    assert written_again == {}


def test_append_mode_writes_to_main_rule_file(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    main_rule_path = rules_dir / "auth.yml"
    main_rule_path.write_text(
        yaml.safe_dump(
            {
                "service": "auth",
                "rules": [
                    {
                        "id": "A_AUTH_UNCLASSIFIED_FAILURE",
                        "signal_key": "auth_unclassified_failure",
                        "level": "critical",
                        "description": "fallback",
                        "tags": ["fallback", "unclassified", "critical"],
                        "condition": {"field": "message", "op": "contains", "value": "authentication failure"},
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    config = RuleLearningConfig(
        enabled=True,
        mode="append",
        output_directory=str(tmp_path / "unused"),
        min_occurrences=2,
        max_candidates_per_service=10,
        min_keyword_count=2,
        max_keywords_per_signal=4,
    )
    learner = AutoRuleLearner(
        config=config,
        rules_directory=str(rules_dir),
        service_rule_files={"auth": "auth.yml"},
    )

    learner.observe(
        "auth",
        {"message": "authentication timeout for invalid user admin from 10.0.0.10"},
        _fallback_signal(),
    )
    learner.observe(
        "auth",
        {"message": "authentication timeout for invalid user root from 10.0.0.11"},
        _fallback_signal(),
    )

    written = learner.flush()
    assert written == {"auth": 1}

    payload = yaml.safe_load(main_rule_path.read_text(encoding="utf-8"))
    assert payload["service"] == "auth"
    assert len(payload["rules"]) == 2
    assert payload["rules"][-1]["signal_key"].startswith("auth_auto_")

