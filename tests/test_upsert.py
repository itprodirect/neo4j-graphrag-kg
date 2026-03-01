"""Unit tests for batched upsert helpers."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

import neo4j_graphrag_kg.upsert as upsert_mod
from neo4j_graphrag_kg.upsert import _UPSERT_DOCUMENT, _execute_write_with_retry, _run_batch


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


@pytest.mark.parametrize(
    "transient_exc",
    [TransientError, ServiceUnavailable, SessionExpired],
)
def test_execute_write_with_retry_retries_once_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    transient_exc: type[Exception],
) -> None:
    session = MagicMock()
    session.execute_write.side_effect = [transient_exc("transient"), None]

    sleep_calls: list[float] = []
    monkeypatch.setattr(upsert_mod.time, "sleep", lambda s: sleep_calls.append(s))

    callback = MagicMock()
    rows = [{"id": "x"}]
    _execute_write_with_retry(
        session,
        callback,
        "UNWIND $rows AS row RETURN row",
        rows,
        max_attempts=3,
        base_backoff_s=0.2,
    )

    assert session.execute_write.call_count == 2
    assert sleep_calls == [0.2]
    session.execute_write.assert_called_with(callback, "UNWIND $rows AS row RETURN row", rows)


def test_execute_write_with_retry_raises_after_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock()
    session.execute_write.side_effect = SessionExpired("expired")

    sleep_calls: list[float] = []
    monkeypatch.setattr(upsert_mod.time, "sleep", lambda s: sleep_calls.append(s))

    with pytest.raises(SessionExpired):
        _execute_write_with_retry(
            session,
            MagicMock(),
            "UNWIND $rows AS row RETURN row",
            [{"id": "x"}],
            max_attempts=3,
            base_backoff_s=0.2,
        )

    assert session.execute_write.call_count == 3
    assert sleep_calls == [0.2, 0.4]


def test_upsert_document_preserves_created_at_on_reingest_contract() -> None:
    assert "ON CREATE SET d.created_at = row.created_at" in _UPSERT_DOCUMENT
    assert "SET d.created_at = row.created_at" not in _UPSERT_DOCUMENT.replace(
        "ON CREATE SET d.created_at = row.created_at",
        "",
    )
