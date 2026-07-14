"""MMLU-style scoring: extract the chosen letter (A-D) and compare exactly."""
import re

LETTER_RE = re.compile(r"\b([ABCD])\b")


def extract_letter(model_output: str) -> str | None:
    text = model_output.strip()

    # Prefer an explicit "answer is X" / "answer: X" statement.
    explicit = re.search(r"answer(?:\s*is|:)?\s*\(?([ABCD])\)?", text, re.IGNORECASE)
    if explicit:
        return explicit.group(1).upper()

    # A bare single letter response.
    if len(text) <= 3:
        bare = re.match(r"^\(?([ABCD])\)?\.?$", text, re.IGNORECASE)
        if bare:
            return bare.group(1).upper()

    # Fall back to the first standalone A/B/C/D token anywhere in the output.
    match = LETTER_RE.search(text)
    return match.group(1).upper() if match else None


def score(item: dict, model_output: str) -> tuple[bool, str]:
    """item needs answer (letter A-D). Returns (correct, extracted_letter)."""
    extracted = extract_letter(model_output)
    if extracted is None:
        return False, "(no letter found)"
    return extracted == item["answer"], extracted
