*The UX review of the page before the chat layout, produced by the assistant (Claude Code) in November 2026, before pull request #35 applied it. It is the review the report and README refer to: section 3 advises against a chat transcript. Kept as written.*

# A2 UX review: clarity of interaction

## 1. Verdict
The skeleton is a real L07 hybrid: fixed slots, reasons, one-click AND/OR and counted options work. **The biggest clarity problem is what happens after the user acts.** The reason line becomes a generic "Updated with your changes" (show-5, ask-4, ask-5). The screen stops saying *what changed and why*, and the ask→show switch erases the question that was asked.

## 2. Ranked fixes

**1. The reason line reports the change and keeps the why.** After an edit: "You switched AND → OR: 9 candidates (was 4)." After an answer: "You said 'senior' means job title: 4 candidates." Below it, keep the first reason in muted text (composable in `app.js` from `state`). *Frames:* show-5, ask-4/5. *Serves:* feedback, gulf of evaluation, grounding, G11. *Effort:* S. *Risk:* none, since it uses the same slot.

**2. Editable chips look editable, and fixed chips look fixed.** "Tap a chip to change it" is a **false signifier**: Python, AWS and 'Senior' in title are inert spans with the same bordered pill shape as the toggle. Fixed chips become flat (no border), while editable ones keep a border and an always-visible ▾ or ⇄. The toggle reads "AND ⇄ OR", with `aria-pressed`. The copy names its target: "Tap AND to switch to OR." *Frames:* show-3, show-5. *Serves:* signifier, gulf of execution. *Effort:* S. *Risk:* none.

**3. Keep keyboard focus across re-renders.** Each chip change, toggle or answer rebuilds `#interpretation`, so focus falls to `<body>`. Refocus the control for the same `slot`, or the answered chip after an ask. Make `#count` `aria-live="polite"`. *Frames:* show-5, ask-4. *Serves:* accessibility, feedback. *Effort:* S–M. *Risk:* none.

**4. Add a pending state for live interpreters.** `runSearch` gives no feedback during a 1–10 s model call and doesn't handle a failed fetch. While waiting, show "Reading your request…" in the mode-line slot, set `aria-busy`, and disable Search and the chips. Show a plain error if the call fails. *Frames:* any 2→3 step. *Serves:* feedback timing (0.1/1/10 s), G2. *Effort:* S. *Risk:* low, since it looks the same in every mode.

**5. Make the ask options self-explanatory.** The "(10)" is unlabelled, so write "→ 10 candidates", and capitalise "Either". Use `<fieldset>`/`<legend>` for the radio semantics the spec requires, and focus the question when it appears. *Frame:* ask-3. *Serves:* the L07 *clarify* turn ("present the options"), signifier. *Effort:* S. *Risk:* none.

**6. Move the study settings out of the task path.** The Strategy select and the θ slider sit between the request and the answer, so they read as search filters. Put them in a collapsed `<details>` called "Study settings" at the bottom. *Frames:* every frame 2. *Serves:* gulf of execution. *Effort:* S. *Risk:* none.

**7. Lift the scope line and the "Ignored" words above the table.** A dropped word is a silent change, yet it sits in small grey text below the results. Place the line under the count, split it into "Searched: … · Not searched: …", and lead with "Ignored: 'rockstar'" in the ask colour. *Frames:* act-4, show-4. *Serves:* G10, G11, the L07 *decline* turn. *Effort:* S. *Risk:* low, as the position is the same in every mode.

**8. Strengthen act's escape hatch and drop the researcher copy.** Write "9 candidates · Read as: Java · London", and rename "Show filters" to "Edit this reading". Replace the server's "Mode set by hand to show. (The rule would have chosen act.)" with "Showing my reading so you can edit it.", and log the rule's choice. *Frames:* act-3, act-5. *Serves:* G9, HAX 9C. *Effort:* S. *Risk:* low.

## 3. The chat question
**No transcript. The mode line becomes one assistant turn that echoes at most one prior exchange**, for example: *"You: senior Java developers · I asked what 'senior' meant · you chose job title → 4 candidates."* It is one line in the existing slot, replaced on the next request.

**Against a transcript, per L07:** a transcript moves state into history. The AND/OR reading drifts up the history, and a correction becomes a new message, not a direct edit. That breaks "the screen holds the state". The echo adds only what the hybrid lacks: grounding of the exchange. Language still carries only the exception. No avatars or typing dots: PAIR and the expectation gulf (Luger & Sellen) warn that fluency over-promises.

## 4. What NOT to change
- **The fixed slots and the single question.** These keep the comparison fair.
- **Ask hides the results, with "Search anyway".** That is the condition under test.
- **"(guessed)" as text plus a dashed border, and no confidence %.** This follows PAIR and doesn't rely on colour alone.
- **"Read as" built from the filters that ran.** Honest under live models.
- **"(was N)", "Reset to my words" and no memory.** They prevent a silent carry-over of OR.
- **The ACT/SHOW/ASK badge.** It makes the condition legible in the report. Fix 1's sentence does the explaining.

## 5. Improved show mode
```text
[ Python and AWS people with Senior in the title ] [Search]
SHOW · You switched AND → OR: 9 candidates (was 4).
 Python  [OR ⇄ AND]  AWS  ['Senior' in title ▾]   Reset to my words
9 candidates (was 4) · Searched: title, skills, years, city
Not searched: CV text, notes · Interpreter: stand-in
Name | Title | Skills | Years | City | Work mode | Notice
▸ Study settings
```
