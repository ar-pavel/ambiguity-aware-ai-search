# Ask, Show, or Just Do It?

**Handling vague requests in an AI search assistant**

[![tests](https://github.com/ar-pavel/ambiguity-aware-ai-search/actions/workflows/tests.yml/badge.svg)](https://github.com/ar-pavel/ambiguity-aware-ai-search/actions/workflows/tests.yml)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)
![dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)

A recruiter types a request into a chat, such as *"senior Java developers"*. Requests like this are
often unclear: "senior" could mean years of experience or a job title. The assistant notices what is
unclear and chooses one of three responses, always with its reason:

- **Act:** search straight away, because nothing important is unclear.
- **Show:** search, and show how it read the request as editable chips.
- **Ask:** ask one question first, with the number of results each answer would give.

Changes to records (shortlisting candidates, closing jobs) are never guessed: each is listed and
confirmed first, and can be undone. Built as an MSc project at the University of Birmingham.

*README prose: about 930 words (code, commands, tables and headings not counted).*

```bash
python3 app.py    # Python 3.8+, nothing to install; open http://127.0.0.1:8770
```

![System diagram: reading a request on the top row, changing records on the bottom row; each part marked implemented, simulated or planned](docs/system.png)

### How it works

1. An **interpreter** turns the request into one structured **reading** (target, skills, place,
   seniority…) and lists the parts that are unclear.
2. For each unclear part, the **rule** compares the result lists the alternatives would give.
   - Nothing unclear: **act**.
   - One reading is clearly meant, or the lists overlap by at least θ = 0.5: **show**.
   - Otherwise: **ask** about the part whose lists differ most.
3. The model only *judges*. Code checks its reply and builds every option, count and message from the
   search that actually ran. **Why?** under each reply shows the rule's own numbers.

## Project status

Status words: **implemented** (works in the code), **simulated** (stands in for a real component),
**planned** (designed, not built).

| Part | Status |
|---|---|
| Chat page; only the latest reply is live, earlier turns are read-only | implemented |
| Search over 200 synthetic candidates and 30 jobs at 18 companies (skills AND/OR, place, seniority, notice, work mode, company, job status) | implemented |
| Act; show (editable chips, "(guessed)" marks, the count before each edit); ask (one question, a count per option, number keys) | implemented |
| The rule and its reason; **Why?**; study settings (force a strategy, move θ) | implemented |
| What the search cannot use (a name, an unknown place) is listed under *Ignored*; a request with nothing to search for never returns everyone | implemented |
| Shortlist and close: plan → confirmation → apply → undo, with a warning when candidates don't fit the job | implemented |
| Typed follow-ups ("shortlist them for the Java role"): a clear job opens the same confirmation, an unclear one is asked about | implemented |
| Event log for evaluation (`logs/events.jsonl`) | implemented |
| Interpreter, default: a rule-based *stand-in* for a language model | **simulated** |
| Interpreter, local model through Ollama (`qwen3:14b`), checked by code | implemented |
| Interpreter, Claude or OpenAI, same prompt, schema and checks (not yet run with a key) | implemented |
| Free-text "Other…" answers; a view of each job's shortlist; learning when to ask from corrections; semantic skill matching | planned |

## Technology stack

| Layer | Choice | Why |
|---|---|---|
| Server | Python 3.8+, standard library only (`http.server`) | runs anywhere with one command |
| Page | one HTML page, plain JavaScript and CSS | nothing to build |
| Data | synthetic candidates, jobs and companies (`data/`), fixed seed | no real personal data; repeatable |
| Interpreter | rule-based stand-in (default) | works with no key or network |
| Live models (optional) | Ollama (`qwen3:14b`, local); Claude (`claude-opus-5-5`); OpenAI (`gpt-5-mini`), all through `urllib` and one JSON schema | if one fails, the stand-in answers and the page says so |
| Quality | `unittest`; `ruff`; GitHub Actions on Python 3.8 and 3.13 | ruff runs in CI only |

**Undecided:** which live model, if any, the Phase 3 study uses. The stand-in gives every participant
the same readings; a live model is closer to a real product.

## Running or inspecting the work

```bash
python3 run_tests.py                                     # 174 tests; no key, network or install
python3 app.py                                           # http://127.0.0.1:8770 (--port 8771 if busy)
python3 -m assistant.strategy "senior Java developers"   # the rule's decision as JSON, no server
```

### Requests to try

With the stand-in interpreter, θ = 0.5 and no changes made yet:

| Request | Mode | What to look for |
|---|---|---|
| *Java developers in London* | act | 21 candidates; the "Read as" line; what was not searched |
| *Java with Python in London* | show | flip the AND ⇄ OR chip: 7 vs 43 |
| *senior Java developers* | ask | 5+ years (35) or 'Senior' in the title (12); press 1–3; open **Why?** |
| *Python and AWS people with Senior in the title* | show | the motivating request: AND kept, 7 (22 with OR) |
| *Java developers at Bluefin* | ask | people who work there (5) or its jobs (1) |
| *open jobs in London* | act | 10 jobs; **Close these jobs…** → **Close 10 jobs** → **Undo** |
| *Java developers in London*, then *shortlist them for the Senior Backend Engineer role* | — | the confirmation opens with that job chosen |
| *Java developers named Matin* · *hello* | act · — | "named Matin" listed under Ignored; nothing to search for |

### Live interpreter (optional)

```bash
cp .env.example .env    # set A2_MODEL=ollama (after `ollama pull qwen3:14b`), or claude / openai plus your own key
python3 tools/compare.py --with rules,ollama:qwen3:14b   # every scripted request through each interpreter
```

Keys go only in `.env`, which git ignores. A live model receives only the typed request and a fixed
instruction, never candidate data.

### Code map

[`app.py`](app.py) starts the server; the code is in [`assistant/`](assistant).

| File | Job |
|---|---|
| [`server.py`](assistant/server.py) | HTTP server and request handlers |
| [`interpret.py`](assistant/interpret.py) | the stand-in; the checks on a live model's reply |
| [`model.py`](assistant/model.py) | the call to Ollama, Claude or OpenAI |
| [`strategy.py`](assistant/strategy.py) | the act / show / ask rule (`THETA`) |
| [`search.py`](assistant/search.py) | filters and the "Read as" line |
| [`replies.py`](assistant/replies.py) | what the page shows: results, chips, question, Why? |
| [`commands.py`](assistant/commands.py) · [`actions.py`](assistant/actions.py) · [`store.py`](assistant/store.py) | typed follow-ups · plan, apply, undo · the only module that writes |
| [`log.py`](assistant/log.py) | event log |
| [`web/`](web) · [`data/`](data) · [`tests/`](tests) · [`tools/compare.py`](tools/compare.py) | the page · synthetic data · tests · interpreter comparison |

## Development record

The starting point: an assistant over a recruitment CRM silently widened a user's "and" to OR and
claimed a notes search it never ran. Each pull request records what changed, why, and how it was
checked. "Review" means a Claude Code pass with the
`review-change` checklist, followed by my own check in the browser.

1. **Search, reading and rule** ([#9](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/9), [#10](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/10), [#11](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/11))
   - Explicit filters rather than embeddings, so every result can be explained. The data is built so that "senior" is truly ambiguous.
   - A hand-set threshold rather than a learned policy, because which strategy works better is the open question.
2. **The page and the three modes** ([#13](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/13), [#14](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/14), [#19](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/19), [#20](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/20), [#21](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/21))
   - A security review found another web page could send requests to the server; it now answers only its own page.
   - A strategy switch and θ slider for the study conditions; one log line per turn.
3. **Live interpreters** ([#16](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/16), [#18](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/18))
   - Plain HTTPS instead of the SDK, which needs Python 3.10+ and an install.
   - Review found three ways a reply could mislead the page (a skill matched inside another word, an unknown place, a malformed reply). Each got a test, then a fix.
4. **Jobs, companies and confirmed changes** ([#29](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/29), [#30](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/30), [#32](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/32), [#33](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/33))
   - I widened the scope from reading to acting. Two reviews found nine issues, each fixed with a test.
   - The server's own search decides which records change, and a confirmation for a search that has since changed is refused. CI runs the tests on Python 3.8 and 3.13.
5. **Why? and the chat page** ([#34](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/34)–[#36](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/36), [#39](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/39), [#40](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/40), [#43](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/43), [#47](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/47), [#50](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/50))
   - Why? takes every number from the rule; a test checks 49.7% is never shown as 50%. Eight UX fixes, each tied to a course concept.
   - I chose a chat layout but kept the reading editable in the latest reply. Review found Why? crediting a setting for the recruiter's own edit; fixed and checked at 1440 and 390 px.
6. **Follow-ups and what cannot be searched** ([#46](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/46), [#48](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/48), [#52](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/52))
   - A typed follow-up is itself vague (which job?), so the same rule applies. Shortlisting people without the job's skills warns but never blocks.
   - "hello" returned all 200 candidates. My first fix, a word list, was rejected in review; the interpreter now reports what it cannot use.
7. **Structure and a local model** ([#54](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/54), [#56](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/56), [#58](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/58))
   - The code moved into the `assistant/` package with no behaviour change; `ruff` added to CI.
   - With Ollama, `qwen3:14b` gave the expected mode for 10 of 15 scripted requests, never fell back, about 4–5 s each ([table](docs/compare-qwen3-14b.md)). Four misses acted where show or ask was expected: the model under-reports what is unclear, which is why code, not the model, decides.
8. **Pre-submission review** ([#61](https://github.com/ar-pavel/ambiguity-aware-ai-search/issues/61))
   - The code checks did not cover the operator, so a live model could still turn "and" into OR. Code now keeps AND when the user wrote *and*, *with* or *&*; tested for each word. The comparison was re-run with the same result.

## AI assistance

- **Tool:** Claude Code (Claude Opus 5.5), for drafting code, tests and documents, and for reviews.
- **My part:** the research question, the design decisions and scope, and accepting, changing or
  rejecting each change. Every change went through a pull request, the review above, the tests and a
  check in the browser.
- **Examples:**
  - The first live interpreter used the Claude SDK; I replaced it with plain HTTPS so the project still needs nothing installed ([#16](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/16)).
  - The UX review and the assistant advised against a chat transcript ([#35](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/35)); I chose chat, keeping the reading editable ([#43](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/43)).
  - The assistant argued for a flat file layout ([#54](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/54)); I asked for a package ([#56](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/56)).
  - Review rejected my first fix for "hello" (a word list) as brittle ([#52](https://github.com/ar-pavel/ambiguity-aware-ai-search/pull/52)).

## Additional files

| Path | What it is |
|---|---|
| [`docs/system.png`](docs/system.png) (source [`system.dot`](docs/system.dot)) | the system diagram |
| [`docs/storyboards/`](docs/storyboards) | three storyboards: [show](docs/storyboards/storyboard-show.png), [ask](docs/storyboards/storyboard-ask.png), [a confirmed change](docs/storyboards/storyboard-write.png); five frames each from real screenshots; [`make_storyboards.py`](docs/storyboards/make_storyboards.py) rebuilds them |
| [`docs/compare-qwen3-14b.md`](docs/compare-qwen3-14b.md) | the stand-in and `qwen3:14b` on the 15 scripted requests |
| [`AGENTS.md`](AGENTS.md), [`skills/`](skills) | working rules and two task procedures for coding agents and people |
| [`.env.example`](.env.example) | live-interpreter and logging settings |
| [`.github/workflows/tests.yml`](.github/workflows/tests.yml), [`pyproject.toml`](pyproject.toml) | CI and ruff's rules |

Created locally and ignored by git: `state/state.json`, `logs/events.jsonl`, `.env`.
