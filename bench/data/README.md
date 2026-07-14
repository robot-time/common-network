# Benchmark datasets

All subsets are drawn with a fixed seed (42) from public, well-known benchmarks
for reproducibility. Each item has `id`, `domain`, and `expected_specialist`
(the node that should handle it, per the v0.1 router).

| File | Source | Size | Scoring |
|---|---|---|---|
| `code_humaneval.jsonl` | [openai/human-eval](https://github.com/openai/human-eval), `HumanEval.jsonl` | 60 / 164 | unit-test execution (pass@1) |
| `math_gsm8k.jsonl` | [openai/grade-school-math](https://github.com/openai/grade-school-math), `test.jsonl` | 60 / 1319 | numeric exact match |
| `general_mmlu.jsonl` | [cais/mmlu](https://huggingface.co/datasets/cais/mmlu), `all/test` split | 70 across all 57 subjects | exact match (letter) |
| `legal_sa.jsonl` | **pending** — CGLA's 22 SA-law scenarios + the LegalBench subset already used internally | TBD | TBD, see `bench/scorers/legal_scorer.py` |

## Legal dataset — blocked

This is the domain the whole v0.2 claim leans on ("CGLA-Legal already beats
frontier models on its turf, 100% vs 31.8%"), so it must not be faked or
approximated. Waiting on:
1. The 22 SA-law scenarios CGLA was evaluated against.
2. The LegalBench subset already used.
3. CGLA's actual API (so `legal_scorer.py` can be written against its real
   output shape, not a guess).

Do not run the full benchmark's legal column, and do not report a legal
number, until this file is populated with real data.

## Regenerating

```bash
cd bench
.venv/bin/python3 -c "..."  # see git history for the exact fetch scripts used;
                             # re-run with the same seed (42) for identical subsets.
```
