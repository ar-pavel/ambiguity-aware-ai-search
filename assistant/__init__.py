"""Ask, Show, or Just Do It? The assistant behind the chat page.

    server.py     HTTP server and the request handlers
    replies.py    what the page shows, built from what ran
    interpret.py  rule-based stand-in, and the checks on a live model's reply
    model.py      the live model call (Ollama, Claude or OpenAI)
    strategy.py   the act / show / ask rule
    search.py     filters, and the "Read as" line
    commands.py   typed follow-ups ("shortlist them for the Java role")
    actions.py    plan, apply and undo a write; the skills-fit warning
    store.py      the only module that writes
    log.py        one line per turn for evaluation

Files the app reads or writes (data/, web/, state/, logs/, .env) stay at the project root.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
