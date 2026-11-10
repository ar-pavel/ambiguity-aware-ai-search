"""Build the three storyboards as HTML pages from the screenshots in frames/.

    python3 docs/storyboards/make_storyboards.py

Each storyboard has five frames (W2 L06): the goal, the person's action, the system's inference and
action, the result, and recovery. Each frame is labelled with who acts (P = person, S = system), the
gulf involved, and the signifier on screen. The frames are real screenshots of the running prototype.
Open each HTML file and save it as PNG (the PNGs in this folder were captured that way).
"""
import html
import os

HERE = os.path.dirname(os.path.abspath(__file__))

STORYBOARDS = {
    "act": ("Act: a clear request", "Java developers in London", [
        ("Goal", "Find Java developers in London.", "P", "—", "example in the hint"),
        ("Action", "frames/act-2-action.png", "P", "execution", "search box"),
        ("Inference + action", "frames/act-3-system.png", "S", "evaluation", "ACT badge + reason"),
        ("Result", "frames/act-4-result.png", "S", "evaluation", "Read as · scope line"),
        ("Recovery", "frames/act-5-recovery.png", "P", "evaluation", "'Show filters' → chips"),
    ]),
    "show": ("Show: the motivating request", "Python and AWS people with Senior in the title", [
        ("Goal", "Find people with Python and AWS, titled Senior. (A real assistant once widened this 'and' to OR, silently.)",
         "P", "—", "—"),
        ("Action", "frames/show-2-action.png", "P", "execution", "search box"),
        ("Inference + action", "frames/show-3-system.png", "S", "evaluation", "AND chip + reason with counts"),
        ("Result", "frames/show-4-result.png", "S", "evaluation", "4 candidates · Read as"),
        ("Recovery", "frames/show-5-recovery.png", "P", "execution", "AND ⇄ chip · '(was 4)'"),
    ]),
    "ask": ("Ask: readings that differ a lot", "senior Java developers", [
        ("Goal", "Find senior Java developers. 'Senior' could mean years or job title.", "P", "—", "—"),
        ("Action", "frames/ask-2-action.png", "P", "execution", "search box"),
        ("Inference + action", "frames/ask-3-system.png", "S", "execution", "one question · counts on options"),
        ("Result", "frames/ask-4-result.png", "both", "evaluation", "highlighted chip · 4 candidates"),
        ("Recovery", "frames/ask-5-recovery.png", "P", "execution", "chip dropdown · '(was 4)'"),
    ]),
}

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title><style>
body {{ margin: 0; padding: 24px; font: 15px/1.4 system-ui, sans-serif; color: #1f2933; background: #fff; width: 1560px; display: inline-block; }}
h1 {{ margin: 0 0 4px; font-size: 22px; }} .req {{ margin: 0 0 16px; color: #616e7c; }}
.grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }}
.frame {{ border: 1px solid #d9e2ec; border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; }}
.head {{ padding: 6px 10px; background: #f5f7fa; font-weight: 600; }} .head span {{ color: #616e7c; font-weight: 400; }}
.shot {{ flex: 1; display: flex; align-items: center; justify-content: center; background: #fff; padding: 6px;
        border-top: 1px solid #d9e2ec; border-bottom: 1px solid #d9e2ec; min-height: 120px; }}
img {{ display: block; max-width: 100%; max-height: 420px; }}
.key {{ background: #f5f7fa; }} .key .goal {{ font-size: 14px; align-items: flex-start; flex-direction: column; gap: 6px; }}
.goal {{ flex: 1; display: flex; align-items: center; padding: 18px; font-size: 18px; min-height: 120px; }}
.tags {{ padding: 6px 10px; font-size: 13px; color: #3e4c59; }} .tags b {{ color: #1f2933; }}
</style></head><body><h1>{title}</h1><p class="req">Request: <em>{request}</em> · real screenshots of the prototype</p>
<div class="grid">{frames}<div class="frame key"><div class="head">Key</div><div class="goal">
<div><b>P</b> = person acts · <b>S</b> = system acts</div>
<div><b>Gulf of execution</b>: can I say what I want?</div>
<div><b>Gulf of evaluation</b>: can I tell what it did?</div>
<div><b>Signifier</b>: what on screen shows what is possible</div></div></div></div></body></html>"""


def frame(i, step, content, who, gulf, signifier):
    body = ('<div class="shot"><img src="%s" alt="%s"></div>' % (content, html.escape(step)) if content.endswith(".png")
            else '<div class="goal">%s</div>' % html.escape(content))
    return ('<div class="frame"><div class="head">%d · %s</div>%s<div class="tags"><b>Who:</b> %s · '
            '<b>Gulf:</b> %s · <b>Signifier:</b> %s</div></div>'
            % (i, html.escape(step), body, who, gulf, html.escape(signifier)))


if __name__ == "__main__":
    for name, (title, request, frames) in STORYBOARDS.items():
        cells = "".join(frame(i + 1, *f) for i, f in enumerate(frames))
        path = os.path.join(HERE, "storyboard-%s.html" % name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(PAGE.format(title=html.escape(title), request=html.escape(request), frames=cells))
        print("wrote", os.path.relpath(path, HERE))
