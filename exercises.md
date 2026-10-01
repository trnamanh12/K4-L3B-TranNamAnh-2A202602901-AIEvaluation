# Day 14 — Exercises

## AI Evaluation & Benchmarking · Lab Worksheet

**Thời gian làm bài:** 9:15–12:00

**Domain:** OrbitTech Store Customer Support

Điền trực tiếp câu trả lời vào file này. Golden dataset 20 QA được viết một lần
duy nhất trong `golden_dataset.json`, không chép lại toàn bộ vào Markdown.

---

Từ 9:15–9:30, cài môi trường và chạy baseline tests theo `guide_lab.md`.

---

## Part 1 — Warm-up (9:30–9:45)

### Exercise 1.1 — RAGAS Metric Thresholds

Theo bài giảng:

- 0.8–1.0: Good — monitor, maintain.
- 0.6–0.8: Needs work — analyze failures, iterate.
- Dưới 0.6: Significant issues — investigate.

Với từng metric, xác định khi nào score thấp có thể chấp nhận và khi nào là
critical.

| Metric | Acceptable Low Score Scenario | Critical Low Score Scenario | Action Required |
|---|---|---|---|
| Faithfulness | Nếu câu hỏi nằm ngoài tài liệu, điểm thấp có thể chấp nhận khi trợ lý nói rõ là chưa có thông tin và không đoán. | Nếu trợ lý khẳng định sai về giá, chính sách hay đơn hàng thì đây là lỗi nghiêm trọng. | Đối chiếu câu trả lời với tài liệu để tìm phần nào không có căn cứ. Nếu lỗi ảnh hưởng khách hàng hoặc lặp lại, chưa nên deploy. |
| Answer Relevance | Câu hỏi hơi mơ hồ nên câu trả lời có thêm một chút giải thích, nhưng vẫn trả lời đúng điều khách hỏi. | Câu trả lời đi sang chuyện khác hoặc không giải quyết được yêu cầu chính. | Xem lại những câu bị lệch để chỉnh prompt hoặc cách phân loại câu hỏi, rồi chạy lại các trường hợp đó. |
| Context Recall | Với câu hỏi đơn giản không cần tra cứu, hoặc corpus vốn không có thông tin đó, recall thấp chưa chắc là vấn đề. | Câu hỏi cần thông tin cụ thể nhưng tài liệu lấy về thiếu ý quan trọng, khiến trợ lý phải tự đoán. | Kiểm tra tài liệu và cách chia đoạn, sau đó chỉnh truy vấn hoặc bổ sung nguồn còn thiếu. |
| Context Precision | Truy vấn rộng có thể lấy vài đoạn chỉ liên quan một phần; vẫn chấp nhận được nếu đoạn cần thiết được tìm thấy và xếp đủ cao. | Kết quả đầu toàn đoạn không liên quan, còn bằng chứng cần thiết bị đẩy xuống dưới hoặc không được lấy về. | Xem lại các đoạn theo thứ tự xếp hạng, lọc bớt nhiễu và thử điều chỉnh reranking. |
| Completeness | Nếu khách chỉ hỏi một ý thì câu trả lời ngắn vẫn ổn, miễn là đã trả lời đủ ý đó. | Câu trả lời bỏ mất một bước, điều kiện hoặc thông tin quan trọng trong đáp án chuẩn. | So từng ý trong đáp án chuẩn với câu trả lời để biết đang thiếu gì, rồi sửa và chạy lại các case đó. |

### Exercise 1.2 — Bias trong LLM-as-a-Judge

Ba bias thường gặp:

- Position bias: judge ưu tiên answer xuất hiện trước.
- Verbosity bias: judge ưu tiên answer dài hơn.
- Self-preference: judge ưu tiên output giống chính model đó.

**Câu 1: Thiết kế experiment phát hiện position bias với ít nhất hai conditions.**

> Mình sẽ chuẩn bị nhiều cặp A/B có chất lượng tương đương. Ở lượt đầu cho judge xem A trước B, lượt sau đảo thành B trước A; câu hỏi, rubric và nội dung giữ nguyên. Sau đó so xem judge có đổi lựa chọn chỉ vì thứ tự không. Nếu có, đó là dấu hiệu position bias. Nên lặp trên nhiều câu hỏi để tránh kết luận từ một ví dụ.

**Câu 2: Làm thế nào giảm verbosity bias bằng rubric design?**

> Rubric nên chấm những điểm cụ thể như đúng thông tin, trả lời đúng câu hỏi và có đủ ý cần thiết. Ghi rõ câu trả lời dài không tự động được điểm cao hơn; phần giải thích lặp hoặc không liên quan không được tính thêm. Như vậy câu ngắn nhưng đủ ý vẫn có thể đạt điểm tối đa.

**Câu 3: Tại sao cần calibrate LLM judge với human labels?**

> Cần so điểm của judge với người thật để biết judge đang chấm có sát và ổn định không. Nếu thường xuyên chấm lệch ở một loại câu hỏi, mình có thể sửa rubric hoặc điều chỉnh ngưỡng. Người đánh giá cũng có thể bất đồng với nhau, nên cần xem các trường hợp đó thay vì coi nhãn của một người là tuyệt đối.

### Exercise 1.3 — Evaluation trong CI/CD

**Câu 1: Chọn threshold để block deployment.**

| Metric | Threshold | Lý do |
|---|---:|---|
| Faithfulness | 0.80 | Mình đặt ngưỡng này cao vì câu trả lời hỗ trợ khách hàng không nên tự đưa ra thông tin không có trong tài liệu. |
| Answer Relevance | 0.70 | Cho phép câu trả lời diễn đạt khác câu hỏi một chút, nhưng vẫn phải giải quyết đúng nhu cầu chính. |
| Completeness | 0.70 | Không cần viết dài, nhưng các ý quan trọng trong đáp án chuẩn phải được nhắc đến. |

**Câu 2: Khi nào dùng offline evaluation, online evaluation và human review?**

> Mình dùng offline evaluation trước khi deploy và mỗi khi đổi prompt, model hoặc retrieval để so với golden set. Sau khi deploy, online evaluation giúp theo dõi câu hỏi thực tế và phát hiện chất lượng giảm theo thời gian. Human review phù hợp với câu trả lời rủi ro cao, điểm thấp hoặc trường hợp judge không chắc; cũng nên kiểm tra ngẫu nhiên một số câu để chắc rằng judge vẫn chấm hợp lý.

---

## Part 2 — Core Coding (9:45–10:40)

Hoàn thiện các TODO bắt buộc trong `template.py`.

### Task 1 — Data Models

- `QAPair`: question, expected answer, gold context, metadata và retrieved contexts.
- `EvalResult`: answer-side scores, optional retrieval scores, pass/failure fields.
- `overall_score()`: trung bình Faithfulness, Relevance và Completeness.

### Task 2 — RAGASEvaluator

Answer-side:

- `evaluate_faithfulness(answer, context)`
- `evaluate_relevance(answer, question)`
- `evaluate_completeness(answer, expected)`

Retrieval-side:

- `evaluate_context_recall(contexts, expected)`
- `evaluate_context_precision(contexts, expected)`

Full pipeline:

- `run_full_eval(..., contexts=None)` luôn tính ba answer metrics.
- Nếu có `contexts`, tính và lưu thêm Context Recall và Context Precision.
- Retrieval scores không làm thay đổi `overall_score()` và pass rule gốc.

### Task 3 — LLMJudge

- `score_response(question, answer, rubric)`
- `detect_bias(scores_batch)`

### Task 4 — BenchmarkRunner

- `run(qa_pairs, agent_fn, evaluator)`
- `generate_report(results)`
- `run_regression(new_results, baseline_results)`
- `identify_failures(results, threshold)`

`BenchmarkRunner.run()` phải truyền `pair.retrieved_contexts` vào
`run_full_eval()`. Report phải có average của hai retrieval metrics.

### Task 5 — FailureAnalyzer

- `categorize_failures(failures)`
- `find_root_cause(failure)`
- `generate_improvement_suggestions(failures)`
- `generate_improvement_log(failures, suggestions)`

Kiểm tra:

```bash
pytest tests/ -v
```

`rerank_by_overlap()` là TODO bonus của Exercise 3.5. Test tương ứng được skip
nếu bạn chưa làm bonus.

---

## Part 3 — Golden Dataset & Real Benchmark (10:40–11:35)

### Exercise 3.1 — Build the Golden Dataset

Thiết kế và validate dataset theo Mục 5–6 trong `guide_lab.md`. Nội dung 20 QA
được điền trực tiếp trong `golden_dataset.json`; phần dưới chỉ ghi lại kết quả
và quyết định thiết kế, không chép lại toàn bộ QA.

**Kết quả dataset**

| Hạng mục | Kết quả |
|---|---|
| Tổng số records | ____ / 20 |
| Easy | ____ / 5 |
| Medium | ____ / 7 |
| Hard | ____ / 5 |
| Adversarial | ____ / 3 |
| Source documents được sử dụng | ____ / 10 |
| Validator status | PASS / FAIL |

**Ba case đại diện cho quyết định thiết kế**

| ID | Difficulty | Source document(s) | Vì sao case phù hợp với difficulty/attack type? |
|---|---|---|---|
| | | | |
| | | | |
| | | | |

**Điểm khó nhất khi xây dựng expected answer hoặc evidence là gì?**

> *Câu trả lời:*

**Xác nhận:**

- [ ] Mọi claim trong expected answer đều có evidence hỗ trợ.
- [ ] Không có questions trùng ý và không dùng kiến thức ngoài corpus.
- [ ] `python validate_golden_dataset.py` báo `PASS`.

### Exercise 3.2 — Benchmark Run

Chạy:

```bash
python domain_assistant.py
python evaluate_answers.py
```

Copy bảng terminal vào đây hoặc điền từ `artifacts/benchmark_results.json`.

| ID | Question (short) | Ctx Recall | Ctx Precision | Faithfulness | Relevance | Completeness | Overall | Passed? | Failure Type |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| E01 | | | | | | | | | |
| E02 | | | | | | | | | |
| E03 | | | | | | | | | |
| E04 | | | | | | | | | |
| E05 | | | | | | | | | |
| M01 | | | | | | | | | |
| M02 | | | | | | | | | |
| M03 | | | | | | | | | |
| M04 | | | | | | | | | |
| M05 | | | | | | | | | |
| M06 | | | | | | | | | |
| M07 | | | | | | | | | |
| H01 | | | | | | | | | |
| H02 | | | | | | | | | |
| H03 | | | | | | | | | |
| H04 | | | | | | | | | |
| H05 | | | | | | | | | |
| A01 | | | | | | | | | |
| A02 | | | | | | | | | |
| A03 | | | | | | | | | |

**Aggregate Report**

- Overall pass rate: ____%
- Avg Context Recall: ____
- Avg Context Precision: ____
- Avg Faithfulness: ____
- Avg Relevance: ____
- Avg Completeness: ____
- Failure type distribution: ____

**Ba cases có Overall Score thấp nhất**

1. ID: ____ | Score: ____ | Failure type: ____
2. ID: ____ | Score: ____ | Failure type: ____
3. ID: ____ | Score: ____ | Failure type: ____

**Nhận xét ngắn:** Metric nào yếu nhất? Kết quả gợi ý vấn đề nằm ở retrieval
hay generation?

> *Câu trả lời:*

### Exercise 3.3 — LLM-as-a-Judge Rubric Design

Thiết kế rubric domain-specific cho OrbitTech Customer Support. Mỗi mức phải
đủ cụ thể để hai người chấm độc lập có thể hiểu giống nhau.

Chọn 3–5 dimensions:

- [ ] Correctness
- [ ] Completeness
- [ ] Relevance
- [ ] Evidence/citation
- [ ] Actionability
- [ ] Safety/privacy
- [ ] Tone/clarity
- [ ] Dimension khác: __________

| Score | Tiêu chí domain-specific | Ví dụ response |
|---:|---|---|
| 5 | | |
| 4 | | |
| 3 | | |
| 2 | | |
| 1 | | |

**Ba edge cases khó chấm**

| Edge Case | Tại sao khó chấm? | Rubric xử lý thế nào? |
|---|---|---|
| | | |
| | | |
| | | |

**Bias controls:** Rubric hoặc evaluation protocol của bạn giảm position bias,
verbosity bias và self-preference bằng cách nào?

> *Câu trả lời:*

### Exercise 3.4 — Framework Comparison (Bonus +5)

Chỉ làm sau khi hoàn thành 3.1–3.3. Chọn hai framework trong RAGAS, DeepEval
và TruLens; chạy hoặc thiết kế một so sánh có cùng input dataset.

| Tiêu chí | Framework 1: ____ | Framework 2: ____ |
|---|---|---|
| Setup complexity | | |
| Metrics available | | |
| CI/CD integration | | |
| Kết quả trên cùng dataset | | |
| Insight rút ra | | |

- Scores có nhất quán không?
- Framework nào strict hơn và vì sao?
- Hai framework có tìm ra cùng failure cases không?

> *Phân tích:*

### Exercise 3.5 — Retrieval Reranking (Bonus +5)

Mục tiêu: kiểm tra việc đổi thứ tự chunks có tăng Context Precision mà không
thay đổi Context Recall hay không.

1. Chọn ít nhất 5 cases từ `artifacts/actual_answers.json`.
2. Tính Context Recall và Context Precision trước rerank.
3. Implement `rerank_by_overlap()` hoặc một reranker khác.
4. Rerank cùng tập chunks, không thêm hoặc xóa chunk.
5. Tính lại hai metrics và giải thích kết quả.

| ID | Recall before | Recall after | Precision before | Precision after | Delta Precision |
|---|---:|---:|---:|---:|---:|
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| | | | | | |
| **Avg** | | | | | |

**Tại sao Recall dự kiến không đổi?**

> *Câu trả lời:*

**Khi nào reranking không đủ và cần sửa retriever/query/chunking?**

> *Câu trả lời:*

---

## Part 4 — Reflection (11:35–11:50)

Hoàn thành `reflection.md` bằng kết quả thật từ Exercise 3.2.

---

## Completion Checklist

Hoàn thành kiểm tra cuối trong khoảng 11:50–12:00.

- [ ] Tất cả required tests pass.
- [ ] `golden_dataset.json` validate thành công.
- [ ] Exercise 3.1 hoàn thành trong file JSON và bảng kết quả phía trên.
- [ ] Exercise 3.2 có năm metrics, aggregate report và ba cases thấp nhất.
- [ ] Exercise 3.3 có rubric 1–5 và bias controls.
- [ ] `reflection.md` có ba failure analyses và regression strategy.
- [ ] Đã copy `template.py` thành `solution/solution.py`.
- [ ] Exercise 3.4 và 3.5 chỉ làm nếu chọn bonus.
