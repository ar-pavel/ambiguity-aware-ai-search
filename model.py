"""Optional live interpreter: a language model reads the request and judges what is unclear.

To use it (otherwise the rule-based stand-in in interpret.py runs):
    cp .env.example .env    # then set A2_MODEL=claude + ANTHROPIC_API_KEY, or A2_MODEL=openai + OPENAI_API_KEY
Settings already in the shell environment take priority over .env. .env is ignored by git.
Privacy: live mode sends the typed request (only that text) to the chosen provider's API. Candidate data
never leaves this machine; the search runs locally.

Each provider has a small adapter (request body, HTTPS call, reading the reply). The system prompt,
the schema and everything after the reply are shared, so both providers are checked the same way.

The model only *judges*: which skills, place, seniority and availability the request names, which of
those are unclear, and whether one reading is clearly meant. Structured outputs force the reply into
SCHEMA. interpret.from_model() then checks the reply and builds the options in code. Any problem
(no key, network, refusal, truncated or bad reply) returns None, and the rules are used instead.
"""
import json
import os
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

# Claude (Anthropic Messages API)
API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2026-10-21"
FALLBACK_BETA = "server-side-fallback-2026-07-01"  # lets the API retry a declined request on another model
MODEL = "claude-opus-5-5"
EFFORT = "low"  # a short extraction task: low effort keeps it fast and cheap

# OpenAI (Chat Completions API). The model name depends on what your account offers.
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_DEFAULT_MODEL = "gpt-5-mini"

SYSTEM = """You read a recruiter's search request and report what it asks for.
Only use words the recruiter actually wrote. Never change their 'and' into OR.

Fill in the JSON:
- target: "jobs" if they asked for jobs, roles, vacancies, openings or positions; otherwise "candidates".
- company: the company named (e.g. "at Bluefin"), as written, or null. For candidates it is where they
  work now; for jobs it is the company hiring.
- status: for jobs only, "open" or "closed" if they said so, otherwise null.
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
  skills_op, seniority, location, availability, target. A company named without saying people or jobs
  ("Java developers at Bluefin") makes target ambiguous. dominant is true when one reading is clearly meant
  (e.g. they wrote 'with' or 'and' between skills). evidence quotes their words, like "you wrote 'senior'".
  A capitalised AND/OR, an explicit number of years, or "in <city>" is not ambiguous.
- unsupported: the parts of the request these fields cannot hold, quoted exactly as written, so the
  recruiter is told instead of the search quietly ignoring them. kind "name" for a person's name
  ("named Matin"), "place" for a place that is not a real city or country, "other" for anything else
  (salary, CV content, a greeting). Empty when everything fits the fields above."""

NULLABLE_STR = {"anyOf": [{"type": "string"}, {"type": "null"}]}
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["target", "company", "status", "skills", "skills_op", "location", "seniority",
                 "availability", "work_mode", "ambiguities", "unsupported"],
    "properties": {
        "target": {"type": "string", "enum": ["candidates", "jobs"]},
        "company": NULLABLE_STR,
        "status": {"anyOf": [{"type": "null"}, {"type": "string", "enum": ["open", "closed"]}]},
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
                                    "enum": ["skills_op", "seniority", "location", "availability", "target"]},
                           "dominant": {"type": "boolean"}, "evidence": {"type": "string"}}}},
        "unsupported": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["text", "kind"],
            "properties": {"text": {"type": "string"},
                           "kind": {"type": "string", "enum": ["name", "place", "other"]}}}},
    },
}


ENV_FILE = os.path.join(HERE, ".env")


def load_env(path=ENV_FILE):
    """Read KEY=VALUE lines from a local .env file into the environment (without overriding)."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                value = value.strip().strip('"').strip("'")
                if value:
                    os.environ.setdefault(key.strip(), value)


load_env()


def provider():
    """'claude', 'openai', or None (rule-based stand-in)."""
    choice = os.environ.get("A2_MODEL", "").strip().lower()
    return choice if choice in ("claude", "openai") else None


def live():
    """True when a live provider is configured (A2_MODEL and its key)."""
    return provider() is not None


def label():
    """Which model produced a live reading, for the page."""
    if provider() == "openai":
        return "OpenAI (%s)" % openai_model()
    return "Claude (%s)" % MODEL


def openai_model():
    """The OpenAI model to call: A2_OPENAI_MODEL if set, else the default."""
    return os.environ.get("A2_OPENAI_MODEL", "").strip() or OPENAI_DEFAULT_MODEL


def _https_json(url, body, headers, timeout=60):
    """POST JSON over HTTPS (standard library only) and return the JSON reply."""
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=dict(headers, **{"content-type": "application/json"}))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post(body):
    """Claude: send one Messages API request."""
    return _https_json(API_URL, body, {"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                                       "anthropic-version": API_VERSION, "anthropic-beta": FALLBACK_BETA})


def _post_openai(body):
    """OpenAI: send one Chat Completions request."""
    return _https_json(OPENAI_URL, body, {"authorization": "Bearer " + os.environ["OPENAI_API_KEY"]})


def judge(text, post=None):
    """Ask the chosen provider to judge the request. Returns a dict, or None if anything goes wrong."""
    try:
        if provider() == "openai":
            return _judge_openai(text, post or _post_openai)
        return _judge_claude(text, post or _post)
    except (KeyError, IndexError, StopIteration, TypeError, ValueError, OSError, urllib.error.URLError):
        return None  # no key, network or API error, or an unusable reply: fall back to the rules


def _judge_claude(text, post):
    reply = post({
        "model": MODEL,
        "max_tokens": 4000,
        "fallbacks": "default",
        "system": SYSTEM,
        "output_config": {"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        "messages": [{"role": "user", "content": text}],
    })
    if reply.get("stop_reason") in ("refusal", "max_tokens"):
        return None
    return json.loads(next(b["text"] for b in reply["content"] if b.get("type") == "text"))


def _judge_openai(text, post):
    reply = post({
        "model": openai_model(),
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "reading", "strict": True, "schema": SCHEMA}},
    })
    choice = reply["choices"][0]
    if choice.get("finish_reason") == "length" or choice["message"].get("refusal"):
        return None
    return json.loads(choice["message"]["content"])
