"""GSM8K-style scoring: extract the final numeric answer and compare exactly."""
import re

NUMBER_RE = re.compile(r"-?\$?\d[\d,]*\.?\d*")


def _clean(num_str: str) -> str:
    return num_str.replace("$", "").replace(",", "").rstrip(".")


def extract_answer(model_output: str) -> str | None:
    text = model_output.strip()

    # Prefer an explicit "answer is X" / "#### X" style statement if present.
    explicit = re.search(r"(?:answer is|answer:|####)\s*\$?(-?\d[\d,]*\.?\d*)", text, re.IGNORECASE)
    if explicit:
        return _clean(explicit.group(1))

    # Otherwise fall back to the last number mentioned anywhere in the output.
    matches = NUMBER_RE.findall(text)
    if not matches:
        return None
    return _clean(matches[-1])


def score(item: dict, model_output: str) -> tuple[bool, str]:
    """item needs answer (string numeric). Returns (correct, extracted_answer)."""
    extracted = extract_answer(model_output)
    if extracted is None:
        return False, "(no number found)"

    try:
        correct = float(extracted) == float(item["answer"])
    except ValueError:
        correct = extracted == item["answer"]

    return correct, extracted
