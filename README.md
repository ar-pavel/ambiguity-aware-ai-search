# Ask, Show, or Just Do It?

*Handling vague requests in an AI search assistant*

[![tests](https://github.com/ar-pavel/ambiguity-aware-ai-search/actions/workflows/tests.yml/badge.svg)](https://github.com/ar-pavel/ambiguity-aware-ai-search/actions/workflows/tests.yml)

A recruiter types a vague request into a chat, such as *"senior Java developers"*. The assistant notices
what is unclear and decides whether to **act** (just search), **show** how it read the request as
editable chips (small labelled controls), or **ask** one question, and it always says why. Changes to records are never guessed:
each one is confirmed first and can be undone. Built as an MSc project at the University of Birmingham.

*README prose: about 1,255 words (code, commands, tables and headings not counted).*

```bash
python3 app.py          # needs Python 3.8+, nothing to install; open http://127.0.0.1:8770
```

![System diagram: the read path on top, changes to records below; each part marked implemented, simulated or planned](docs/system.png)

**How it works.** An *interpreter* turns the request into one structured *reading* (target, skills,
place, seniority…) plus the parts that are unclear. For each unclear part, the rule compares the two
shortlists it could give. Nothing unclear: **act**. One reading is clearly meant (you wrote "with"), or
the lists share at least half their records (threshold θ = 0.5): **show**. Otherwise: **ask** about the
part whose lists differ most. The model only *judges*; code checks its reply and builds every option,
count and message from the search that ran. **Why?** under each reply shows the rule's own numbers.

## Project status

| Part | Status |
|---|---|
| Chat page: only the latest reply is live (chips, question, buttons); earlier turns are read-only | implemented |
| Search over 200 synthetic candidates and 30 jobs at 18 companies (skills AND/OR, place, seniority, notice, work mode, company, job status) | implemented |
| Act; show (editable chips, "(guessed)" marks, the count before each edit); ask (one question, a real count per option, number keys answer) | implemented |
| The rule and its reason; **Why?**; study settings (force a strategy, move θ) | implemented |
| What the search cannot use (a name, an unknown place) is listed under *Ignored*; a request with nothing to search for never returns everyone | implemented |
| Shortlist and close: plan → confirmation → apply → undo, with a warning when candidates don't fit the job | implemented |
| Typed follow-ups ("shortlist them for the Java role"): a clear job opens the confirmation, an unclear one is asked about | implemented |
| Event log for evaluation (`logs/events.jsonl`) | implemented |
| Interpreter, default: a rule-based *stand-in* for a language model | **simulated** |
| Interpreter, local model through Ollama (`qwen3:14b`), checked by code | implemented |
| Interpreter, Claude or OpenAI, same prompt, schema and checks | implemented (not yet run with a real key) |
| Free-text "Other…" answers; a view of each job's shortlist; learning when to ask from corrections; semantic skill matching | planned |

## Technology stack

- **Python 3.8+, standard library only.** `http.server` serves the page; nothing to install.
- **One HTML page**, plain JavaScript and CSS.
- **Synthetic data** in `data/`, built from a fixed seed.
- **Optional live interpreters**, called with `urllib`, each made to return the same JSON schema:
  a local model through **Ollama** (default `qwen3:14b`; no key, nothing leaves the machine);
  **Claude** (`claude-opus-5-5`); **OpenAI** (default `gpt-5-mini`). If one can't be used, the
  stand-in reads the request and the page says so.
- **CI:** GitHub Actions runs the tests on Python 3.8 and 3.13, and `ruff` (CI only).

## Running or inspecting the work

```bash
python3 run_tests.py                                  # 172 tests; no key, network or install needed
python3 app.py                                        # http://127.0.0.1:8770; --port 8771 if busy; Ctrl+C stops
python3 -m assistant.strategy "senior Java developers"  # the rule's decision as JSON, no server
```

Requests to try (stand-in interpreter, θ = 0.5, nothing changed yet):

| Request | Mode | What to look for |
|---|---|---|
| *Java developers in London* | act | 21 candidates; the "Read as" line; what was not searched |
| *Java with Python in London* | show | flip the AND ⇄ OR chip: 7 vs 43 |
| *senior Java developers* | ask | 5+ years (35) or 'Senior' in the title (12); press 1–3; open **Why?** |
| *Python and AWS people with Senior in the title* | show | the motivating request: AND kept, 7 (22 with OR) |
| *Java developers at Bluefin* | ask | people who work there (5) or its jobs (1) |
| *open jobs in London* | act | 10 jobs; **Close these jobs…** → **Close 10 jobs** → **Undo** |
| *Java developers in London*, then type *shortlist them for the Senior Backend Engineer role* | — | the confirmation opens with that job chosen |
| *Java developers named Matin* · *hello* | act · — | "named Matin" listed under Ignored; nothing to search for |

**Live interpreter (optional):**
```bash
cp .env.example .env     # A2_MODEL=ollama (after `ollama pull qwen3:14b`), or claude / openai with a key
python3 tools/compare.py --with rules,ollama:qwen3:14b   # every scripted request through each interpreter
```

**Safety:**
- Keys go only in `.env`, which git ignores. A live model receives only the typed request and a fixed
  instruction, never candidate data.

**Code map:** `app.py` starts the server; the code is in `assistant/`.

| File | Job |
|---|---|
| `assistant/server.py` | HTTP server and request handlers |
| `assistant/replies.py` | what the page shows: table, chips, question, Why? |
| `assistant/interpret.py` | the stand-in; checks on a live model's reply; what cannot be searched |
| `assistant/model.py` | the call to Ollama, Claude or OpenAI |
| `assistant/strategy.py` | the act / show / ask rule (`THETA`) |
| `assistant/search.py` | filters and the "Read as" line |
| `assistant/commands.py` | typed follow-ups |
| `assistant/actions.py` | plan, apply and undo; the fit warning |
| `assistant/store.py` | the only module that writes |
| `assistant/log.py` | event log |
| `web/` · `data/` · `tests/` · `tools/compare.py` | the page · synthetic data · tests · interpreter comparison |

## Development record

The motivating failure: an assistant over a recruitment CRM silently widened a user's "and" to OR and
claimed a notes search it never ran. Each pull request records what changed, why, and how it was
checked. "Review" below means a Claude Code pass with the `review-change` checklist, then my own check
in the browser.

1. **Search, reading and rule** ([#9](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/9), [#10](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/10), [#11](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/11))
   - Explicit filters, not embeddings, so every result can be explained. Data built so 'senior' is ambiguous (Senior titles with few years, and the reverse).
   - A rule-based stand-in instead of recorded replies, so any request with known skills and places works. A test pins that "and" is never widened to OR.
   - A hand-set threshold, not a learned policy, because which strategy works better is the open question.
2. **The page and three modes** ([#13](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/13), [#14](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/14), [#19](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/19))
   - A security review found another web page could send requests to the server; it now answers only its own page.
   - Review found the question could quote the model's wording; it is now built from the reading.
3. **Live interpreters** ([#16](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/16), [#18](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/18))
   - Plain HTTPS instead of the SDK, which needs Python 3.10+ and an install.
   - Review found three ways a reply could mislead the page: a skill matched inside another word, an unknown place matching nobody, a malformed reply crashing. Each got a test, then a fix. Faked replies test that every failure falls back to the stand-in.
4. **Controls and log** ([#20](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/20), [#21](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/21)): a strategy switch and θ slider for the study conditions; one log line per turn, tested to write nothing when `A2_LOG=off`.
5. **Jobs and companies** ([#29](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/29), [#30](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/30))
   - I widened the scope to the records a recruiter works with; every expected mode stayed the same. Two reviews found nine issues, such as availability dropped without a word when switching to jobs; each fixed with a test.
6. **CI** ([#32](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/32)): the tests run on every push on Python 3.8, the stated minimum, and 3.13, with no keys or network.
7. **Changes that always confirm** ([#33](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/33))
   - The server's own search decides the records, and a confirmation for a search that has since changed is refused. Tests: no write without the confirmed plan; undo restores the exact state.
8. **Why? and a UX review** ([#34](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/34), [#35](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/35), [#36](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/36), [#39](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/39), [#40](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/40))
   - Why? takes every number from the rule; a test checks 49.7% is never shown as 50%.
   - Eight UX fixes, each tied to a course concept (e.g. signifiers such as AND ⇄ OR for the gulf of execution). #36 re-landed #34–#35, merged into the wrong base.
   - Review found focus leaving the θ slider and a confirmation opening after Esc; both fixed.
9. **A chat page** ([#43](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/43), [#47](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/47), [#50](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/50))
   - I chose a chat layout, but kept the reading visible and editable in the latest reply; earlier turns are frozen, so a click never applies to an old request.
   - Review found **Why?** saying "the strategy setting chose show" after the recruiter's own edit, which was false; Why? now never credits a setting for the user's choice. Checked in the browser at 1440 and 390 px.
   - Number keys answer the question. At my request (#50), a change's reply states only its result, not the whole search again.
10. **Follow-ups and advice** ([#46](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/46), [#48](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/48))
    - A typed follow-up is itself vague (which job?), so the same rule applies; text that is not clearly a command stays a search. 21 tests, including "close to London".
    - Shortlisting people without the job's skills now warns, but never blocks.
11. **What the search cannot use** ([#52](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/52))
    - "hello" returned all 200 candidates. My first fix, a word list, was rejected in review: it refused "show me all" and still dropped "in Narnia" silently. The interpreter now reports what it cannot use; code keeps only words the user wrote.
12. **Structure** ([#54](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/54), [#56](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/56)): `ruff` in CI and the code moved into the `assistant/` package, with no behaviour change and file history kept; all tests and ruff pass.
13. **A local model** ([#58](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/58))
    - Ollama lets the live path run with no key or cost. `tools/compare.py` runs 15 scripted requests through each interpreter.
    - One run (temperature 0): `qwen3:14b` gave the expected mode for 10 of 15, never fell back, about 4 s per request. Of the five misses, four acted where show or ask was expected and one asked where show was expected: the model under-reports what is unclear, which is why code, not the model, decides.
    - It also exposed a bug (a correct "Bluefin" dropped by the company check), fixed with a test.

## AI assistance

- **Tool:** Claude Code (Claude Opus 5.5), for drafting code, tests and documents, and for reviews.
- **My part:** the research question, the design decisions and scope, and accepting, changing or
  rejecting each change. Every feature went through a pull request and the review above
  ([#12](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/12)), the tests and a browser check.
- **Examples:**
  - The first live interpreter used the Claude SDK; I replaced it with plain HTTPS so the project still needs nothing installed ([#16](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/16)).
  - The UX review and the assistant advised against a chat transcript ([#35](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/35)); I chose chat, keeping the reading editable ([#43](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/43)).
  - The assistant argued for keeping a flat file layout ([#54](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/54)); I asked for a package, done in [#56](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/56).
  - Review rejected my first fix for "hello" (a word list) as brittle; the interpreter now reports what it cannot use ([#52](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/52)).

## Additional files

- `AGENTS.md`: working rules for coding agents and people. `skills/`: two task procedures.
- `.env.example`: live-interpreter and logging settings. `.github/workflows/tests.yml`: CI. `pyproject.toml`: ruff's rules.
- `docs/system.png` (source `docs/system.dot`): the system diagram.
- `docs/storyboards/`: `storyboard-show.png`, `storyboard-ask.png`, `storyboard-write.png`, five frames each
  from real screenshots; `make_storyboards.py` rebuilds the pages.
- Created locally, ignored by git: `state/state.json`, `logs/events.jsonl`, `.env`.
