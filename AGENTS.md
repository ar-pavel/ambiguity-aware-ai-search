# AGENTS.md

## Project overview
A small web prototype in Python 3.8+, standard library only. A recruiter types a vague search for
candidates or jobs in a chat. An interpreter turns it into one structured reading plus its ambiguities,
and a visible rule chooses to **act**, **show** the reading as editable chips, or **ask** one question.
Search is structured filtering over synthetic data; there is no vector store and no embeddings. Live
mode calls Claude or OpenAI over HTTPS, or a local model through Ollama, with `urllib`; otherwise a
rule-based stand-in reads the request (labelled *simulated*), and it is also the fallback whenever a
live model cannot be used.

## Build and test
```
python3 run_tests.py      # CI runs this on Python 3.8 and 3.13 for every push and pull request
ruff check .              # CI runs ruff 0.17.4 (rules in pyproject.toml); the app itself needs nothing installed
python3 app.py            # then open http://127.0.0.1:8770 (--port to change it, Ctrl+C to stop)
cp .env.example .env      # live mode: A2_MODEL=claude or openai (+ key), or ollama (a local model, no key)
python3 tools/compare.py --with rules,ollama:qwen3:14b   # the scripted requests through each interpreter
```

## Code map
`app.py` starts the server; the code is in the `assistant/` package. Files the app reads or writes
(`data/`, `web/`, `state/`, `logs/`, `.env`) stay at the project root.

| File | Job |
|---|---|
| `assistant/server.py` | HTTP server and the request handlers (`/api/search`, `plan`, `apply`, `undo`, `command`) |
| `assistant/replies.py` | what the page shows: table, chips, the one question, the sentence after an edit, Why? |
| `assistant/interpret.py` | rule-based stand-in, the checks on a live model's reply, and what cannot be searched |
| `assistant/model.py` | the live call: Claude, OpenAI, or a local model through Ollama |
| `assistant/strategy.py` | the act / show / ask rule and its reason (`python3 -m assistant.strategy "<request>"`) |
| `assistant/search.py` | filters, and the "Read as" line built from them |
| `assistant/commands.py` | typed follow-ups ("shortlist them for the Java role") |
| `assistant/actions.py` | plan, apply and undo a write; the skills-fit warning |
| `assistant/store.py` | the only module that writes (`state/state.json`) |
| `assistant/log.py` | one line per turn for evaluation (`logs/events.jsonl`) |
| `web/` | the chat page: `index.html`, `app.js`, `style.css` |
| `data/generate.py` | builds the synthetic data from a fixed seed |
| `tests/` | one test file per module, run by `run_tests.py` |
| `tools/compare.py` | runs the scripted requests through each interpreter and tabulates the outcomes |

## Conventions
- One interpretation object drives the chips, the question, the "Read as" line and the search.
- Every message on screen is built from what ran, never from model text. Why? never credits a setting
  for something the recruiter did.
- Status words are exactly: implemented, simulated, planned.
- Tuning numbers (such as the threshold θ) live in one named constant with a one-line reason.
- Reads follow act / show / ask. Every write (shortlist, close) goes plan -> confirm -> apply, can be
  undone, and is logged. Only `store.py` writes; `data/` is never changed.
- The skills-fit warning is advice: it never blocks a write and is not part of the fingerprint.
- What the search cannot use is never dropped silently. The interpreter lists it in `unsupported`
  (stand-in by heuristic, a live model through the schema; code keeps only words the user wrote), and
  the page shows it under Ignored. The reason shown comes from `interpret.WHY`, not model text. A
  request with nothing to search for is never a search of everyone.
- A typed follow-up only names the action and the job; it opens the same confirmation and never writes.
  When unsure whether text is a command, treat it as a new search.
- The page: only the latest search turn is live; earlier turns are read-only. A write replies with its
  result only and refreshes the live search in place. Server text is set with `textContent`.
- Python style: ruff's rules in `pyproject.toml`, lines up to 120 characters, a docstring on every
  public function saying what it returns and why it exists. Comments explain why, not what.
- Commits: conventional (`feat(scope):`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`), one logical
  change each, through a pull request whose body says `Closes #<issue>`.

## Never
- commit API keys, `.env` files, logs or `state/`
- write data without a confirmed plan (`actions.apply` refuses a fingerprint that no longer matches)
- use code, data, screenshots or branding from any real product
- add a runtime dependency; the standard library is the whole toolbox (ruff runs in CI only)
- label something "implemented" that is simulated or planned
- weaken a test to make a run pass

## Skills
Task-specific procedures live in `skills/<name>/SKILL.md`. Read one when its description matches the task:
`review-change` (before merging) and `add-scripted-request` (growing the test set).

## When you are unsure
- stop and ask, with the two possible readings written out
