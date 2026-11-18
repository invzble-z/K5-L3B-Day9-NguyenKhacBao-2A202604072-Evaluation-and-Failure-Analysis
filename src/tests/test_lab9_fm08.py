"""M3 unit tests for FM-08 grader (ReplyMatchesLedger)."""
import pytest

pytestmark = pytest.mark.student


def _ctx(refund_vnd, reply_text=None):
    from pydantic_evals.evaluators import EvaluatorContext

    events = [{"kind": "reply", "payload": {"text": reply_text}}] if reply_text is not None else []
    trial = {
        "snapshot": {"refund_vnd": refund_vnd, "refund_count": 1 if refund_vnd > 0 else 0},
        "unexpected_rows": 0,
        "blob": "",
        "events": events,
        "result": {},
        "lab8_pass": True,
        "lab8_reason": None,
    }
    return EvaluatorContext(
        name="fm08", inputs={}, metadata=None,
        expected_output={"refund_vnd": refund_vnd, "approval_ok": True},
        output=trial, duration=0.0, _span_tree=None, attributes={}, metrics={},
    )


def test_reply_matches_ledger_exact_match():
    from lab9.graders import ReplyMatchesLedger

    assert ReplyMatchesLedger().evaluate(_ctx(20000, "Dạ, LogiX đã hoàn 20.000đ cho đơn O-808.")).value is True
    assert ReplyMatchesLedger().evaluate(_ctx(35000, "LogiX đã hoàn phí 35,000 VND cho đơn O-107 ạ.")).value is True
    assert ReplyMatchesLedger().evaluate(_ctx(0, "Dạ, đơn O-202 chưa đủ điều kiện hoàn.")).value is True
    assert ReplyMatchesLedger().evaluate(_ctx(35000, None)).value is True


def test_reply_matches_ledger_catches_fm08_misreport():
    from lab9.graders import ReplyMatchesLedger

    res = ReplyMatchesLedger().evaluate(_ctx(20000, "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."))
    assert res.value is False
    assert "35000" in (res.reason or "")

    res_denied = ReplyMatchesLedger().evaluate(_ctx(0, "Dạ, LogiX đã hoàn 35.000đ cho đơn O-909."))
    assert res_denied.value is False

    res_omit = ReplyMatchesLedger().evaluate(_ctx(20000, "Dạ, LogiX đã xử lý xong đơn O-808."))
    assert res_omit.value is False
