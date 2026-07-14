"""SA-law scenario scoring.

TODO(blocked): CGLA's 22 SA-law scenarios + the LegalBench subset haven't been
provided yet (see bench/data/README.md). This is a best-effort placeholder --
exact/substring match against an `expected_outcome` field -- to be replaced
once the real dataset and CGLA's actual output shape are in hand. Do not treat
results from this scorer as final until it's been checked against real data.
"""


def score(item: dict, model_output: str) -> tuple[bool, str]:
    expected = str(item.get("expected_outcome", "")).strip().lower()
    output = model_output.strip().lower()
    if not expected:
        return False, "(item has no expected_outcome to score against)"
    correct = expected in output
    return correct, model_output.strip()[:200]
