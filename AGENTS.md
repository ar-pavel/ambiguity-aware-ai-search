# AGENTS.md

## Project overview
A small web prototype in Python 3 (standard library only, 3.8+). Live mode calls the Claude or OpenAI API over HTTPS with `urllib`. A recruiter types a vague
search for candidates or jobs. An interpreter turns it into one structured reading plus its ambiguities, and a
visible rule chooses to **act**, **show** the reading as editable chips, or **ask** one question.
Search is structured filtering over synthetic data; there is no vector store and no embeddings.

## Build and test
python3 run_tests.py      # CI runs this on Python 3.8 and 3.13 for every push and pull request
python3 app.py            # then open http://127.0.0.1:8770
cp .env.example .env      # live mode: set A2_MODEL=claude or openai, and that provider's key

## Conventions
- one interpretation object drives the chips, the question, the "Read as" line and the search
- the "Read as" line is built from the filters that ran, never from model text
- status words are exactly: implemented, simulated, planned
- tuning numbers (such as the threshold θ) live in one named constant with a one-line reason
- reads follow act / show / ask; every write (shortlist, close) goes plan -> confirm -> apply, can be
  undone, and is logged. Only `store.py` writes, to `state/state.json`; `data/` is never changed

## Never
- commit API keys, `.env` files, logs or `state/`
- write data without a confirmed plan (`actions.apply` refuses a fingerprint that no longer matches)
- use code, data, screenshots or branding from any real product
- add a dependency; the standard library is the whole toolbox
- label something "implemented" that is simulated or planned
- weaken a test to make a run pass

## Skills
Task-specific procedures live in `skills/<name>/SKILL.md`. Read one when its description matches the task:
`review-change` (before merging) and `add-scripted-request` (growing the test set).

## When you are unsure
- stop and ask, with the two possible readings written out
