---
name: add-scripted-request
description: Use when adding a new vague search request to the scripted test set, or when a request behaves unexpectedly and should be pinned by a test.
---

# Add a scripted request

## When this applies
The scripted requests are the fixed examples used for testing now and as evaluation material later.
Add one when a new kind of ambiguity is supported, or when a real phrasing gives a surprising mode.

## Steps
1. Run `python3 strategy.py "<the request>"` and read the mode, the reason and the comparisons.
2. Decide the mode the rule *should* choose, using the detection rules in the design:
   - capital AND/OR is stated; a lower-case 'and', 'with' or 'or' is dominant evidence;
   - 'senior' or 'lead' without a number is open between years and title;
   - only 'near', 'around' or 'within' make a location ambiguous.
3. If the output differs from what the rules say, the code is wrong, not the expectation. Open an issue.
4. Add the request and its expected mode to `EXPECTED` in `tests/test_strategy.py`, with a short
   comment saying why.
5. If the text is a follow-up command ("shortlist them for the Java role", "close these"), it belongs
   in `tests/test_commands.py` instead: add it to the commands or the searches that must stay searches.
6. If the request needs a candidate that does not exist yet, add one to `data/core_candidates.json`
   with a fake name, run `python3 data/generate.py`, and check the existing tests still pass.

## Check
`python3 run_tests.py` ends with `0 failures, 0 errors`, and the new request appears in the
`test_expected_mode_for_every_scripted_request` subtests.

## Do not
Do not change an expected mode just to make the test pass. That hides exactly the kind of silent
misreading this project is about.
