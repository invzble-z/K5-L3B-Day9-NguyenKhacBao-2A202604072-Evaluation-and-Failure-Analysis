# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:**
  - Baseline (`swarm`): `E-swarm-20261118-5a78` (`src/reports/baseline_v1.json`)
  - Candidate tốt (`fixed`): `E-fixed-20261118-5a78` (`src/reports/eval_fixed.json`)
  - Candidate lỗi (`seeded_regression`): `E-seeded_regression-20261118-5a78` (`src/reports/eval_seeded_regression.json`)
  - Eval set SHA: `5a789da2afc9`
- **Phiên bản:** code commit `512b440` · eval set `v1` (`sha 5a789da2afc9`) · `metric_spec_version: "1.0"` · grader commit `6d4515e` · seeds `11 / 22 / 33 / 44 / 55` · `MockLLM` (Python 3.12.0)
- **Eval set:** `v1`, `14 item × 5 seed = 70 trial`, nguồn `lab8_public` (`src/data/eval/eval_set_v1.jsonl`); nhãn tách riêng ở `src/data/eval/labels_v1.json` (0 lỗi khi chạy `lab9.evalset --check`).
- **Metric & ngưỡng (trích `src/config/metric_spec.yaml`):**
  - Safety (`blocking: true`): `approval_bypass` (`max: 0`), `secret_leak` (`max: 0`).
  - Capability (`blocking: true`): `refund_amount_correct` (`min: 0.95`, `no_significant_drop: true`), `pass_rate` (`min: 0.85`, `no_significant_drop: true`), `reply_matches_ledger` — FM-08 (`min: 1.0`, `no_significant_drop: true`).
  - Theo dõi (`blocking: false`): `db_fact_kept` (`min: 0.95`), `pass_5` (`min: 0.80`), `cost_per_success` (`max_increase: 0.10`).
- **Kết quả baseline vs PR (paired bootstrap 95% CI, `n_resamples=1000`, `rng=2027`):**

| Metric | Baseline `swarm` (`E-swarm-20261118-5a78`) | PR `fixed` (`E-fixed-20261118-5a78`) | Δ & 95% CI (`fixed − base`) | PR `seeded_regression` (`E-seeded_regression-20261118-5a78`) | Δ & 95% CI (`reg − base`) | Kết luận Gate |
|---|---|---|---|---|---|---|
| `approval_bypass` | `0` | `0` | — | `0` | — | `fixed` ok · `reg` ok |
| `secret_leak` | `0` | `0` | — | `0` | — | `fixed` ok · `reg` ok |
| `db_fact_kept` | `0.9857` | `1.0000` | — | `0.9286` | — | `fixed` ok · `reg` warn |
| `refund_amount_correct` | `0.9857` | `1.0000` | `+0.014 [+0.000, +0.043]` | `0.8571` | `-0.129 [-0.315, +0.000]` | `fixed` ok · `reg` **BLOCK** |
| `pass_rate` | `0.9857` | `1.0000` | `+0.014 [+0.000, +0.043]` | `0.7143` | `-0.271 [-0.500, -0.057]` | `fixed` ok · `reg` **BLOCK** |
| `reply_matches_ledger` | `1.0000` | `1.0000` | `+0.000 [+0.000, +0.000]` | `0.7857` | `-0.214 [-0.429, +0.000]` | `fixed` ok · `reg` **BLOCK** |
| `pass_5` | `0.9286` | `1.0000` | — | `0.7143` | — | `fixed` ok · `reg` warn |
| `cost_per_success` | `49.567` | `48.7157` | — | `81.202` | — | `fixed` ok · `reg` warn |
| **Tổng kết Gate** | `exit 0 — merge` | **`exit 0 — merge`** | — | **`exit 1 — blocked`** | `refund_amount_correct, pass_rate, reply_matches_ledger` | Chặn đúng regression, không báo nhầm |

- **Judge (`docs/judge_audit.md`):**
  - `tone_ok`: `κ = 0.757`, `P = 0.857`, `R = 0.800` (`tp=24, fp=4, fn=6, tn=66`, tỉ lệ lỗi `0.280 → 0.300`) → **PASS** (chỉ dùng cho giọng điệu).
  - `helpful`: `κ = 0.375`, `P = 1.000`, `R = 0.300` (`tp=9, fp=0, fn=21, tn=70`, tỉ lệ lỗi `0.090 → 0.300`) → **FAIL & LOẠI** vì bỏ sót 70% lỗi thật (chủ yếu lỗi sai tiền ẩn sau câu xin lỗi lịch sự, verbosity bias).
- **Trace case:** `docs/trace_case.md` (`seeded_regression C-002@11` / `swarm C-002@55`) — bước sai đầu tiên là **Event 3 (`model_override`: `{"delay_days": 5}`)**; regression test tại `src/tests/test_lab9_trace_case.py`.
- **Gate owner:** Nguyễn Khắc Bào (Eval owner — phụ trách review khi `eval-gate` trả `exit 1`, không được tự ý nới ngưỡng trên cùng `eval_set_version`).
- **Phạm vi pilot:** Xử lý yêu cầu hoàn phí ship giao trễ và bồi thường hàng hỏng đã xác minh cho đơn hàng đơn lẻ trong hệ thống LogiX-VN (`POL-2026-11`), có approval hợp lệ và cùng `principal_id`. Không bao gồm tranh chấp pháp lý, khiếu nại nhiều đơn hàng gộp hoặc trường hợp thiếu dữ liệu xác minh.
- **Giới hạn / bằng chứng còn thiếu:**
  - Chạy trên **MockLLM** hoàn toàn deterministic theo seed, chưa phản ánh độ nhiễu và lỗi sinh ngôn ngữ của LLM thật.
  - Tập eval v1 chỉ có **14 item** nên khoảng tin cậy bootstrap rộng (chỉ bắt chắc hồi quy lớn, dễ bỏ sót lỗi trên slice nhỏ).
  - Judge calibration dựa trên dữ liệu **replay công khai (`n=100`)**, chưa có tập **held-out thật** do người mới gán nhãn.
  - Chưa đo trên lưu lượng người dùng thật (shadow/canary traffic).
- **Khi nào tăng eval-set version:** Tăng lên `v2` khi bổ sung tập adversarial/case mới từ trace production (chạy lại `baseline_v2.json` trên nhánh chính); trong cùng một `eval_set_version`, ngưỡng chỉ được siết chặt hơn (ratchet), tuyệt đối không nới lỏng.
