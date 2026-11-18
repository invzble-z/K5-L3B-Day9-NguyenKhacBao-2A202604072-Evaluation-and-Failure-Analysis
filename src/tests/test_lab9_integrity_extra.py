"""Extra M5-M7 tests covering hidden trap patterns and edge cases."""
import copy
import pytest

pytestmark = pytest.mark.student


def _report(rows, metrics, items=4, seeds=(1, 2), evaluator_failures=None):
    return {
        "manifest": {"eval_set_sha": "x", "items": items, "seeds": list(seeds)},
        "rows": rows,
        "metrics": metrics,
        "evaluator_failures": list(evaluator_failures or []),
    }


ROWS = [
    {"item_id": f"E-{i:03d}", "seed": s, "pass_rate": True, "slices": ["denial"] if i < 2 else ["money_movement"]}
    for i in range(4)
    for s in (1, 2)
]
SPEC = {
    "eval_set_version": "v2",
    "metrics": [
        {"id": "pass_rate", "kind": "capability", "blocking": True, "threshold": {"min": 0.85, "no_significant_drop": True}},
        {"id": "approval_bypass", "kind": "safety", "blocking": True, "threshold": {"max": 0}},
    ],
    "slices": [
        {"name": "denial", "metric": "pass_rate", "min": 0.90, "no_significant_drop": True, "blocking": True},
    ],
}


def test_integrity_catches_hidden_traps_advanced():
    from lab9 import gate

    base_rows = [{**r, "approval_bypass": False} for r in ROWS]
    base = _report(copy.deepcopy(base_rows), {"pass_rate": 1.0, "approval_bypass": 0})
    assert gate.integrity_check(base, base, SPEC, SPEC) == []

    # Hidden trap 1: duplicate row replacing a dropped row (total row count unchanged)
    dup_rows = copy.deepcopy(base_rows[:-1]) + [copy.deepcopy(base_rows[0])]
    assert gate.integrity_check(_report(dup_rows, {"pass_rate": 1.0, "approval_bypass": 0}), base, SPEC)

    # Hidden trap 2: non-empty evaluator_failures on an otherwise green report
    green_with_err = _report(copy.deepcopy(base_rows), {"pass_rate": 1.0, "approval_bypass": 0}, evaluator_failures=["E-001@1:Grader:boom"])
    assert gate.integrity_check(green_with_err, base, SPEC)

    # Hidden trap 3: None cell for a graded metric even when aggregate metric is finite
    none_rows = copy.deepcopy(base_rows)
    none_rows[0]["pass_rate"] = None
    assert gate.integrity_check(_report(none_rows, {"pass_rate": 1.0, "approval_bypass": 0}), base, SPEC)

    # Hidden trap 4: relabelling slice tags out of a protected slice
    relabelled = copy.deepcopy(base_rows)
    relabelled[0]["slices"] = []
    assert gate.integrity_check(_report(relabelled, {"pass_rate": 1.0, "approval_bypass": 0}), base, SPEC)

    # Hidden trap 5: inf metric
    assert gate.integrity_check(_report(copy.deepcopy(base_rows), {"pass_rate": float("inf"), "approval_bypass": 0}), base, SPEC)

    # Hidden trap 6: ratchet checks on blocking, max, no_significant_drop, and slices
    for mut in (
        lambda s: s["metrics"][0].update({"blocking": False}),
        lambda s: s["metrics"][0]["threshold"].pop("no_significant_drop"),
        lambda s: s["metrics"][1]["threshold"].update({"max": 1}),
        lambda s: s["slices"][0].update({"min": 0.5}),
        lambda s: s["slices"][0].pop("no_significant_drop"),
        lambda s: s["slices"].clear(),
    ):
        bad_spec = copy.deepcopy(SPEC)
        mut(bad_spec)
        assert gate.integrity_check(base, base, bad_spec, SPEC)


def test_pass_k_hidden_invalid_args_advanced():
    from lab9 import stats

    for bad in [(0, 0, 1), (-1, 0, 1), (5, -1, 1), (5, 2, -1), (True, 1, 1), (5, True, 1)]:
        with pytest.raises(ValueError):
            stats.pass_at_k(*bad)
        with pytest.raises(ValueError):
            stats.pass_hat_k(*bad)
