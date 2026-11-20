"""Build the three storyboards as HTML pages from the screenshots in frames/.

    python3 docs/storyboards/make_storyboards.py

Each storyboard has five frames (W2 L06): the goal, the person's action, the system's inference and
action, the result, and recovery. Each frame is labelled with who acts (P = person, S = system), the
gulf involved, and the signifier on screen. The frames are real screenshots of the running prototype
(stand-in interpreter, θ = 0.5, fresh state). The frames are stacked in one column so that the text
stays readable when a storyboard is printed on a portrait A4 page. Open each HTML file and save it as
PNG; the PNGs in this folder were captured that way, at twice the pixel density.
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
body {{ margin: 0; padding: 20px; font: 16px/1.4 system-ui, sans-serif; color: #172033; background: #fff;
       width: 940px; display: inline-block; }}
h1 {{ margin: 0 0 2px; font-size: 22px; }} .req {{ margin: 0 0 12px; color: #3b4558; }}
.grid {{ display: grid; grid-template-columns: 1fr; gap: 10px; }}
.frame {{ border: 1px solid #c4ccd8; border-radius: 8px; overflow: hidden; }}
.head {{ display: flex; justify-content: space-between; gap: 16px; padding: 6px 10px; background: #edf1f6; }}
.head b {{ white-space: nowrap; }} .tags {{ font-size: 14px; color: #3b4558; text-align: right; }}
.tags b {{ color: #172033; }}
.shot {{ display: flex; justify-content: center; background: #f6f8fb; padding: 8px; border-top: 1px solid #c4ccd8; }}
img {{ display: block; max-width: 100%; border-radius: 4px; }}
.goal {{ padding: 12px 14px; font-size: 17px; border-top: 1px solid #c4ccd8; }}
.key {{ margin: 10px 0 0; font-size: 14px; color: #3b4558; }} .key b {{ color: #172033; }}
</style></head><body><h1>{title}</h1>
<p class="req">Request: <em>{request}</em> · real screenshots of the prototype ·
interpreter: rule-based stand-in (simulated)</p>
<div class="grid">{frames}</div>
<p class="key"><b>Key.</b> <b>P</b> = the person acts, <b>S</b> = the system acts. <b>Gulf of execution</b>: can I say
what I want? <b>Gulf of evaluation</b>: can I tell what it did? <b>Signifier</b>: what on screen shows what is
possible.</p></body></html>"""


def frame(i, step, content, who, gulf, signifier):
    """One labelled cell: a screenshot (or the goal in words) with who acts, the gulf and the signifier."""
    body = ('<div class="shot"><img src="%s" alt="%s"></div>' % (content, html.escape(step)) if content.endswith(".png")
            else '<div class="goal">%s</div>' % html.escape(content))
    return ('<div class="frame"><div class="head"><b>%d · %s</b><span class="tags"><b>Who:</b> %s · '
            '<b>Gulf:</b> %s · <b>Signifier:</b> %s</span></div>%s</div>'
            % (i, html.escape(step), who, gulf, html.escape(signifier), body))


if __name__ == "__main__":
    for name, (title, request, frames) in STORYBOARDS.items():
        cells = "".join(frame(i + 1, *f) for i, f in enumerate(frames))
        path = os.path.join(HERE, "storyboard-%s.html" % name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(PAGE.format(title=html.escape(title), request=html.escape(request), frames=cells))
        print("wrote", os.path.relpath(path, HERE))
