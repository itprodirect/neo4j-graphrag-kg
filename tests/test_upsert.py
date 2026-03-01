"""Unit tests for batched upsert helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from neo4j_graphrag_kg.upsert import _run_batch


def test_run_batch_uses_execute_write_with_batches() -> None:
    driver = MagicMock()
    session_cm = MagicMock()
    session = MagicMock()
    session_cm.__enter__.return_value = session
    driver.session.return_value = session_cm

    rows = [{"id": i} for i in range(1200)]
    total = _run_batch(driver, "neo4j", "UNWIND $rows AS row RETURN row", rows, batch_size=500)

    assert total == 1200
    driver.session.assert_called_once_with(database="neo4j")
    assert session.execute_write.call_count == 3

    batch_sizes = [len(call.args[2]) for call in session.execute_write.call_args_list]
    assert batch_sizes == [500, 500, 200]


def test_run_batch_empty_rows_is_noop() -> None:
    driver = MagicMock()
    session_cm = MagicMock()
    session = MagicMock()
    session_cm.__enter__.return_value = session
    driver.session.return_value = session_cm

    total = _run_batch(driver, "neo4j", "UNWIND $rows AS row RETURN row", [], batch_size=500)

    assert total == 0
    driver.session.assert_called_once_with(database="neo4j")
    session.execute_write.assert_not_called()
