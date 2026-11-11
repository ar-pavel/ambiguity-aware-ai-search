// The page: a conversation. Each request or action adds the recruiter's turn and the assistant's reply.
// Only the latest assistant turn is live (its chips, question and buttons work); earlier turns are
// frozen copies, so a click can never apply to an old request. The server keeps no conversation:
// every reply comes from re-running the request with the recruiter's edits.
const $ = (id) => document.getElementById(id);

// What the recruiter has asked for so far. Edits are re-applied by the server to a fresh reading.
// last: the control just used (the server says what it changed). focus: the control to refocus after re-render.
const state = { text: "", mode: "auto", choices: {}, op: null, lastCount: null, lastNoun: null, answered: null,
                last: null, focus: null, firstReason: null, firstHint: null, busy: false };
const chosenMode = () => $("mode").value;          // the strategy picked in the study settings
const theta = () => Number($("theta").value);       // the rule's overlap threshold
const live = () => document.querySelector("#chat .turn.live");

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text) node.textContent = text;
  return node;
}

const capital = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const results = (n, noun) => n + " " + noun + (n === 1 ? "" : "s");

// ---- The conversation ---------------------------------------------------------------------------

function append(node) {
  $("chat").append(node);
  return node;
}

// The recruiter's turn: what they typed, or the control they used, in words.
function addUser(text) {
  append(el("section", { class: "turn user" })).append(el("p", {}, text));
}

// A study-setting change is not part of the task, so it is a small note rather than a turn.
function addNote(text) {
  append(el("p", { class: "turn note" }, text));
}

// Freeze the live turn: redraw it read-only from the reply it was drawn from.
function freezeLive() {
  const old = live();
  if (old) old.replaceWith(assistantTurn(old.data, false));
}

function addAssistant(data) {
  freezeLive();
  const turn = append(assistantTurn(data, true));
  // A job question from a typed command belonged to the old results: it can no longer be answered.
  document.querySelectorAll("#chat .turn.command .options").forEach((o) => o.remove());
  const label = data._answered ? "Ask, answered" : capital(data.mode);   // the same words as the tag on screen
  const count = results(data.count, data.noun);
  const reason = data.reason.includes(count) ? data.reason : data.reason + (data.mode === "ask" ? "" : " " + count + ".");
  announce(data.error ? data.error : label + ". " + reason);
  // Keep the recruiter's own turn in view above the reply, so it reads as an exchange.
  const before = turn.previousElementSibling;
  (before && before.classList.contains("user") ? before : turn).scrollIntoView({ block: "start" });
  return turn;
}

let thinking = null;   // "Reading your request…", shown only for a noticeable wait
function setBusy(on) {
  state.busy = on;
  $("chat").setAttribute("aria-busy", on ? "true" : "false");
  document.querySelectorAll("#ask-form button, .turn.live button, .turn.live select, .turn.command button, .suggestion")
    .forEach((c) => { c.disabled = on; });
}

// What a reply is computed from. Saved before a change, so a failed reply can put it back.
const snapshot = () => JSON.parse(JSON.stringify({ text: state.text, mode: state.mode, choices: state.choices,
  op: state.op, answered: state.answered, last: state.last, lastCount: state.lastCount, lastNoun: state.lastNoun }));

// prev: the state before the recruiter's change. If the reply fails, the change is undone on the page
// too, so the live turn still matches what the server would do, and it stays usable for a retry.
async function runSearch(prev) {
  planSeq++;  // a confirmation for the old results must not open over the new ones
  setBusy(true);
  const slow = setTimeout(() => {
    thinking = append(el("p", { class: "turn assistant thinking" }, "Reading your request…"));
    thinking.scrollIntoView({ block: "end" });
  }, 300);
  let data;
  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: state.text, mode: state.mode, choices: state.choices, op: state.op,
                             theta: theta(), last: state.last }),
    });
    data = await res.json();
  } catch (e) {
    data = { error: "Could not reach the app. Is python3 app.py still running?" };
  } finally {
    clearTimeout(slow);
    if (thinking) { thinking.remove(); thinking = null; }
  }
  try {
    if (data.error && (live() || data.nothing)) {
      if (prev) Object.assign(state, prev);   // the search on screen, if any, stays the one actions use
      addError(data.error, data.nothing);
    } else {
      addAssistant(data);
    }
  } finally {
    setBusy(false);   // even if drawing the reply failed, the page must not stay locked
    restoreFocus();
    if (state.settingsChanged) rerunWithSettings();
  }
}

// A failed reply is reported under the live turn, which stays live so the recruiter can retry.
// "Nothing to search for" uses the same path, worded and coloured as a reply, not a fault.
function addError(text, calm) {
  const turn = append(replyTurn(calm ? "is-done" : "is-error"));
  turn.append(el("p", { class: calm ? "" : "error" }, text));
  announce(turn.textContent);
  turn.scrollIntoView({ block: "start" });
}

// Screen readers hear one short line per reply, not the whole table. Cleared first, so the same
// words twice in a row are still read out.
function announce(text) {
  $("status").textContent = "";
  setTimeout(() => { $("status").textContent = text; }, 50);
}

// After a re-render, put focus back on the control the recruiter used (UX review fix 3).
// "question": a new request was sent, so focus its question if one is asked. Other re-runs (a study
// setting, an undo) leave focus where the recruiter is working.
function restoreFocus() {
  if (!state.focus) return keepFocus();
  const turn = live();
  const target = !turn ? null
    : state.focus === "question" ? turn.querySelector("fieldset")
    : state.focus === "reading" ? turn.querySelector("fieldset, .chips button, .chips select")
    : state.focus === "result" ? document.querySelector("#chat .turn.result:last-of-type .notice")
    : turn.querySelector('[data-slot="' + state.focus + '"]');
  if (target) target.focus(); else keepFocus();
  state.focus = null;
}

// If the control the recruiter used has gone (a disabled or replaced button), focus the new reply,
// so keyboard users are never dropped at the top of the page.
function keepFocus() {
  const a = document.activeElement;
  if (a && a !== document.body && !a.disabled && document.body.contains(a)) return;
  const turn = live();
  if (turn) { turn.setAttribute("tabindex", "-1"); turn.focus({ preventScroll: true }); }
  else $("request").focus();
}

// A short assistant reply that is not a search turn (nothing to search for, an error, a command's
// answer): the same card and mark as any other reply, without the search's parts.
function replyTurn(classes) {
  const turn = el("section", { class: "turn assistant reply " + classes });
  const mark = el("span", { class: "mark small", "aria-hidden": "true" });
  mark.append(el("i"), el("i"), el("i"));
  turn.append(mark);
  return turn;
}

// ---- One assistant turn -------------------------------------------------------------------------

function assistantTurn(data, isLive) {
  if (isLive && !data.error) remember(data);
  // The mode colours the turn's edge. The reply to an answered question stays an ask turn, so the
  // conversation reads ask -> answered, not ask -> show.
  const kind = data.error ? "error" : data._answered ? "ask" : data.mode;
  const turn = el("section", { class: "turn assistant " + (isLive ? "live" : "frozen") + " is-" + kind });
  turn.data = data;
  if (data.error) {
    turn.append(el("p", { class: "error" }, data.error));
    return turn;
  }
  turn.append(modeLine(data, isLive), whyBox(data.why));
  if (data.mode === "ask" && data.question) {
    turn.append(isLive ? questionCard(data.question) : askedLine(data.question));
    return turn;   // ask before searching: no results until the question is answered
  }
  if (data.mode === "show") {
    turn.append(isLive ? chipRow(data) : el("p", { class: "read-as" }, "Read as: " + data.read_as));
  } else {
    turn.append(el("p", { class: "read-as" }, "Read as: " + data.read_as));
    // Act keeps its answer; any editable chips open in place, with no extra exchange (fair to act).
    // With nothing to choose, the way to change it is to type a new request.
    if (isLive && data.chips.some((c) => c.kind === "op" || c.options)) {
      const toShow = el("button", { type: "button", class: "link" }, "Edit this reading");
      toShow.addEventListener("click", () => {
        const row = chipRow(data, false);
        toShow.replaceWith(row);
        const first = row.querySelector("button, select");
        if (first) first.focus();
      });
      turn.append(toShow);
    }
  }
  if (data.dropped.length) turn.append(el("p", { class: "ignored" }, "Ignored: " + data.dropped.join("; ") + "."));
  const row = el("div", { class: "count-row" });
  row.append(el("p", { class: "count" }, results(data.count, data.noun) + (data._was || "")));
  if (isLive && data.count > 0) row.append(actionButton(data));
  turn.append(row, el("p", { class: "scope" },
    data.searched + " · " + data.not_searched + " · Interpreter: " + data.interpreter + "."));
  if (data.count > 0) turn.append(isLive ? tableBox(data.table) : frozenTable(data));
  return turn;
}

// Work out once, when a reply arrives, what it says relative to the turn before: "(was N)" and the
// first reason. Stored on the reply, so the frozen copy says the same thing later.
function remember(data) {
  if (data._seen) return;
  data._seen = true;
  if (!state.last && !data._refresh) { state.firstReason = data.reason; state.firstHint = data.hint; }
  if (state.last && state.firstReason && state.firstReason !== data.reason) {
    data._first = withoutHint(state.firstReason, state.firstHint);   // its "Tap…" no longer applies
  }
  data._answered = !!(state.last && state.last.answered);
  if (data.mode !== "ask") {
    // "(was N)" only compares like with like: not 5 candidates with 1 job.
    if (state.lastCount !== null && state.lastNoun === data.noun && state.lastCount !== data.count) {
      data._was = " (was " + state.lastCount + ")";
    }
    state.lastCount = data.count;
    state.lastNoun = data.noun;
  } else {
    state.lastCount = null;
  }
}

const withoutHint = (reason, hint) => (hint && reason.endsWith(" " + hint) ? reason.slice(0, -hint.length - 1) : reason);

function modeLine(data, isLive) {
  const p = el("p", { class: "mode-line" });
  // The assistant is signed with the three-mode mark, not a face: it should not look like a person.
  const mark = el("span", { class: "mark small", "aria-hidden": "true" });
  mark.append(el("i"), el("i"), el("i"));
  p.append(mark);
  const mode = data._answered ? "ask" : data.mode;
  p.append(el("strong", { class: "mode mode-" + mode }, data._answered ? "Ask · answered" : capital(mode)),
           el("span", { class: "reason" }, isLive ? data.reason : withoutHint(data.reason, data.hint)));
  if (!isLive) p.append(el("span", { class: "earlier" }, "Earlier · read-only"));
  if (data._first) p.append(el("span", { class: "first-reason" }, "At first: " + data._first));
  return p;
}

// The rule's comparison, row by row, collapsed by default (Amershi G11).
function whyBox(why) {
  const box = el("details", { class: "why" });
  box.append(el("summary", {}, "Why?"));
  const body = el("div", { class: "why-body" });
  body.append(el("p", {}, why.summary));
  if (why.rows.length) {
    const t = el("table", { class: "why-table" });
    const head = el("tr");
    ["Unclear part", "Reading used", "Other reading", "Lists share", "Result"].forEach((h) => head.append(el("th", { scope: "col" }, h)));
    t.append(el("thead"), el("tbody"));
    t.tHead.append(head);
    for (const r of why.rows) {
      const row = el("tr");
      const [used, other] = r.readings;
      [r.part, used.label + " → " + used.count, other.label + " → " + other.count,
       r.share, r.verdict].forEach((v) => row.append(el("td", {}, String(v))));
      t.tBodies[0].append(row);
    }
    const wrap = el("div", { class: "table-wrap" });
    wrap.append(t);
    body.append(wrap);
  }
  why.notes.forEach((n) => body.append(el("p", { class: "why-note" }, n)));
  box.append(body);
  return box;
}

// Ask: one question, each option saying what it would give (UX review fix 5). A click is the reply.
function questionCard(q) {
  const card = el("fieldset", { class: "question", tabindex: "-1" });
  card.append(el("legend", { class: "question-text" }, q.text));
  const options = el("div", { class: "options" });
  q.options.forEach((opt, i) => {
    // A keycap per option: pressing its number answers (see the keydown handler below).
    const b = el("button", { type: "button", class: "option", "aria-keyshortcuts": String(i + 1) });
    b.append(el("kbd", { class: "key", "aria-hidden": "true" }, String(i + 1)),
             el("span", {}, capital(opt.label) + " → " + results(opt.count, opt.noun)));
    b.addEventListener("click", () => act(capital(opt.label), () => {
      state.choices[q.slot] = i; state.answered = q.slot;
      state.last = { slot: q.slot, answered: true }; state.focus = q.slot;
    }));
    options.append(b);
  });
  const best = q.options[q.default].label;
  const anyway = el("button", { type: "button", class: "link" }, "Search anyway with my best guess (" + best + ")");
  anyway.addEventListener("click", () => act("Search anyway (" + best + ")", () => { state.mode = "show"; state.last = { anyway: true }; }));
  card.append(options, anyway);
  if (q.options.length <= 9) {
    card.append(el("p", { class: "key-hint" }, "Press 1–" + q.options.length + " to answer."));
  }
  return card;
}

function askedLine(q) {
  const p = el("p", { class: "asked" }, q.text + " ");
  p.append(el("span", { class: "muted" }, q.options.map((o) => capital(o.label) + " → " + results(o.count, o.noun)).join(" · ")));
  return p;
}

// Show: a chip for each assumption. Fixed parts are flat text; only choices look and act like controls
// (UX review fix 2): open choices are dropdowns marked ▾, the AND/OR operator is a one-click ⇄ toggle.
function chipRow(data, withReset = true) {
  const wrap = el("div");
  const row = el("div", { class: "chips", role: "group", "aria-label": "How I read your request" });
  data.chips.forEach((c) => row.append(chipFor(c)));
  const reset = el("button", { type: "button", class: "link" }, "Reset to my words");
  reset.addEventListener("click", () => act("Reset to my words", () => {
    Object.assign(state, { choices: {}, op: null, answered: null, last: null, mode: chosenMode(), focus: "reading" });
  }));
  wrap.append(row);
  if (withReset) wrap.append(reset);
  return wrap;
}

function chipFor(chip) {
  if (chip.kind === "skill") return el("span", { class: "chip fixed" }, chip.text);
  if (chip.kind === "op") {
    const other = chip.value === "AND" ? "OR" : "AND";
    const b = el("button", { type: "button", class: "chip op" + (chip.guessed ? " guessed" : ""), "data-slot": "op",
                             title: chip.evidence, "aria-label": chip.value + " ⇄ " + other + (chip.guessed ? " (guessed)" : "") + ": skills joined by " + chip.value + "; press to switch to " + other + "." },
                 chip.value + " ⇄ " + other + (chip.guessed ? " (guessed)" : ""));
    b.addEventListener("click", () => act("Switch " + chip.value + " to " + other, () => {
      state.op = other; state.last = { op: true }; state.focus = "op";
    }));
    return b;
  }
  if (!chip.options) return el("span", { class: "chip fixed" }, chip.text);
  const answered = chip.slot === state.answered ? " answered" : "";
  const wrap = el("label", { class: "chip choice" + (chip.guessed ? " guessed" : "") + answered, title: chip.evidence });
  const select = el("select", { "aria-label": chip.text + (chip.guessed ? " (guessed)" : "") + ": change", "data-slot": chip.slot });
  chip.options.forEach((label, i) => {
    const opt = el("option", { value: i }, label);
    if (i === chip.chosen) opt.selected = true;
    select.append(opt);
  });
  select.addEventListener("change", () => {
    const i = Number(select.value);
    act("Change to: " + chip.options[i], () => {
      state.choices[chip.slot] = i; state.last = { slot: chip.slot }; state.focus = chip.slot;
    });
  });
  wrap.append(select, el("span", { class: "caret", "aria-hidden": "true" }, "▾"));
  if (chip.guessed) wrap.append(el("span", { class: "tag" }, "(guessed)"));
  return wrap;
}

// Every control in the live turn is a reply: say it in the recruiter's turn, change the state, re-run.
function act(said, change) {
  if (state.busy) return;
  const prev = snapshot();
  addUser(said);
  change();
  runSearch(prev);
}

function tableBox(table) {
  const wrap = el("div", { class: "table-wrap" });
  const t = el("table", { class: "results" });
  const head = el("tr");
  table.headers.forEach((h) => head.append(el("th", { scope: "col" }, h)));
  t.append(el("thead"), el("tbody"));
  t.tHead.append(head);
  for (const cells of table.rows) {
    const row = el("tr");
    cells.forEach((v) => row.append(el("td", {}, v)));
    t.tBodies[0].append(row);
  }
  wrap.append(t);
  return wrap;
}

// Earlier results stay inspectable, folded away so the conversation stays short.
function frozenTable(data) {
  const box = el("details", { class: "earlier" });
  box.append(el("summary", {}, "Show these " + results(data.count, data.noun)), tableBox(data.table));
  return box;
}

// ---- Write actions: plan -> confirm in a dialog -> apply -> undo ---------------------------------

const searchPayload = () => ({ text: state.text, mode: state.mode, choices: state.choices, op: state.op, theta: theta() });
let pending = null;   // the plan shown in the dialog, and the button that opened it

async function post(path, body) {
  const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return res.json();
}

function actionButton(data) {
  const action = data.target === "jobs" ? ["close", "Close these jobs…"] : ["shortlist", "Shortlist for a job…"];
  const b = el("button", { type: "button", class: "secondary" }, action[1]);
  b.addEventListener("click", () => openPlan(action[0], b, null));
  return b;
}

// ---- The result of a write or undo ------------------------------------------------------------
// A write does not change the search, so the reply is only what was done, with Undo. The live search
// above is refreshed where it is (a closed job leaves "open jobs"), not printed again.

function addResult(text, canUndo) {
  // Undo always reverses the most recent write, so only the newest result may offer it.
  document.querySelectorAll("#chat .turn.result .notice button").forEach((b) => b.remove());
  const turn = append(el("section", { class: "turn assistant result" }));
  const n = el("p", { class: "notice", tabindex: "-1" });
  n.append(el("span", {}, text + " "));
  if (canUndo) {
    const u = el("button", { type: "button", class: "link", "aria-label": "Undo: " + text }, "Undo");
    u.addEventListener("click", () => undo(u));
    n.append(u);
  }
  turn.append(n);
  announce(text);
  turn.scrollIntoView({ block: "nearest" });
  return turn;
}

async function undo(button) {
  if (state.busy) return;
  setBusy(true);
  button.remove();
  addUser("Undo that");
  let out;
  try { out = await post("/api/undo", {}); } catch (e) { out = { ok: false, error: "Could not reach the app, so nothing was undone." }; }
  addResult(out.ok ? out.done + "." : out.error, false);
  await refreshLive();
}

// Re-run the current search and redraw the live turn in place, keeping it live.
async function refreshLive() {
  planSeq++;
  setBusy(true);
  try {
    const turn = live();
    if (turn && state.text) {
      const res = await fetch("/api/search", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: state.text, mode: state.mode, choices: state.choices, op: state.op, theta: theta(), last: state.last }) });
      const data = await res.json();
      if (!data.error) {
        data._refresh = true;   // the same request, so "At first" and the first reason stay as they were
        turn.replaceWith(assistantTurn(data, true));
      }
    }
  } catch (e) {
    // the result turn already says what happened; the old results stay on screen
  } finally {
    setBusy(false);
    state.focus = "result";
    restoreFocus();
  }
}

function fillPlan(plan) {
  const d = $("confirm");
  d.querySelector(".confirm-read-as").textContent = "Your search: " + (plan.read_as || "");
  d.querySelector(".confirm-summary").textContent = plan.summary || "";
  const list = d.querySelector(".confirm-changes");
  list.innerHTML = "";
  // Advice, not a block: say who doesn't list the job's skills, and mark them in the list.
  const warn = d.querySelector(".confirm-warning");
  warn.textContent = plan.warning ? "⚠ " + plan.warning : "";
  warn.hidden = !plan.warning;
  // Those who don't fit come first, where they will be seen.
  [...(plan.changes || [])].sort((x, y) => (x.fits === false ? 0 : 1) - (y.fits === false ? 0 : 1)).forEach((c) => {
    const item = el("li", c.fits === false ? { class: "misfit" } : {}, c.label + (c.before ? "  (" + c.before + " → " + c.after + ")" : ""));
    if (c.fits === false) item.append(el("span", { class: "misfit-tag" }, " · no matching skills"));
    list.append(item);
  });
  const skipped = d.querySelector(".confirm-skipped");
  skipped.querySelector("ul").innerHTML = "";
  (plan.skipped || []).forEach((s) => skipped.querySelector("ul").append(el("li", {}, s.label + ": " + s.why)));
  skipped.querySelector("summary").textContent = (plan.skipped || []).length + " will not change";
  skipped.hidden = !(plan.skipped || []).length;
  const pick = $("job");
  $("job-pick").hidden = plan.action !== "shortlist";
  if (plan.jobs && pick.options.length === 1) {
    plan.jobs.forEach((j) => pick.append(el("option", { value: j.id }, j.label)));
  }
  if (plan.action === "shortlist") pick.value = plan.job_id || "";
  d.querySelector(".confirm-error").textContent = plan.valid ? "" : (plan.error || "");
  const apply = $("confirm-apply");
  apply.textContent = plan.confirm_label || "Confirm";
  apply.disabled = !plan.valid;
}

// Each plan request gets a number. Esc, a new search or a newer request moves planSeq on, so a reply
// that arrives late is dropped instead of opening the dialog nobody is waiting for any more.
let planSeq = 0;

async function openPlan(action, trigger, jobId) {
  const d = $("confirm");
  const fromButton = !d.open;
  if (fromButton && trigger.getAttribute("aria-disabled") === "true") return;  // already preparing
  const seq = ++planSeq;
  const label = trigger.textContent;
  if (!fromButton) {   // a new job was chosen: the old plan must not be confirmable meanwhile
    $("confirm-apply").disabled = true;
    d.querySelector(".confirm-error").textContent = "";
  }
  if (fromButton) { trigger.setAttribute("aria-disabled", "true"); trigger.textContent = "Preparing…"; }
  let plan = null;
  try {
    plan = await post("/api/plan", { action, job_id: jobId, search: searchPayload() });
  } catch (e) {
    plan = null;
  } finally {
    if (fromButton) { trigger.removeAttribute("aria-disabled"); trigger.textContent = label; }
  }
  if (seq !== planSeq) return;
  if (!plan) {
    const msg = "Could not reach the app. Is python3 app.py still running?";
    if (d.open) d.querySelector(".confirm-error").textContent = msg; else addError(msg);
    return;
  }
  if (!plan.action) plan.action = action;
  pending = { plan, trigger };
  fillPlan(plan);
  if (!d.open) { d.showModal(); $("confirm-cancel").focus(); }  // the safe choice has focus first
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("confirm").open) planSeq++;  // cancels a confirmation still loading
});

$("job").addEventListener("change", () => openPlan("shortlist", pending.trigger, $("job").value || null));

$("confirm-apply").addEventListener("click", async () => {
  const apply = $("confirm-apply");
  if (apply.disabled) return;
  apply.disabled = true;   // one write per confirmation, however often it is clicked
  applying = true;         // Esc and Cancel wait until the server has answered
  $("confirm-cancel").disabled = true;
  setBusy(true);
  const { plan } = pending;
  const said = apply.textContent + (plan.job ? " for " + plan.job : "");
  let out;
  try {
    out = await post("/api/apply", { action: plan.action, job_id: plan.job_id, fingerprint: plan.fingerprint, search: searchPayload() });
  } catch (e) {
    out = { ok: false, error: "Could not reach the app, so nothing was changed. Try again." };
  } finally {
    applying = false;
    $("confirm-cancel").disabled = false;
    setBusy(false);
  }
  if (!out.ok) {
    if (!out.plan) apply.disabled = false;  // refused: show what is true now, and let the recruiter confirm again
    if (out.plan) { pending.plan = Object.assign({ action: plan.action }, out.plan); fillPlan(pending.plan); }
    $("confirm").querySelector(".confirm-error").textContent = out.error;
    return;
  }
  $("confirm").close();
  addUser("Confirmed: " + said);
  addResult(out.done + ".", true);
  await refreshLive();
});

let applying = false;
$("confirm").addEventListener("cancel", (e) => { if (applying) e.preventDefault(); });

// Esc and Cancel close the dialog without writing anything; focus goes back to the button that opened it.
$("confirm").addEventListener("close", () => {
  planSeq++;  // a job-picker reply still on its way must not reopen it
  const p = pending;
  $("job").innerHTML = '<option value="">Choose a job…</option>';
  if (p && p.trigger && document.body.contains(p.trigger)) p.trigger.focus();
});

// ---- Sending a request, examples, settings ------------------------------------------------------

// ---- Typed follow-up commands ("shortlist them for the Java role", "close these") ---------------

// A command only makes sense on results the recruiter can see and has not been asked about.
function hasResults() {
  const t = live();
  return !!(t && t.data && !t.data.error && t.data.mode !== "ask" && t.data.count > 0);
}
const liveActionButton = () => (live() ? live().querySelector(".count-row button") : null);

// A command turn is not live: the live turn above it keeps its results, chips and buttons, and
// the command acts on exactly those (the server re-runs that search, never this text).
function commandTurn(kind) {
  return append(replyTurn("command is-" + kind));
}

// Returns true if the server's answer was handled as a command, false to run the text as a search.
function runCommand(text, cmd, seq) {
  const trigger = liveActionButton();
  if (!cmd || cmd.kind === "search" || (cmd.kind !== "error" && !trigger)) return false;
  addUser(text);
  if (cmd.kind === "error") { addError(cmd.error); return true; }
  if (cmd.kind === "plan") {
    const turn = commandTurn("done");
    turn.append(el("p", {}, cmd.reason));
    announce(cmd.reason);
    turn.scrollIntoView({ block: "start" });
    if (seq === planSeq) openPlan(cmd.action, trigger, cmd.job_id);   // Esc while waiting cancels it
    return true;
  }
  // "ask": several jobs match. One button per job; a click is the reply and opens the confirmation.
  const turn = commandTurn("ask");
  const card = el("fieldset", { class: "question", tabindex: "-1" });
  card.append(el("legend", { class: "question-text" }, cmd.text));
  const options = el("div", { class: "options" });
  cmd.options.forEach((opt) => {
    const b = el("button", { type: "button", class: "option" }, opt.label);
    b.addEventListener("click", () => {
      const button = liveActionButton();
      if (state.busy || !button) return;
      addUser(opt.label);
      options.remove();
      openPlan(cmd.action, button, opt.job_id);
    });
    options.append(b);
  });
  card.append(options);
  turn.append(el("p", { class: "reason" }, cmd.reason), card);
  announce(cmd.reason + " " + cmd.text);
  turn.scrollIntoView({ block: "start" });
  const first = options.querySelector("button");
  if (first) first.focus();
  return true;
}

async function send(text) {
  text = text.trim();
  if (!text || state.busy) return;
  if (hasResults()) {   // is it a command on these results, or a new search?
    $("request").value = "";
    const seq = planSeq;
    setBusy(true);
    let cmd = null;
    try { cmd = await post("/api/command", { text, search: searchPayload() }); } catch (e) { cmd = null; }  // a new search instead
    setBusy(false);
    if (runCommand(text, cmd, seq)) {
      if (state.settingsChanged) rerunWithSettings();
      return;
    }
  }
  const prev = snapshot();
  addUser(text);
  Object.assign(state, { text, mode: chosenMode(), choices: {}, op: null, lastCount: null,
                         answered: null, last: null, focus: "question" });  // the question is next
  $("request").value = "";
  runSearch(prev);
}

// Number keys answer the live question, unless the recruiter is typing or the dialog is open.
document.addEventListener("keydown", (e) => {
  if (!/^[1-9]$/.test(e.key) || e.ctrlKey || e.metaKey || e.altKey || state.busy || $("confirm").open) return;
  if (e.target.closest && e.target.closest("input, textarea, select, [contenteditable]")) return;
  const option = document.querySelectorAll("#chat .turn.live fieldset.question button.option")[Number(e.key) - 1];
  if (option) { e.preventDefault(); option.click(); }
});

$("ask-form").addEventListener("submit", (e) => { e.preventDefault(); send($("request").value); });
document.querySelectorAll(".suggestion").forEach((b) => b.addEventListener("click", () => send(b.textContent)));

$("new-chat").addEventListener("click", () => {
  if (state.busy) return;
  planSeq++;   // a confirmation still loading belongs to the conversation being cleared
  document.querySelectorAll("#chat .turn:not(.welcome)").forEach((t) => t.remove());
  Object.assign(state, { text: "", choices: {}, op: null, lastCount: null, lastNoun: null, answered: null,
                         last: null, focus: null, firstReason: null });
  announce("New conversation.");
  $("request").focus();
});

// Changing a setting re-runs the current request from scratch, so each strategy can be compared.
function rerunWithSettings() {
  $("theta-value").textContent = Math.round(theta() * 100) + "%";
  if (state.busy) { state.settingsChanged = true; return; }   // re-run once the current reply lands
  state.settingsChanged = false;
  if (!state.text) return;
  const strategy = $("mode").selectedOptions[0].textContent;
  addNote("Study setting: " + strategy + ", ask below " + Math.round(theta() * 100) + "%. Reading “" + state.text + "” again.");
  Object.assign(state, { mode: chosenMode(), choices: {}, op: null, lastCount: null, answered: null, last: null, focus: null });
  runSearch();
}
$("mode").addEventListener("change", rerunWithSettings);
$("theta").addEventListener("change", rerunWithSettings);
$("theta").addEventListener("input", () => { $("theta-value").textContent = Math.round(theta() * 100) + "%"; });
