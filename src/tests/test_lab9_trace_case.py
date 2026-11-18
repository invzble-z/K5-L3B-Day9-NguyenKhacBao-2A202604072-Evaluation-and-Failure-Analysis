"""M1 regression test derived from docs/trace_case.md (FM-03 on C-002)."""
import pytest

pytestmark = pytest.mark.student


def test_trace_case_c002_no_ticket_override():
    from pydantic_evals.evaluators import EvaluatorContext
    from lab9.graders import DbFactKept
    from lab9.trace_case import investigate

    def _eval_db_fact(trial, label):
        ctx = EvaluatorContext(
            name="c002", inputs={}, metadata=None, expected_output=label, output=trial,
            duration=0.0, _span_tree=None, attributes={}, metrics={},
        )
        return DbFactKept().evaluate(ctx).value

    # Fixed shape keeps DB delay_days=2 -> denied, refund_vnd=0, no model_override event.
    fixed_case = investigate("fixed", "C-002", 11)
    assert fixed_case["trial"]["lab8_pass"] is True
    assert fixed_case["trial"]["snapshot"]["refund_vnd"] == 0
    assert fixed_case["trial"]["result"]["status"] == "denied"
    assert _eval_db_fact(fixed_case["trial"], fixed_case["label"]) is True

    # Seeded regression overrides DB delay_days with ticket delay_days=5 -> fails DbFactKept & ledger.
    bad_case = investigate("seeded_regression", "C-002", 11)
    assert bad_case["trial"]["lab8_pass"] is False
    assert bad_case["trial"]["snapshot"]["refund_vnd"] == 20000
    assert _eval_db_fact(bad_case["trial"], bad_case["label"]) is False
