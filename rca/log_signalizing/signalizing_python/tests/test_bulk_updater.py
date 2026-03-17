"""Tests for bulk update payload normalization behavior."""

from src.writer.bulk_updater import BulkActionFactory


def test_sets_rule_level_when_missing() -> None:
    factory = BulkActionFactory()
    action = factory.build(
        source_index="linux-logs",
        target_index="linux-logs-rca",
        source_id="abc",
        source_doc={"message": "sample"},
        selected_signal={"signal": "ssh_fail", "level": "warning"},
    )

    assert action["doc"]["log"]["level"] == "warning"


def test_keeps_existing_when_level_is_valid_short_form() -> None:
    factory = BulkActionFactory()
    action = factory.build(
        source_index="linux-logs",
        target_index="linux-logs-rca",
        source_id="abc",
        source_doc={"message": "sample", "log": {"level": "ERR"}},
        selected_signal={"signal": "ssh_fail", "level": "warning"},
    )

    assert action["doc"]["log"]["level"] == "error"


def test_replaces_existing_when_level_is_invalid() -> None:
    factory = BulkActionFactory()
    action = factory.build(
        source_index="linux-logs",
        target_index="linux-logs-rca",
        source_id="abc",
        source_doc={"message": "sample", "log": {"level": "unclassified"}},
        selected_signal={"signal": "ssh_fail", "level": "critical"},
    )

    assert action["doc"]["log"]["level"] == "critical"


def test_normalizes_numeric_level_to_debug() -> None:
    factory = BulkActionFactory()
    action = factory.build(
        source_index="linux-logs",
        target_index="linux-logs-rca",
        source_id="abc",
        source_doc={"message": "sample", "log": {"level": "7"}},
        selected_signal={"signal": "ssh_fail", "level": "warning"},
    )

    assert action["doc"]["log"]["level"] == "debug"


def test_uses_source_id_when_requested() -> None:
    factory = BulkActionFactory()
    action = factory.build(
        source_index="linux-logs",
        target_index="linux-logs",
        source_id="abc",
        source_doc={"message": "sample"},
        selected_signal={"signal": "ssh_fail", "level": "warning"},
        use_source_id=True,
    )

    assert action["_id"] == "abc"


def test_uses_deterministic_derived_id_by_default() -> None:
    factory = BulkActionFactory()
    action = factory.build(
        source_index="linux-logs",
        target_index="linux-logs-rca",
        source_id="abc",
        source_doc={"message": "sample"},
        selected_signal={"signal": "ssh_fail", "level": "warning"},
    )

    assert action["_id"] == factory._target_id("linux-logs", "abc")
