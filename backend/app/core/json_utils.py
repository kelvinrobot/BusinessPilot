import json
import re
from typing import Any

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Best-effort JSON extraction from an LLM response that is supposed to be pure
    JSON but may be wrapped in a markdown code fence or have leading/trailing prose."""
    text = text.strip()

    fence_match = _FENCE_RE.search(text)
    candidate = fence_match.group(1) if fence_match else text

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    start_candidates = [i for i in (candidate.find("{"), candidate.find("[")) if i != -1]
    end_candidates = [i for i in (candidate.rfind("}"), candidate.rfind("]")) if i != -1]
    if start_candidates and end_candidates:
        start, end = min(start_candidates), max(end_candidates)
        return json.loads(candidate[start : end + 1])

    raise ValueError(f"Could not extract JSON from model output: {text[:200]!r}")
