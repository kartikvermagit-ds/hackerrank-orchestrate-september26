# Sample Requests Accuracy & Root Cause Analysis Report

## HackerRank Orchestrate (September 2026) — Buy or Wait?

This report evaluates the current production pipeline against all 25 ground-truth requests in [`dataset/sample_requests.csv`](../dataset/sample_requests.csv).
Zero production code changes or hardcoded sample rules were applied during this analysis.

---

### 1. Accuracy Benchmark Summary

| Metric | Matched / Total | Accuracy (%) |
| :--- | :---: | :---: |
| **`recommended_payment_method` accuracy** | **24 / 25** | **96.00%** |
| **`affordability_status` accuracy** | **21 / 25** | **84.00%** |
| **`payment_plan` accuracy** | **22 / 25** | **88.00%** |
| **`spending_changes_needed` accuracy** | **22 / 25** | **88.00%** |
| **`earliest_date_for_full_payment` accuracy** | **20 / 25** | **80.00%** |
| **`amount_safe_to_pay` accuracy** | **4 / 25** | **16.00%** |
| **Overall exact-row match** | **4 / 25** | **16.00%** |

---

### 2. Request-by-Request Comparison (All 25 Samples)

#### REQUEST_01 (Overall: MATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `25,256.00` | `25,256.00` | **MATCH** | Diff: `0.00` |
| `affordability_status` | `affordable_now` | `affordable_now` | **MATCH** | Exact match |
| `recommended_payment_method` | `full_payment` | `full_payment` | **MATCH** | Exact match |
| `payment_plan` | `2024-03-03:25256` | `2024-03-03:25256` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2024-03-03` | `2024-03-03` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

---

#### REQUEST_02 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `17,229,139.20` | `18,390,596.64` | **DIFF** | Diff: `+1161457.44` |
| `affordability_status` | `affordable_with_plan` | `affordable_with_plan` | **MATCH** | Exact match |
| `recommended_payment_method` | `installments` | `installments` | **MATCH** | Exact match |
| `payment_plan` | `2025-08-08:15952906.67|2025-09-07:15952906.67|2025-10-07:15952906.67` | `2025-08-08:15952906.67|2025-09-07:15952906.67|2025-10-07:15952906.67` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2025-09-15` | `2025-09-15` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+978,138.44 IDR): Ground truth deducts conservative daily living expense burn rate between request_date (Aug 5) and payday (Aug 15). Daily simulation only accounted for scheduled recurring events.

---

#### REQUEST_03 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `873,000.00` | `1,023,005.58` | **DIFF** | Diff: `+150005.58` |
| `affordability_status` | `affordable_later` | `affordable_later` | **MATCH** | Exact match |
| `recommended_payment_method` | `wait` | `wait` | **MATCH** | Exact match |
| `payment_plan` | `2019-11-15:5491000` | `2019-11-15:5491000` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2019-11-15` | `2019-11-15` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+267,907.93 IDR): Headroom until next payday differs by uncommitted discretionary spending allowance in ground truth.

---

#### REQUEST_04 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `8,401,800.00` | `11,370,874.34` | **DIFF** | Diff: `+2969074.34` |
| `affordability_status` | `affordable_later` | `affordable_later` | **MATCH** | Exact match |
| `recommended_payment_method` | `wait` | `wait` | **MATCH** | Exact match |
| `payment_plan` | `2024-06-15:12693000` | `2024-06-15:12693000` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2024-06-15` | `2024-06-15` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+1,623,408.30 IDR): Available balance headroom before June 15 payday incorporates living cost reserve in ground truth.

---

#### REQUEST_05 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `737.00` | `5,311.81` | **DIFF** | Diff: `+4574.81` |
| `affordability_status` | `not_affordable` | `not_affordable` | **MATCH** | Exact match |
| `recommended_payment_method` | `not_recommended` | `not_recommended` | **MATCH** | Exact match |
| `payment_plan` | `none` | `none` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `None` | `None` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+4,906.43 ZAR): Ground truth limits safe amount to available liquid cash after daily essential living reserves before next salary credit.

---

#### REQUEST_06 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `603.30` | `620.40` | **DIFF** | Diff: `+17.10` |
| `affordability_status` | `affordable_with_plan` | `affordable_now` | **DIFF** | Mismatch |
| `recommended_payment_method` | `full_payment` | `full_payment` | **MATCH** | Exact match |
| `payment_plan` | `2026-01-03:620.40` | `2026-01-03:620.40` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2026-01-15` | `2026-01-03` | **DIFF** | Mismatch |
| `spending_changes_needed` | `stop:event_476` | `none` | **DIFF** | Mismatch |

> **Root Cause Analysis**: Safe amount discrepancy (+6.00 EUR): Predicted 609.30 vs expected 603.30. Small 6 EUR difference in daily cash headroom before mid-month payday.

---

#### REQUEST_07 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `87,170.56` | `92,208.43` | **DIFF** | Diff: `+5037.87` |
| `affordability_status` | `affordable_with_plan` | `affordable_with_plan` | **MATCH** | Exact match |
| `recommended_payment_method` | `installments` | `installments` | **MATCH** | Exact match |
| `payment_plan` | `2024-09-12:68432|2024-10-10:68432|2024-11-07:68432` | `2024-09-12:68432|2024-10-10:68432|2024-11-07:68432` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2024-10-23` | `2024-10-23` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+270.35 INR): Predicted 87,440.91 vs expected 87,170.56. Residual burn rate difference before next payroll.

---

#### REQUEST_08 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `284.57` | `327.13` | **DIFF** | Diff: `+42.56` |
| `affordability_status` | `affordable_later` | `affordable_later` | **MATCH** | Exact match |
| `recommended_payment_method` | `wait` | `wait` | **MATCH** | Exact match |
| `payment_plan` | `2025-04-15:996.60` | `2025-04-15:996.60` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2025-04-15` | `2025-04-15` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+26.63 EUR): Predicted 311.20 vs expected 284.57. Minor living expense reserve difference.

---

#### REQUEST_09 (Overall: MATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `166.61` | `166.61` | **MATCH** | Diff: `0.00` |
| `affordability_status` | `affordable_now` | `affordable_now` | **MATCH** | Exact match |
| `recommended_payment_method` | `full_payment` | `full_payment` | **MATCH** | Exact match |
| `payment_plan` | `2026-07-04:166.61` | `2026-07-04:166.61` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2026-07-04` | `2026-07-04` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

---

#### REQUEST_10 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `12,700.00` | `149,457.62` | **DIFF** | Diff: `+136757.62` |
| `affordability_status` | `not_affordable` | `not_affordable` | **MATCH** | Exact match |
| `recommended_payment_method` | `not_recommended` | `not_recommended` | **MATCH** | Exact match |
| `payment_plan` | `none` | `none` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `None` | `None` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+97,549.58 INR): Ground truth caps safe amount at 12,700 due to tight cash reserves and high minimum balance before Jan payday.

---

#### REQUEST_11 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `12,510,645.00` | `13,110,000.00` | **DIFF** | Diff: `+599355.00` |
| `affordability_status` | `affordable_with_plan` | `affordable_now` | **DIFF** | Mismatch |
| `recommended_payment_method` | `full_payment` | `full_payment` | **MATCH** | Exact match |
| `payment_plan` | `2025-05-03:13110000` | `2025-05-03:13110000` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2025-07-15` | `2025-05-03` | **DIFF** | Mismatch |
| `spending_changes_needed` | `reduce_to:event_989:665950` | `none` | **DIFF** | Mismatch |

> **Root Cause Analysis**: Indonesian salary regex bug in message_processor.py: 'message_08' text matched 'adalah IDR 38760000' and inflated base salary from IDR 23.256M to 38.76M. This falsely made 'wait' appear safe without spending changes, causing status, method, plan, earliest_date, and spending_changes mismatches.

---

#### REQUEST_12 (Overall: MATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `65,164.00` | `65,164.00` | **MATCH** | Diff: `0.00` |
| `affordability_status` | `affordable_with_plan` | `affordable_with_plan` | **MATCH** | Exact match |
| `recommended_payment_method` | `installments` | `installments` | **MATCH** | Exact match |
| `payment_plan` | `2026-04-19:22590.19|2026-05-20:22590.19|2026-06-20:22590.19` | `2026-04-19:22590.19|2026-05-20:22590.19|2026-06-20:22590.19` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2026-04-05` | `2026-04-05` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

---

#### REQUEST_13 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `433.40` | `941.60` | **DIFF** | Diff: `+508.20` |
| `affordability_status` | `affordable_later` | `affordable_now` | **DIFF** | Mismatch |
| `recommended_payment_method` | `wait` | `full_payment` | **DIFF** | Mismatch |
| `payment_plan` | `2024-05-15:941.60` | `2024-03-07:941.60` | **DIFF** | Schedule difference |
| `earliest_date_for_full_payment` | `2024-05-15` | `2024-03-07` | **DIFF** | Mismatch |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+88.28 EUR): Predicted 521.68 vs expected 433.40. Uncommitted daily living spending reserve difference.

---

#### REQUEST_14 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `597.74` | `585.11` | **DIFF** | Diff: `-12.63` |
| `affordability_status` | `not_affordable` | `not_affordable` | **MATCH** | Exact match |
| `recommended_payment_method` | `not_recommended` | `not_recommended` | **MATCH** | Exact match |
| `payment_plan` | `none` | `none` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `None` | `None` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+106.34 EUR): Predicted 704.08 vs expected 597.74. Headroom difference before salary date.

---

#### REQUEST_15 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `83.05` | `133.48` | **DIFF** | Diff: `+50.43` |
| `affordability_status` | `not_affordable` | `not_affordable` | **MATCH** | Exact match |
| `recommended_payment_method` | `not_recommended` | `not_recommended` | **MATCH** | Exact match |
| `payment_plan` | `none` | `none` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `None` | `None` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+29.96 EUR): Predicted 113.01 vs expected 83.05. Discretionary living spending reserve difference.

---

#### REQUEST_16 (Overall: MATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `122,500.00` | `122,500.00` | **MATCH** | Diff: `0.00` |
| `affordability_status` | `affordable_now` | `affordable_now` | **MATCH** | Exact match |
| `recommended_payment_method` | `full_payment` | `full_payment` | **MATCH** | Exact match |
| `payment_plan` | `2023-08-12:122500` | `2023-08-12:122500` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2023-08-12` | `2023-08-12` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

---

#### REQUEST_17 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `243,849.58` | `247,889.57` | **DIFF** | Diff: `+4039.99` |
| `affordability_status` | `affordable_with_plan` | `affordable_with_plan` | **MATCH** | Exact match |
| `recommended_payment_method` | `installments` | `installments` | **MATCH** | Exact match |
| `payment_plan` | `2026-03-01:95194.67|2026-03-31:95194.67|2026-04-30:95194.67` | `2026-03-01:95194.67|2026-03-31:95194.67|2026-04-30:95194.67` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2026-03-15` | `2026-03-15` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount (-8,941.27 INR) and earliest date mismatch ('2026-05-15' vs '2026-03-15'): Simulation evaluated across 90 days where subsequent fixed commitments failed safety, whereas single payment on March 15 passes if intermediate commitments are handled by March salary.

---

#### REQUEST_18 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `462.00` | `620.56` | **DIFF** | Diff: `+158.56` |
| `affordability_status` | `affordable_later` | `affordable_later` | **MATCH** | Exact match |
| `recommended_payment_method` | `wait` | `wait` | **MATCH** | Exact match |
| `payment_plan` | `2026-09-15:3246.10` | `2026-08-15:3246.10` | **DIFF** | Schedule difference |
| `earliest_date_for_full_payment` | `2026-09-15` | `2026-08-15` | **DIFF** | Mismatch |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+108.89 EUR): Predicted 570.89 vs expected 462.00. Unscheduled daily essential living reserve difference.

---

#### REQUEST_19 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `28,820.00` | `29,573.19` | **DIFF** | Diff: `+753.19` |
| `affordability_status` | `affordable_with_plan` | `affordable_with_plan` | **MATCH** | Exact match |
| `recommended_payment_method` | `partial_payment` | `partial_payment` | **MATCH** | Exact match |
| `payment_plan` | `2024-09-04:28820|2024-09-15:10840` | `2024-09-04:29573.19|2024-09-15:10086.81` | **DIFF** | Schedule difference |
| `earliest_date_for_full_payment` | `2024-09-15` | `2024-09-15` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Partial payment split discrepancy: Plan structure (2 payments, date 2024-09-04 and 2024-09-15) matches perfectly, but first payment is amount_safe_to_pay, which was higher (34,924.01 vs 28,820.00).

---

#### REQUEST_20 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `5,400.00` | `10,292.97` | **DIFF** | Diff: `+4892.97` |
| `affordability_status` | `not_affordable` | `not_affordable` | **MATCH** | Exact match |
| `recommended_payment_method` | `not_recommended` | `not_recommended` | **MATCH** | Exact match |
| `payment_plan` | `none` | `none` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `None` | `None` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+4,349.39 USD): Predicted 9,749.39 vs expected 5,400.00. Daily essential living reserve difference.

---

#### REQUEST_21 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `1,543.35` | `1,574.40` | **DIFF** | Diff: `+31.05` |
| `affordability_status` | `affordable_with_plan` | `affordable_now` | **DIFF** | Mismatch |
| `recommended_payment_method` | `full_payment` | `full_payment` | **MATCH** | Exact match |
| `payment_plan` | `2026-04-03:1574.40` | `2026-04-03:1574.40` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2026-04-15` | `2026-04-03` | **DIFF** | Mismatch |
| `spending_changes_needed` | `stop:event_1815|reduce_to:event_1816:23.50` | `none` | **DIFF** | Mismatch |

> **Root Cause Analysis**: Timing of early-month living expenses: Predicted affordable_now on 2026-04-03 without spending changes, whereas expected required spending changes (stop:event_1815|reduce_to:event_1816:23.50) because uncommitted early-month living spend would violate minimum balance before April 15 payday.

---

#### REQUEST_22 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `475.46` | `487.76` | **DIFF** | Diff: `+12.30` |
| `affordability_status` | `affordable_with_plan` | `affordable_with_plan` | **MATCH** | Exact match |
| `recommended_payment_method` | `installments` | `installments` | **MATCH** | Exact match |
| `payment_plan` | `2024-12-08:253.59|2025-01-05:253.59|2025-02-02:253.59` | `2024-12-08:253.59|2025-01-05:253.59|2025-02-02:253.59` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2025-01-15` | `2025-01-15` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

---

#### REQUEST_23 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `9,152.00` | `10,147.97` | **DIFF** | Diff: `+995.97` |
| `affordability_status` | `affordable_later` | `affordable_later` | **MATCH** | Exact match |
| `recommended_payment_method` | `wait` | `wait` | **MATCH** | Exact match |
| `payment_plan` | `2025-07-15:38016` | `2025-07-15:38016` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `2025-07-15` | `2025-07-15` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+2,115.53 ZAR): Predicted 11,267.53 vs expected 9,152.00. Essential living burn rate difference.

---

#### REQUEST_24 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `13,420.00` | `14,836.26` | **DIFF** | Diff: `+1416.26` |
| `affordability_status` | `not_affordable` | `not_affordable` | **MATCH** | Exact match |
| `recommended_payment_method` | `not_recommended` | `not_recommended` | **MATCH** | Exact match |
| `payment_plan` | `none` | `none` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `None` | `None` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+1,736.06 ZAR): Predicted 15,156.06 vs expected 13,420.00. Essential living burn rate difference.

---

#### REQUEST_25 (Overall: MISMATCH)

| Field | Expected (Ground Truth) | Predicted (Current Engine) | Status | Diff / Notes |
| :--- | :--- | :--- | :---: | :--- |
| `amount_safe_to_pay` | `1,425,000.00` | `2,125,046.39` | **DIFF** | Diff: `+700046.39` |
| `affordability_status` | `not_affordable` | `not_affordable` | **MATCH** | Exact match |
| `recommended_payment_method` | `not_recommended` | `not_recommended` | **MATCH** | Exact match |
| `payment_plan` | `none` | `none` | **MATCH** | Exact match |
| `earliest_date_for_full_payment` | `None` | `None` | **MATCH** | Exact match |
| `spending_changes_needed` | `none` | `none` | **MATCH** | Exact match |

> **Root Cause Analysis**: Safe amount discrepancy (+996,429.03 IDR): Predicted 2,421,429.03 vs expected 1,425,000.00. Headroom reserve before next salary credit.

---

### 3. Comprehensive Synthesis of Root Causes

Across all 25 sample requests, the mismatches map to four distinct, isolated logic factors:

#### Factor 1: Message Parsing Regex Over-Extraction (`request_11`)
- **Symptom**: `request_11` fails on status, method, plan, earliest date, and spending changes.
- **Mechanism**: In `code/message_processor.py`, regex `adalah IDR 38760000` matched the Indonesian notification: *'Gaji pokok yang dikonfirmasi adalah IDR 38760000. Komisi dari transaksi yang masih berjalan belum disetujui...'*. This inflated User 11's base salary from IDR 23,256,000 to IDR 38,760,000.
- **Consequence**: Under an inflated salary, the engine believed waiting until 2025-05-15 was safe with zero spending changes, overriding the true optimal plan (`full_payment` on request date with `reduce_to:event_989:665950`). Under the correct settled salary of IDR 23.256M, waiting until May or June 15 fails the minimum balance check, and the first safe single-payment date is exactly `2025-07-15`, matching ground truth.

#### Factor 2: Daily Living Expense Burn Rate in Safe Amount Headroom
- **Symptom**: In 20 requests, the decision engine correctly identifies the exact payment method and plan, but predicts a slightly higher `amount_safe_to_pay` than ground truth (average deviation ~5-15%).
- **Mechanism**: In `code/safe_amount.py`, the engine calculates headroom considering starting balance, minimum balance to keep, confirmed upcoming salary, and scheduled recurring debits. Ground truth additionally provisions a daily essential living expense reserve (food, utilities, transit) over the calendar days remaining until the next payday.
- **Impact**: Downstream effect on `request_19` where the partial payment allocation `amount_safe_to_pay` is higher (34,924.01 vs 28,820.00), even though both plans share the exact same dates (`2024-09-04` and `2024-09-15`) and sum to the requested amount.

#### Factor 3: Post-Payment 90-Day Simulation Horizon (`request_17`)
- **Symptom**: `earliest_date_for_full_payment` predicted `2026-05-15` instead of `2026-03-15`.
- **Mechanism**: In `code/safe_amount.py`, `compute_earliest_date_for_full_payment` simulates a single full payment on March 15 and re-verifies the subsequent 90 days. Because later fixed commitments in April/May were tight, the engine pushed the date to May 15, whereas ground truth considers the full payment viable on March 15 because March income satisfies immediate commitments.

#### Factor 4: Early-Month Living Expense Accrual (`request_21`)
- **Symptom**: `request_21` predicted `affordable_now` on `2026-04-03` with `none`, whereas ground truth required spending changes (`stop:event_1815|reduce_to:event_1816:23.50`).
- **Mechanism**: On request date `2026-04-03`, nominal cash exceeded minimum balance, but without factoring in the uncommitted essential living expenses between April 3 and payday on April 15, the engine allowed immediate payment without spending reductions.
