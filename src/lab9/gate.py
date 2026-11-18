"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def _is_nonfinite(v: object) -> bool:
    return isinstance(v, float) and not math.isfinite(v)


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []

    # 1. NaN / inf in aggregate metrics
    for mid, val in (pr.get("metrics") or {}).items():
        if _is_nonfinite(val):
            problems.append(f"metric {mid} is non-finite ({val!r})")

    # 2. Evaluator failures must be empty
    ev_failures = pr.get("evaluator_failures") or []
    if ev_failures:
        problems.append(f"evaluator_failures non-empty ({len(ev_failures)}): {ev_failures[0]}")

    # 3. Row count vs manifest and duplicate (item_id, seed) detection
    pr_rows = pr.get("rows") or []
    base_rows = base.get("rows") or []
    manifest = pr.get("manifest") or {}
    expected_rows = int(manifest.get("items") or 0) * len(manifest.get("seeds") or [])
    if len(pr_rows) != expected_rows:
        problems.append(f"row count {len(pr_rows)} != manifest items*seeds ({expected_rows})")

    pr_pairs = [(r.get("item_id"), r.get("seed")) for r in pr_rows]
    if len(pr_pairs) != len(set(pr_pairs)):
        problems.append(f"duplicate (item_id, seed) rows detected ({len(pr_pairs) - len(set(pr_pairs))} dup)")

    # 4. (item_id, seed) set must match baseline exactly
    base_pairs = [(r.get("item_id"), r.get("seed")) for r in base_rows]
    if set(pr_pairs) != set(base_pairs):
        missing = len(set(base_pairs) - set(pr_pairs))
        extra = len(set(pr_pairs) - set(base_pairs))
        problems.append(f"(item_id, seed) set differs from baseline (missing={missing}, extra={extra})")

    # 5. Graded spec metrics must not be None or non-finite in any row
    base_row_keys = set(base_rows[0].keys()) if base_rows else set()
    graded_ids = [
        m["id"]
        for m in (spec.get("metrics") or [])
        if m["id"] in GRADERS or m["id"] in base_row_keys
    ]
    bad_cells = 0
    first_bad: str | None = None
    for r in pr_rows:
        for mid in graded_ids:
            v = r.get(mid)
            if v is None or _is_nonfinite(v):
                bad_cells += 1
                if first_bad is None:
                    first_bad = f"{r.get('item_id')}@{r.get('seed')}.{mid}={v!r}"
    if bad_cells:
        problems.append(f"{bad_cells} row cell(s) have None/non-finite graded metric (first: {first_bad})")

    # 6. Slice tags of each (item_id, seed) must match baseline
    base_slices = {(r.get("item_id"), r.get("seed")): frozenset(r.get("slices") or []) for r in base_rows}
    slice_mismatches = [
        f"{r.get('item_id')}@{r.get('seed')}"
        for r in pr_rows
        if (r.get("item_id"), r.get("seed")) in base_slices
        and frozenset(r.get("slices") or []) != base_slices[(r.get("item_id"), r.get("seed"))]
    ]
    if slice_mismatches:
        problems.append(f"slice tags differ from baseline on {len(slice_mismatches)} row(s) (first: {slice_mismatches[0]})")

    # 7. Ratchet check when base_spec is supplied for the same eval-set version
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        cur_metrics = {m["id"]: m for m in (spec.get("metrics") or [])}
        for bm in (base_spec.get("metrics") or []):
            mid = bm["id"]
            if mid not in cur_metrics:
                problems.append(f"ratchet: metric {mid} removed")
                continue
            cm = cur_metrics[mid]
            if bm.get("blocking") and not cm.get("blocking"):
                problems.append(f"ratchet: metric {mid} downgraded from blocking to non-blocking")
            bth = bm.get("threshold") or {}
            cth = cm.get("threshold") or {}
            if "min" in bth and ("min" not in cth or cth["min"] < bth["min"]):
                problems.append(f"ratchet: metric {mid} min loosened ({bth.get('min')} -> {cth.get('min')})")
            if "max" in bth and ("max" not in cth or cth["max"] > bth["max"]):
                problems.append(f"ratchet: metric {mid} max loosened ({bth.get('max')} -> {cth.get('max')})")
            if "max_increase" in bth and ("max_increase" not in cth or cth["max_increase"] > bth["max_increase"]):
                problems.append(
                    f"ratchet: metric {mid} max_increase loosened ({bth.get('max_increase')} -> {cth.get('max_increase')})"
                )
            if bth.get("no_significant_drop") and not cth.get("no_significant_drop"):
                problems.append(f"ratchet: metric {mid} dropped no_significant_drop")

        cur_slices = {(s["name"], s["metric"]): s for s in (spec.get("slices") or [])}
        for bs in (base_spec.get("slices") or []):
            skey = (bs["name"], bs["metric"])
            sname = f"{bs['name']}/{bs['metric']}"
            if skey not in cur_slices:
                problems.append(f"ratchet: slice {sname} removed")
                continue
            cs = cur_slices[skey]
            if bs.get("blocking") and not cs.get("blocking"):
                problems.append(f"ratchet: slice {sname} downgraded from blocking to non-blocking")
            if "min" in bs and ("min" not in cs or cs["min"] < bs["min"]):
                problems.append(f"ratchet: slice {sname} min loosened ({bs.get('min')} -> {cs.get('min')})")
            if "max" in bs and ("max" not in cs or cs["max"] > bs["max"]):
                problems.append(f"ratchet: slice {sname} max loosened ({bs.get('max')} -> {cs.get('max')})")
            if bs.get("no_significant_drop") and not cs.get("no_significant_drop"):
                problems.append(f"ratchet: slice {sname} dropped no_significant_drop")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name, mid = s["name"], s["metric"]
        a = per_item(pr, mid, slice_name=name)
        b = per_item(base, mid, slice_name=name)
        val = round(sum(a.values()) / len(a), 4) if a else None
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "min" in s and val < s["min"]:
            verdict = "fail"
        elif "max" in s and val > s["max"]:
            verdict = "fail"
        if s.get("no_significant_drop") and val is not None:
            keys = sorted(set(a) & set(b))
            if not keys:
                verdict = "missing"
            else:
                d, lo, hi = stats.paired_bootstrap(
                    [a[k] for k in keys],
                    [b[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                )
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        sid = f"slice:{name}/{mid}"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        lines.append(f"  {sid:<28} {val!s:<8} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
