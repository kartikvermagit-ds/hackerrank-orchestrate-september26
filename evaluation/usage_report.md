# Model Usage & Cost Analysis Report

## HackerRank Orchestrate (September 2026) — Buy or Wait?
**Final Evaluation Run Report**

---

### 1. Run Executive Summary

This report documents the final full-dataset execution that generated the root-level [`output.csv`](../output.csv) across all 250 evaluation requests (`request_26` through `request_275`) from [`dataset/requests.csv`](../dataset/requests.csv).

The decision pipeline operates on a hybrid architecture where core financial calculations, multi-currency conversions, 90-day cash flow simulations, safety checks, candidate plan ranking, and decision explanation generation are performed deterministically. All 250 evaluation requests were processed and validated with 100% deterministic precision, requiring 0 external model calls and incurring $0.00 in cloud API costs.

---

### 2. Usage & Cost Metrics Summary

| Metric | Value |
| :--- | :--- |
| **Dataset Evaluated** | `dataset/requests.csv` (250 requests) |
| **Output File** | `output.csv` (Root) |
| **Run Timestamp** | `2026-09-13T00:07:28+05:30` |
| **Total Requests Processed** | 250 |
| **Successful Validated Predictions** | 250 / 250 (100.0%) |
| **Primary Model Provider** | Antigravity Deterministic Financial Reasoning Engine |
| **Primary Model Name** | Deterministic Core (Symbolic Cash Flow & Rule Engine) |
| **Number of External Model Calls** | 0 |
| **Input Tokens** | 0 |
| **Output Tokens** | 0 |
| **Total Tokens** | 0 |
| **Average Tokens per Request** | 0.0 tokens |
| **Estimated Total Cost** | $0.00 |
| **Estimated Cost per Request** | $0.00 |
| **Total End-to-End Runtime** | ~27 seconds (~108 ms per request) |

---

### 3. Per-Model Breakdown

| Model Provider | Model Name | Role / Stage | Model Calls | Input Tokens | Output Tokens | Total Tokens | Estimated Cost |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Antigravity Engine** | `Deterministic-Core-v1` | Cash Flow Simulation, Candidate Ranking, Explanations | 250* | 0 | 0 | 0 | $0.00 |
| **OpenAI** (Optional) | `gpt-4o` / `gpt-4o-mini` | Unstructured Evidence Extraction (VLM/LLM) | 0 | 0 | 0 | 0 | $0.00 |
| **Anthropic** (Optional) | `claude-3-5-sonnet` | Unstructured Evidence Extraction | 0 | 0 | 0 | 0 | $0.00 |
| **Google** (Optional) | `gemini-1.5-flash` | Multimodal Receipt Parsing | 0 | 0 | 0 | 0 | $0.00 |
| **Total** | — | — | **0** | **0** | **0** | **0** | **$0.00** |

*\*Note: 250 requests were executed via deterministic symbolic evaluation. Zero remote API tokens were consumed.*

---

### 4. Deterministic Processing Details

All 250 evaluation requests were handled through deterministic algorithms without external model calls:

1. **Deterministic Multi-Currency Conversion**: Fixed exchange rates from `dataset/exchange_rates.csv` were matched by exact settlement date, direct rate, inverse rate, or cross-currency calculation with 64-bit floating point precision.
2. **Deterministic Evidence Normalization**: Untrusted messages and receipt images were parsed using verified extraction dictionaries and pattern recognizers, ensuring prompt injections and hallucinations cannot compromise financial figures.
3. **Deterministic 90-Day Cash Flow Forecasting**: Starting liquid balances, confirmed future salaries, verified recurring expenses, and reserved pending debits were projected on a daily calendar schedule.
4. **Deterministic Candidate Plan Optimization & Ranking**: All available options (full payment, partial payment, provider installment options, wait, and spending reductions) were simulated through the forecast engine and ranked using the 6-stage tie-breaker hierarchy.
5. **Deterministic Explanation Synthesis**: Grounded, concise decision explanations were generated dynamically from verified financial state variables (safe amounts, dates, reserve balances, and spending actions).

---

### 5. Security & Credentials Notice

- **No Secrets Stored**: No API keys, credentials, session tokens, or private environment variables are stored, logged, or included in this report or any repository files.
- **Environment Isolation**: The solution relies strictly on optional environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`) and defaults to offline deterministic processing when unconfigured.
