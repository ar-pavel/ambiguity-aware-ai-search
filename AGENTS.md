# AGENTS.md

## Project overview
A small web prototype in Python 3 (standard library only, 3.8+; the `anthropic` package is an optional extra for live mode). A recruiter types a vague
candidate search. An interpreter turns it into one structured reading plus its ambiguities, and a
visible rule chooses to **act**, **show** the reading as editable chips, or **ask** one question.
Search is structured filtering over synthetic data; there is no vector store and no embeddings.

## Build and test
python3 run_tests.py
python3 app.py            # then open http://127.0.0.1:8770
cp .env.example .env      # live mode: set A2_MODEL=claude and your key; needs `pip install anthropic`

## Conventions
- one interpretation object drives the chips, the question, the "Read as" line and the search
- the "Read as" line is built from the filters that ran, never from model text
- status words are exactly: implemented, simulated, planned
- tuning numbers (such as the threshold θ) live in one named constant with a one-line reason

## Never
- commit API keys, `.env` files or logs
- use code, data, screenshots or branding from any real product
- add a required dependency; only live mode may use the optional `anthropic` package, and the app must run without it
- label something "implemented" that is simulated or planned
- weaken a test to make a run pass

## Skills
Task-specific procedures live in `skills/<name>/SKILL.md`. Read one when its description matches the task:
`review-change` (before merging) and `add-scripted-request` (growing the test set).

## When you are unsure
- stop and ask, with the two possible readings written out
