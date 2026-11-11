"""Build the three storyboards as HTML pages from the screenshots in frames/.

    python3 docs/storyboards/make_storyboards.py

Each storyboard has five frames (W2 L06): the goal, the person's action, the system's inference and
action, the result, and recovery. Each frame is labelled with who acts (P = person, S = system), the
gulf involved, and the signifier on screen. The frames are real screenshots of the running prototype
(stand-in interpreter, θ = 0.5, fresh state). Open each HTML file and save it as PNG; the PNGs in this
folder were captured that way.
"""
import html
import os

HERE = os.path.dirname(os.path.abspath(__file__))

STORYBOARDS = {
    "show": ("Show: the motivating request", "Python and AWS people with Senior in the title", [
        ("Goal", "Find people with Python and AWS whose job title says Senior. "
                 "(An assistant once widened this 'and' to OR without saying so.)", "P", "—", "—"),
        ("Action", "frames/show-2-action.png", "P", "execution", "text box · Send ↵"),
        ("Inference + action", "frames/show-3-system.png", "S", "evaluation",
         "Show tag · reason with both counts · AND ⇄ OR chip"),
        ("Result", "frames/show-4-result.png", "S", "evaluation", "7 candidates · what was not searched"),
        ("Recovery", "frames/show-5-recovery.png", "P", "execution", "AND ⇄ OR chip · '(was 7)'"),
    ]),
    "ask": ("Ask: two readings that differ a lot", "senior Java developers", [
        ("Goal", "Find senior Java developers. 'Senior' could mean years of experience or the job title.",
         "P", "—", "—"),
        ("Action", "frames/ask-2-action.png", "P", "execution", "text box · Send ↵"),
        ("Inference + action", "frames/ask-3-system.png", "S", "execution",
         "one question · a count on each option · keys 1–3"),
        ("Result", "frames/ask-4-result.png", "both", "evaluation", "'Ask · answered' · the chosen chip"),
        ("Recovery", "frames/ask-5-recovery.png", "P", "execution", "chip ▾ · '(was 12)'"),
    ]),
    "write": ("Changing records: confirmed, then undone",
              "Java developers in London → shortlist them for the Senior Backend Engineer role", [
        ("Goal", "Put the Java developers in London on one job's shortlist, and change nothing else.",
         "P", "—", "—"),
        ("Action", "frames/write-2-action.png", "P", "execution", "text box (a follow-up, not a new search)"),
        ("Inference + action", "frames/write-3-system.png", "S", "evaluation",
         "job chosen · every change listed · Cancel focused"),
        ("Result", "frames/write-4-result.png", "S", "evaluation", "the result only · Undo"),
        ("Recovery", "frames/write-5-recovery.png", "P", "execution", "Undo"),
    ]),
}

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title><style>
body {{ margin: 0; padding: 24px; font: 15px/1.4 system-ui, sans-serif; color: #172033; background: #fff;
       width: 1560px; display: inline-block; }}
h1 {{ margin: 0 0 4px; font-size: 22px; }} .req {{ margin: 0 0 16px; color: #5b6578; }}
.grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }}
.frame {{ border: 1px solid #d5dce6; border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; }}
.head {{ padding: 6px 10px; background: #edf1f6; font-weight: 600; }}
.shot {{ flex: 1; display: flex; align-items: center; justify-content: center; background: #f6f8fb; padding: 10px;
        border-top: 1px solid #d5dce6; border-bottom: 1px solid #d5dce6; min-height: 120px; }}
img {{ display: block; max-width: 100%; max-height: 430px; border-radius: 4px; }}
.key {{ background: #edf1f6; }}
.key .goal {{ font-size: 14px; align-items: flex-start; flex-direction: column; gap: 6px; }}
.goal {{ flex: 1; display: flex; align-items: center; padding: 18px; font-size: 18px; min-height: 120px; }}
.tags {{ padding: 6px 10px; font-size: 13px; color: #3b4558; }} .tags b {{ color: #172033; }}
</style></head><body><h1>{title}</h1><p class="req">Request: <em>{request}</em> · real screenshots of the prototype</p>
<div class="grid">{frames}<div class="frame key"><div class="head">Key</div><div class="goal">
<div><b>P</b> = person acts · <b>S</b> = system acts</div>
<div><b>Gulf of execution</b>: can I say what I want?</div>
<div><b>Gulf of evaluation</b>: can I tell what it did?</div>
<div><b>Signifier</b>: what on screen shows what is possible</div></div></div></div></body></html>"""


def frame(i, step, content, who, gulf, signifier):
    """One labelled cell: a screenshot (or the goal in words) with who acts, the gulf and the signifier."""
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
