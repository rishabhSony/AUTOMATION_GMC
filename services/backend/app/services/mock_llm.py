"""
Offline stand-in for the instructor/OpenAI client (USE_MOCK_AI, or no OPENAI_API_KEY in
development). It answers Pass 1 / Pass 2 deterministically, so the whole pipeline and UI
can be exercised without network access or API credits.

- If the RFQ is the bundled sample (`samples/rfq_apex.md`), it returns the pre-baked
  Pass 1 / Pass 2 JSON in `mock_data/` (the same answers the test fixtures use).
- Otherwise it scans the Markdown: a table row or "Label: value" line whose label matches
  a registry field (or procedure) becomes an extraction, with the line itself as verbatim
  evidence. Pass 2 marks every scanned field "supported" with Medium confidence.

The result still goes through `assemble_rows`, so grounding, defaults and validators apply
exactly as they do for the real model.
"""

import json
import re
from pathlib import Path
from types import SimpleNamespace

from app.services.field_registry import EXTRACT_FIELDS, PROCEDURES

MODEL_NAME = "mock-local"
_DATA = Path(__file__).parent / "mock_data"
_MARKER = re.compile(r"\[\[File:\s*(?P<file>[^|\]]+?)\s*\|\s*Page\s*(?P<page>[^\]]+?)\s*\]\]")
_KEY_VALUE = re.compile(r"^\s*(?:[-*]\s*)?\**(?P<label>[^:*|]{3,80}?)\**\s*:\s*(?P<value>.+)$")
_EMPTY = {"", "-", "–", "—", "na", "n/a", "nil", "none"}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9%]+", " ", text.lower()).strip()


def _aliases(name: str) -> set[str]:
    """'Coronary Artery Bypass Grafting (CABG)' → {full, 'coronary artery…', 'cabg'}."""
    base = re.sub(r"\s*\([^)]*\)", "", name)
    found = {_norm(name), _norm(base), *(_norm(p) for p in re.findall(r"\(([^)]*)\)", name))}
    found |= {_norm(part) for part in base.split("/") if len(part.strip()) > 3}
    return {a for a in found if a}


def _value(cell: str) -> str | None:
    cell = cell.strip()
    return None if cell.lower() in _EMPTY else cell


def _scan(markdown: str):
    """Yields (label, values, raw_line, file, page) for table rows and Label: value lines."""
    file = page = None
    for line in markdown.splitlines():
        if m := _MARKER.search(line):
            file, page = m["file"], m["page"]
            continue
        stripped = line.strip()
        if stripped.startswith("|") and not re.fullmatch(r"\|[\s:|-]+\|?", stripped):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2:
                yield cells[0], cells[1:], stripped, file, page
        elif m := _KEY_VALUE.match(line):
            yield m["label"], [m["value"].strip()], stripped, file, page


def _match(label: str, names: list[str]) -> str | None:
    key = _norm(label)
    if not key or key in {"benefit", "procedure", "field", "particulars"}:
        return None
    for name in names:
        if key in _aliases(name):
            return name
    return None


def heuristic_pass1(markdown: str) -> dict:
    field_names = [f.name for f in EXTRACT_FIELDS]
    fields: dict[str, dict] = {}
    sublimits: dict[str, dict] = {}
    for label, values, raw, file, page in _scan(markdown):
        if (proc := _match(label, PROCEDURES)) and proc not in sublimits:
            amount = next((v for v in values if _value(v) and re.search(r"\d", v)), None)
            if amount:
                sublimits[proc] = {"procedure_name": proc, "raw_amount_text": amount,
                                   "verbatim_evidence": raw, "source_file": file,
                                   "source_page": page}  # fmt: skip
            continue
        if (name := _match(label, field_names)) and name not in fields:
            current, proposed = (values + [None])[:2] if len(values) >= 2 else (None, values[0])
            current, proposed = _value(current or ""), _value(proposed or "")
            if current or proposed:
                fields[name] = {"field_name": name, "coverage_details": current,
                                "proposed_details": proposed, "verbatim_evidence": raw,
                                "source_file": file, "source_page": page}  # fmt: skip
    return {"fields": list(fields.values()), "sublimits": list(sublimits.values()),
            "unmapped_clauses": []}  # fmt: skip


def _baked() -> tuple[dict, dict]:
    return (
        json.loads((_DATA / "pass1_apex.json").read_text()),
        json.loads((_DATA / "pass2_apex.json").read_text()),
    )


def _is_baked_sample(pass1: dict, markdown: str) -> bool:
    """
    The sample RFQ: at least 80% of the baked evidence strings occur in the document. (The
    baked answers deliberately include one ungrounded citation, so grounding is exercised.)
    """
    flat = " ".join(markdown.split())
    evidence = [f["verbatim_evidence"] for f in pass1["fields"] if f.get("verbatim_evidence")]
    found = sum(" ".join(e.split()) in flat for e in evidence)
    return bool(evidence) and found >= 0.8 * len(evidence)


class _MockCompletions:
    def __init__(self):
        self._pass1: dict | None = None
        self._pass2: dict | None = None

    def create_with_completion(self, *, response_model, messages, **kwargs):
        markdown = messages[-1]["content"].split("RFQ DOCUMENT (Markdown)\n", 1)[-1]
        if self._pass1 is None:  # first call is Pass 1
            baked1, baked2 = _baked()
            if _is_baked_sample(baked1, markdown):
                self._pass1, self._pass2 = baked1, baked2
            else:
                self._pass1 = heuristic_pass1(markdown)
                self._pass2 = {"verdicts": [
                    {"field_name": f["field_name"], "verdict": "supported",
                     "confidence": "Medium",
                     "explanation": "Mock AI: value read from a matching labelled line"}
                    for f in self._pass1["fields"]
                ]}  # fmt: skip
            payload = self._pass1
        else:
            payload = self._pass2
        usage = SimpleNamespace(prompt_tokens=len(markdown) // 4, completion_tokens=0)
        return response_model.model_validate(payload), SimpleNamespace(usage=usage)


class MockLLMClient:
    """Duck-types `instructor.Instructor` for `extractor.run_pass1/run_pass2`."""

    model_name = MODEL_NAME

    def __init__(self):
        self.chat = SimpleNamespace(completions=_MockCompletions())
