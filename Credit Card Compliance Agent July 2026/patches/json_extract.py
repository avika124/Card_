"""
json_extract.py
===============
Replacement for the JSON extraction step in compliance_engine.py and
consistency_checker.py.

THE BUG
-------
Both modules extract Claude's response with:

    re.search(r'```(?:json)?\\s*(\\{.*?\\})\\s*```', response, re.DOTALL)

That pattern requires a markdown code fence. But both prompts end with
"Respond ONLY with valid JSON in this exact format:" — and a model told to
respond only with JSON returns bare JSON, no fence. The pattern finds nothing,
the parse raises, and the caller writes:

    "Error parsing Claude response. Raw response saved."

which is exactly what appears twice in section 4.1 of
compliance_report_20260415_151424.docx — in `regulatory_assessment` and
`assessment`. On that run the entire A1–J checklist produced nothing. The eight
findings in the report all came from consistency_checker; the compliance engine
silently contributed zero.

The failure is silent by construction: the string is written into the report as
though it were analysis text, so the report looks complete.

THE FIX
-------
Try, in order: bare JSON, fenced JSON, then brace-depth scanning that respects
strings and escapes. Raise a typed error the caller can distinguish from a
finding, so a parse failure surfaces as a failure rather than as prose.

    from json_extract import extract_json, JSONExtractionError

    try:
        result = extract_json(response_text)
    except JSONExtractionError as e:
        # do NOT write e into a report field — retry or fail loudly
        logger.error("Claude returned unparseable output: %s", e)
        raise
"""

import json
import re
from typing import Any, Optional


class JSONExtractionError(ValueError):
    """Claude's response could not be parsed as JSON."""

    def __init__(self, message: str, raw: str = ""):
        super().__init__(message)
        self.raw = raw
        self.preview = raw[:400]


_FENCE = re.compile(r"```(?:json|JSON)?\s*(.+?)\s*```", re.DOTALL)


def _scan_balanced(text: str, opener: str = "{", closer: str = "}") -> Optional[str]:
    """
    Return the first balanced {...} (or [...]) block, tracking string literals
    and escapes so braces inside quoted values don't throw off the depth count.

    This is what the original non-greedy `\\{.*?\\}` could not do: on nested
    JSON it stops at the first inner closing brace and yields invalid output.
    """
    start = text.find(opener)
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for i in range(start, len(text)):
        ch = text[i]

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    return None


def _repair_common(text: str) -> str:
    """
    Repair the two truncation artifacts that actually occur in practice:
    a trailing comma before a close, and an unterminated tail when the model
    hits max_tokens mid-array.
    """
    text = re.sub(r",\s*([}\]])", r"\1", text)          # trailing comma

    # Unbalanced close: append whatever is missing, in the right order.
    stack = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()

    if in_string:
        text += '"'
    for opener in reversed(stack):
        text += "}" if opener == "{" else "]"

    return text


def extract_json(response: str, *, allow_repair: bool = True) -> Any:
    """
    Parse JSON out of a model response.

    Strategy, in order:
      1. The whole response, trimmed — the common case when the prompt says
         "respond only with JSON". This is the path the original regex missed.
      2. Inside a markdown code fence.
      3. First balanced brace or bracket block, string-aware.
      4. Same, with light repair for truncation, if allow_repair.

    Raises JSONExtractionError with the raw text attached if all fail.
    """
    if not response or not response.strip():
        raise JSONExtractionError("Empty response from the API.", response or "")

    text = response.strip()

    # 1. bare JSON
    if text[0] in "{[":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # 2. fenced
    fence = _FENCE.search(text)
    if fence:
        inner = fence.group(1).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            text = inner  # fall through with the fence stripped

    # 3. balanced scan — object, then array
    for opener, closer in (("{", "}"), ("[", "]")):
        block = _scan_balanced(text, opener, closer)
        if block:
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                if allow_repair:
                    try:
                        return json.loads(_repair_common(block))
                    except json.JSONDecodeError:
                        pass

    # 4. repair the whole thing as a last resort
    if allow_repair:
        try:
            return json.loads(_repair_common(text))
        except json.JSONDecodeError:
            pass

    raise JSONExtractionError(
        "No parseable JSON found. The response may have been truncated by "
        "max_tokens, or the model returned prose instead of JSON.",
        response,
    )


def extract_json_or_none(response: str) -> Optional[Any]:
    """Non-raising variant for call sites that already branch on None."""
    try:
        return extract_json(response)
    except JSONExtractionError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cases = [
        ("bare JSON (the case that fails today)",
         '{"findings":[{"severity":"HIGH","excerpt":"gauranteed approval"}],"risk":"high"}'),
        ("fenced JSON",
         '```json\n{"findings":[{"a":1},{"b":2}]}\n```'),
        ("fenced, no language tag",
         '```\n{"findings":[]}\n```'),
        ("preamble then JSON",
         'Here is the analysis:\n\n{"findings":[{"nested":{"deep":true}}]}'),
        ("nested braces, unfenced — breaks the old non-greedy pattern",
         '{"a":{"b":{"c":[1,2,3]}},"d":"}"}'),
        ("brace inside a string value",
         '{"excerpt":"the rate is {variable}","severity":"LOW"}'),
        ("truncated at max_tokens",
         '{"findings":[{"severity":"HIGH","finding":"APR missing from headline"'),
        ("trailing comma",
         '{"findings":[{"a":1},],}'),
        ("top-level array",
         '[{"a":1},{"b":2}]'),
    ]

    old = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

    print(f"{'case':<52} {'old':<8} {'new'}")
    print("─" * 72)
    for label, payload in cases:
        m = old.search(payload)
        old_ok = False
        if m:
            try:
                json.loads(m.group(1))
                old_ok = True
            except json.JSONDecodeError:
                pass
        try:
            extract_json(payload)
            new_ok = True
        except JSONExtractionError:
            new_ok = False
        print(f"{label:<52} {'PASS' if old_ok else 'FAIL':<8} {'PASS' if new_ok else 'FAIL'}")
