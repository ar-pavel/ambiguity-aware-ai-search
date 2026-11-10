"""Optional live interpreter: Claude reads the request and judges what is unclear.

To use it (otherwise the rule-based stand-in in interpret.py runs):
    pip install anthropic             # optional; only live mode needs it
    export ANTHROPIC_API_KEY=...      # in your shell, never in a file
    export A2_MODEL=claude

The model only *judges*: which skills, place, seniority and availability the request names, which of
those are unclear, and whether one reading is clearly meant. Structured outputs force the reply into
SCHEMA. interpret.from_model() then checks the reply and builds the options in code. Any problem
(package missing, no key, network, refusal, bad reply) returns None, and the rules are used instead.
"""
import json
import os

MODEL = "claude-opus-5-5"
EFFORT = "low"  # a short extraction task: low effort keeps it fast and cheap

SYSTEM = """You read a recruiter's candidate-search request and report what it asks for.
Only use words the recruiter actually wrote. Never change their 'and' into OR.

Fill in the JSON:
- skills: each skill or technology named, as written (e.g. "Java", "k8s", "SAP MM").
- skills_op: "OR" if they wrote 'or', otherwise "AND".
- location: the city or country named, with scope "nearby" if they said near/around/within/commutable,
  "country" for a country, otherwise "city". null if none.
- seniority: null if not mentioned. {"kind":"years","min":N} if they gave a number of years.
  {"kind":"title","contains":"Senior"} if they said the title must contain the word.
  If they said "senior" or "lead" with no number, use {"kind":"years","min":5,"contains":"Senior" or "Lead"}.
- availability: "immediate" for now/immediately/available, "2w" for within two weeks, otherwise null.
- work_mode: "remote", "hybrid" or "onsite" if stated, otherwise null.
- ambiguities: one entry per part that could reasonably be read two ways. slot is one of
  skills_op, seniority, location, availability. dominant is true when one reading is clearly meant
  (e.g. they wrote 'with' or 'and' between skills). evidence quotes their words, like "you wrote 'senior'".
  A capitalised AND/OR, an explicit number of years, or "in <city>" is not ambiguous."""

NULLABLE_STR = {"anyOf": [{"type": "string"}, {"type": "null"}]}
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["skills", "skills_op", "location", "seniority", "availability", "work_mode", "ambiguities"],
    "properties": {
        "skills": {"type": "array", "items": {"type": "string"}},
        "skills_op": {"type": "string", "enum": ["AND", "OR"]},
        "location": {"anyOf": [{"type": "null"}, {
            "type": "object", "additionalProperties": False, "required": ["value", "scope"],
            "properties": {"value": {"type": "string"},
                           "scope": {"type": "string", "enum": ["city", "nearby", "country"]}}}]},
        "seniority": {"anyOf": [{"type": "null"}, {
            "type": "object", "additionalProperties": False, "required": ["kind", "min", "contains"],
            "properties": {"kind": {"type": "string", "enum": ["years", "title"]},
                           "min": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                           "contains": NULLABLE_STR}}]},
        "availability": {"anyOf": [{"type": "null"}, {"type": "string", "enum": ["immediate", "2w"]}]},
        "work_mode": {"anyOf": [{"type": "null"}, {"type": "string", "enum": ["remote", "hybrid", "onsite"]}]},
        "ambiguities": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["slot", "dominant", "evidence"],
            "properties": {"slot": {"type": "string",
                                    "enum": ["skills_op", "seniority", "location", "availability"]},
                           "dominant": {"type": "boolean"}, "evidence": {"type": "string"}}}},
    },
}


def live():
    """Live mode is on only when asked for. Missing package or key is handled at call time."""
    return os.environ.get("A2_MODEL") == "claude"


def judge(text, client=None):
    """Return the model's judgement as a dict, or None if anything goes wrong."""
    try:
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=4000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # if Claude declines, the API retries on its recommended fallback
            system=SYSTEM,
            output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": text}],
        )
        if response.stop_reason in ("refusal", "max_tokens"):
            return None
        reply = next(b.text for b in response.content if b.type == "text")
        return json.loads(reply)
    except Exception:  # no package, no key, network, API or JSON problems: fall back to the rules
        return None
