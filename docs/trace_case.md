# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

## Case phân tích (`seeded_regression C-002@11`, tái hiện cùng lỗi trên `swarm C-002@55`)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11` (tái hiện trên `swarm C-002@55` ở `reports/baseline_v1.json`) |
| Triệu chứng | `TrialPass` (`lab8` grader) fail với lý do `status resolved != denied`; `DbFactKept` và `RefundAmountCorrect` đều fail. **Ledger** ghi `refund_vnd=20000`, `refund_count=1` trong khi nhãn mong đợi `refund_vnd=0`, `refund_count=0`, `status=denied`; **reply** nói `"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."` |
| Bước sai đầu tiên | **Event 3** (`kind: model_override`), payload: `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | **Event 1** (`handoff`) truyền đúng hợp đồng `claim_id="C-002"`, `principal_scope="owner_order_only"` và danh sách tool chỉ đọc. **Event 2** (`investigator`) gọi `lookup_order` trả về chính xác dữ liệu DB của `O-202` (`status="delivered"`, `delay_days=2`, chưa đạt ngưỡng `min_delay_days=3`). Ngay tại **Event 3**, agent tin số ngày trong ticket (`"Đơn giao trễ 5 ngày"`) và ghi đè `delay_days` của DB từ `2` thành `5`, dẫn đến sai dây chuyền ở Event 4 (`quote=20000` theo `SHIP-LATE-03`) và ghi tiền sai vào ledger. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) trong `docs/failure_taxonomy.md` |
| Đối chứng | Trên `fixed C-002@11`: Event 1 (`handoff`) và Event 2 (`investigator`) giống hệt, nhưng **không xuất hiện event `model_override`**. Event 3 nhảy thẳng sang `quote` với `{"amount_vnd": 0, "reason": "no_entitlement", "clause_ids": [], "parts": {}}`; ledger giữ `refund_vnd=0`, `refund_count=0`, `status=denied`, `PASS`. |
| Regression test | `test_trace_case_c002_no_ticket_override` trong `src/tests/test_lab9_trace_case.py`: kiểm tra `DbFactKept` + ledger `refund_vnd == 0` + `status == "denied"` — xác nhận fail (phát hiện lỗi) trên `seeded_regression C-002@11` và `swarm C-002@55`, pass trên `fixed C-002@11`. |
| Chưa chắc chắn | Event `model_override` chỉ chứng minh agent có ghi log bước ghi đè; nếu một variant sau này ghi đè thầm lặng không phát event (ví dụ kiểu `quiet_override`), chỉ dựa vào `DbFactKept` sẽ không đủ mà phải kết hợp grader mức outcome (`RefundAmountCorrect` trên ledger) để chặn. |

## Quy tắc tuân thủ
- Đọc **ledger trước reply**: đối chiếu `refund_vnd=20000` với `label=0` trước khi xem câu trả lời.
- "Bước sai đầu tiên" chỉ rõ **Event 3 (`model_override`)** kèm chứng minh Event 1–2 đều đúng.
- Đã có regression test chạy được bằng `pytest` trong `src/tests/test_lab9_trace_case.py`.
