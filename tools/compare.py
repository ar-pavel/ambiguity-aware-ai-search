"""Run the scripted requests through each interpreter and compare what the page would do.

    python3 tools/compare.py                                   # the rule-based stand-in only
    python3 tools/compare.py --with rules,ollama:qwen3:14b,ollama:gpt-oss:20b
    python3 tools/compare.py --with rules,claude --out logs/compare.md

Interpreters: "rules" (the stand-in), "ollama:<model>" (needs Ollama running and the model pulled),
"claude" or "openai" (need their key in .env). Each request goes through the whole pipeline, as from
the page: interpreter -> code checks -> the act / show / ask rule -> the reply. For each it records
the outcome, whether it matches the expected one, what the code checks dropped or flagged, whether
the model failed and the stand-in was used instead, and the time taken. Nothing is written to the
recruiter's state or event log.
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["A2_LOG"] = "off"

from assistant import server  # noqa: E402
from tests.test_strategy import EXPECTED  # noqa: E402  (the scripted requests the rule is tested on)

# Beyond the scripted search requests: jobs, companies, and requests the search cannot fully use.
# "nothing" means the reply says there is nothing it can search for, instead of searching everyone.
EXTRA = {
    "open jobs in London": "act",
    "Java developers at Bluefin": "ask",            # people at Bluefin, or Bluefin's jobs?
    "hello": "nothing",
    "candidates named Matin": "nothing",             # searching by name is not supported
    "Java developers near Narnia": "act",            # Narnia should be listed under Ignored
}
REQUESTS = dict(EXPECTED, **EXTRA)


def use(interpreter):
    """Point the app at one interpreter by setting the same variables .env would."""
    for key in ("A2_MODEL", "A2_OLLAMA_MODEL"):
        os.environ.pop(key, None)
    if interpreter == "rules":
        return
    if interpreter.startswith("ollama:"):
        os.environ["A2_MODEL"] = "ollama"
        os.environ["A2_OLLAMA_MODEL"] = interpreter.split(":", 1)[1]
    else:
        os.environ["A2_MODEL"] = interpreter


def run(interpreter):
    """One row per request: what the page would have done with this interpreter."""
    use(interpreter)
    rows = []
    for text, expected in REQUESTS.items():
        start = time.time()
        reply = server.handle({"text": text, "mode": "auto"})
        seconds = time.time() - start
        outcome = "nothing" if reply.get("nothing") else reply.get("mode", "error")
        # The interpreter label says "(simulated)" whenever the stand-in read the request.
        used_rules = "simulated" in reply.get("interpreter", "")
        rows.append({"text": text, "expected": expected, "outcome": outcome, "match": outcome == expected,
                     "fell_back": interpreter != "rules" and used_rules,
                     "flagged": "; ".join(reply.get("dropped", [])), "seconds": seconds})
    return rows


def markdown(results):
    """A table per interpreter and a summary line, ready to paste into notes or the report."""
    out = []
    for interpreter, rows in results.items():
        hits = sum(r["match"] for r in rows)
        falls = sum(r["fell_back"] for r in rows)
        mean = sum(r["seconds"] for r in rows) / len(rows)
        out.append("## %s: %d of %d as expected, %d fell back to the stand-in, %.1f s per request"
                   % (interpreter, hits, len(rows), falls, mean))
        out.append("")
        out.append("| Request | Expected | Got | Code checks dropped or flagged | s |")
        out.append("|---|---|---|---|---|")
        for r in rows:
            got = r["outcome"] + ("" if r["match"] else " ✗") + (" (fell back)" if r["fell_back"] else "")
            out.append("| %s | %s | %s | %s | %.1f |" % (r["text"], r["expected"], got, r["flagged"], r["seconds"]))
        out.append("")
    return "\n".join(out)


def main(argv=None):
    """Parse the arguments, run each interpreter, print (and optionally save) the tables."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--with", dest="interpreters", default="rules",
                        help="comma-separated: rules, ollama:<model>, claude, openai")
    parser.add_argument("--out", help="also write the tables to this file")
    args = parser.parse_args(argv)
    results = {name: run(name) for name in args.interpreters.split(",") if name.strip()}
    text = markdown(results)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
