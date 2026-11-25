"""Build the three storyboards as HTML pages from the screenshots in frames/.

    python3 docs/storyboards/make_storyboards.py

Each storyboard has five frames (W2 L06): the goal, the person's action, the system's inference and
action, the result, and recovery. Each frame is labelled with who acts (P = person, S = system), the
gulf involved, and the signifier on screen. The frames are unedited screenshots of the running
prototype (θ = 0.5, fresh state), taken at twice the pixel density. Two storyboards use the default
rule-based stand-in; the ask storyboard uses a live model (Claude through Amazon Bedrock), and its
result frame shows the interpreter line the page prints. The frames are stacked in one column so the
text stays readable on a portrait A4 page. Open each HTML file and save it as PNG at twice the pixel
density; the PNGs in this folder were captured that way.
"""
import html
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
STAND_IN = "rule-based stand-in (simulated)"
LIVE = "a live model, Claude on Amazon Bedrock (implemented)"

STORYBOARDS = {
    "show": ("Show: the request that started the project", "Python and AWS people with Senior in the title",
             STAND_IN, "", [
        ("Goal", "Find people with Python and AWS whose job title says Senior. "
                 "(An assistant once widened this 'and' to OR without saying so.)", "P", "—", "—"),
        ("Action", "frames/show-2-action.png", "P", "execution", "text box · Send ↵"),
        ("Inference + action", "frames/show-3-system.png", "S", "evaluation",
         "Show tag · reason with both counts · AND ⇄ OR chip"),
        ("Result", "frames/show-4-result.png", "S", "evaluation", "7 candidates · what was not searched"),
        ("Recovery", "frames/show-5-recovery.png", "P", "execution", "AND ⇄ OR chip · '(was 7)'"),
    ]),
    "ask": ("Ask: two readings that differ a lot", "senior Java developers", LIVE,
            " <b>Planned, not built:</b> a free-text 'Other…' answer.", [
        ("Goal", "Find senior Java developers. 'Senior' could mean years of experience or the job title.",
         "P", "—", "—"),
        ("Action", "frames/ask-2-action.png", "P", "execution", "text box · Send ↵"),
        ("Inference + action", "frames/ask-3-system.png", "S", "evaluation (the reason), then execution (the options)",
         "one question · a count on each option · keys 1–3"),
        ("Result", "frames/ask-4-result.png", "both", "evaluation",
         "'Ask · answered' · Why? opened: the rule's numbers · the interpreter named"),
        ("Recovery", "frames/ask-5-recovery.png", "P", "execution", "chip ▾ changed to 'either' · '(was 12)'"),
    ]),
    "write": ("Act, then a change to records: confirmed, then undone",
              "Java developers in London → shortlist them for the Senior Backend Engineer role", STAND_IN, "", [
        ("Goal", "Put the Java developers in London on one job's shortlist, and change nothing else.",
         "P", "—", "—"),
        ("Action", "frames/write-2-action.png", "S, then P", "evaluation, then execution",
         "Act tag and its reason · 21 candidates · text box (a follow-up, not a new search)"),
        ("Inference + action", "frames/write-3-system.png", "S", "evaluation",
         "job chosen · every change listed · Cancel focused"),
        ("Result", "frames/write-4-result.png", "S", "evaluation", "what was confirmed · the result only · Undo"),
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
img {{ display: block; max-width: 100%; height: auto; border-radius: 4px; }}
.goal {{ padding: 12px 14px; font-size: 17px; border-top: 1px solid #c4ccd8; }}
.key {{ margin: 10px 0 0; font-size: 14px; color: #3b4558; }} .key b {{ color: #172033; }}
</style></head><body><h1>{title}</h1>
<p class="req">Request: <em>{request}</em> · real screenshots of the prototype ·
interpreter: {interpreter}</p>
<div class="grid">{frames}</div>
<p class="key"><b>Key.</b> <b>P</b> = the person acts, <b>S</b> = the system acts. <b>Gulf of execution</b>: can I say
what I want? <b>Gulf of evaluation</b>: can I tell what it did? <b>Signifier</b>: what on screen shows what is
possible.{note}</p></body></html>"""


def shown_width(path):
    """Half the PNG's pixel width: the screenshots are taken at twice the pixel density."""
    with open(os.path.join(HERE, path), "rb") as f:
        return struct.unpack(">I", f.read(24)[16:20])[0] // 2


def frame(i, step, content, who, gulf, signifier):
    """One labelled cell: a screenshot (or the goal in words) with who acts, the gulf and the signifier."""
    if content.endswith(".png"):
        body = ('<div class="shot"><img src="%s" width="%d" alt="%s"></div>'
                % (content, shown_width(content), html.escape(step)))
    else:
        body = '<div class="goal">%s</div>' % html.escape(content)
    return ('<div class="frame"><div class="head"><b>%d · %s</b><span class="tags"><b>Who:</b> %s · '
            '<b>Gulf:</b> %s · <b>Signifier:</b> %s</span></div>%s</div>'
            % (i, html.escape(step), who, gulf, html.escape(signifier), body))


if __name__ == "__main__":
    for name, (title, request, interpreter, note, frames) in STORYBOARDS.items():
        cells = "".join(frame(i + 1, *f) for i, f in enumerate(frames))
        path = os.path.join(HERE, "storyboard-%s.html" % name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(PAGE.format(title=html.escape(title), request=html.escape(request),
                                interpreter=html.escape(interpreter), note=note, frames=cells))
        print("wrote", os.path.relpath(path, HERE))
