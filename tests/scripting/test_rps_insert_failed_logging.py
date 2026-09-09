"""RPS insert-fail path must log str/repr so Arch debug shows UNO errors."""

from __future__ import annotations

import logging
from unittest.mock import patch

from plugin.scripting.helper_domain import rps_insert_failed_outcome


def test_rps_insert_failed_outcome_logs_type_str_repr(caplog):
    err = RuntimeError("insertDocumentFromURL")
    with caplog.at_level(logging.ERROR, logger="writeragent.scripting"):
        out = rps_insert_failed_outcome(err, t0=0.0)
    assert out["ok"] is False
    assert "insertDocumentFromURL" in out["message"]
    assert any("rps_insert_failed_outcome" in r.message for r in caplog.records)
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert "RuntimeError" in joined
    assert "insertDocumentFromURL" in joined
