# Judge audit

Chạy:
```bash
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
```

| Tiêu chí | n | κ | Precision | Recall | Confusion (`tp/fp/fn/tn`, `POS=FAIL`) | Tỉ lệ lỗi quan sát → Rogan-Gladen | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|---|---|
| `tone_ok` | 100 | 0.757 | 0.857 | 0.800 | `tp=24, fp=4, fn=6, tn=66` | `0.280 → 0.300` | **Có (PASS)** | **Dùng được** (chỉ cho tiêu chí giọng điệu, không thay code grader) |
| `helpful` | 100 | 0.375 | 1.000 | 0.300 | `tp=9, fp=0, fn=21, tn=70` | `0.090 → 0.300` | **Không (FAIL)** | **Loại** (cấm dùng làm CI gate) |

## Audit thủ công các case bất đồng (8 case đại diện)

| # | Case | Trích reply | Judge nói | Người nói | Ai đúng? | Phân tích & hành động sửa rubric / hệ thống |
|---|---|---|---|---|---|---|
| 1 | `H-008` (`tone_ok`) | *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* | PASS | FAIL | **Người đúng** | Xưng `"em"`, dùng `"nha"`, `"check"` quá suồng sã; judge bị đánh lừa vì nghe thân thiện. **Sửa rubric:** quy định rõ xưng hô chuẩn CSKH LogiX (`LogiX` – `anh/chị`), đánh `FAIL` với từ lóng/suồng sã (`nha`, `nhé`, `check giúp em`). |
| 2 | `H-029` (`tone_ok`) | *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* | PASS | FAIL | **Người đúng** | Cụm `"không cần nhắn thêm"` mang giọng ra lệnh, xua đuổi khách; judge chỉ bám vào từ khóa `"Dạ, vui lòng"`. **Sửa rubric:** thêm ví dụ few-shot negative cho mẫu lịch sự bề mặt nhưng mang hàm ý đóng/chặn giao tiếp. |
| 3 | `H-042` (`tone_ok`) | *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* | FAIL | PASS | **Người đúng** | Câu ngắn gọn, lịch sự, đủ thông tin nhưng judge phạt vì không có câu xin lỗi (verbosity/apology bias). **Sửa rubric:** nêu rõ câu xác nhận hoàn tiền thành công không bắt buộc phải có lời xin lỗi dài. |
| 4 | `H-051` (`tone_ok`) | *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* | FAIL | PASS | **Người đúng** | Chính sách CSKH cho phép dùng thuật ngữ phổ biến `"refund"`, nhưng judge phạt vì xen tiếng Anh. **Sửa rubric:** bổ sung danh sách từ vay mượn hợp lệ (`refund`, `voucher`, `order`) không bị phạt giọng điệu. |
| 5 | `H-063` (`tone_ok`) | *"Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ."* | PASS | FAIL | **Người đúng** | Agent tự hứa `"sẽ hoàn thêm"` vượt ngoài quyết định hệ thống (rủi ro cam kết sai). **Sửa rubric:** bổ sung tiêu chí đánh `FAIL` nếu reply chứa lời hứa/cam kết không có trong kết quả hệ thống; đồng thời kiểm tra bằng code grader đối chiếu ledger. |
| 6 | `H-070` (`tone_ok`) | *"Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂"* | PASS | FAIL | **Người đúng** | Dùng emoji cười cợt không phù hợp ngữ cảnh xử lý khiếu nại. **Sửa rubric:** cấm emoji đùa cợt/cười trong trả lời khiếu nại (hoặc bắt trực tiếp bằng rule regex trước khi gọi judge). |
| 7 | `H-081` (`tone_ok`) | *"Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ."* | FAIL | PASS | **Judge đúng (lỗi nhãn người)** | Nhãn người đánh nhầm khi đối chiếu ticket; cần **sửa lại golden label** và rà soát quy trình double-annotation (đồng thuận 2 người chấm) cho tập calibration. |
| 8 | `HL-015` & `HL-016` (`helpful`) | *"Dạ, LogiX thành thật xin lỗi… LogiX đã hoàn 55.000đ cho đơn O-404…"* (ledger ghi `35.000đ`) | PASS | FAIL | **Người đúng** | Judge chỉ đọc văn bản nên bị **verbosity/politeness bias** đánh lừa, bỏ lọt hoàn toàn lỗi báo sai số tiền (`FM-08`) so với ledger. **Hành động:** không dùng LLM judge cho tính đúng đắn về tiền bạc; tách sang **code grader** (`RefundAmountCorrect`, `ReplyMatchesLedger`). |

## Kết luận
- **Tiêu chí bị loại — `judge_helpful`:** Dù `Precision = 1.000` (`fp = 0`), nhưng `Recall = 0.300` (`tp = 9, fn = 21`) và `κ = 0.375` thấp hơn nhiều so với ngưỡng sàn (`κ ≥ 0.6`, `R ≥ 0.7`). Ma trận nhầm lẫn cho thấy judge bỏ sót tới **70% lỗi thực tế** (`21/30` case `FAIL` bị chấm nhầm là `PASS`, phần lớn là lỗi báo sai số tiền so với ledger kèm câu xin lỗi dài dòng). Nếu dùng `judge_helpful` làm CI gate, tỉ lệ lỗi quan sát chỉ còn `9%` trong khi tỉ lệ lỗi thực (sau hiệu chỉnh Rogan-Gladen) là `30%`, tạo cảm giác an toàn giả và cho lọt lỗi tài chính nghiêm trọng lên production.
- **Tiêu chí dùng được — `judge_tone`:** Đạt cả ba ngưỡng (`κ = 0.757`, `P = 0.857`, `R = 0.800`), sai số quan sát (`0.280`) gần tỉ lệ thực (`0.300`). Tuy nhiên chỉ dùng để theo dõi **giọng điệu**, tuyệt đối không thay thế code grader cho tiền bạc, quyền truy cập và phê duyệt.
- **Rủi ro còn lại:** Việc hiệu chuẩn hiện chỉ chạy trên dữ liệu replay công khai (`n = 100`); cần thu thập nhãn người mới trên tập **held-out thật** và hiệu chuẩn lại định kỳ mỗi khi thay đổi prompt hoặc model judge.
