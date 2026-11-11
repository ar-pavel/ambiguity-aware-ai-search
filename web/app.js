// The page: a conversation. Each request or action adds the recruiter's turn and the assistant's reply.
// Only the latest assistant turn is live (its chips, question and buttons work); earlier turns are
// frozen copies, so a click can never apply to an old request. The server keeps no conversation:
// every reply comes from re-running the request with the recruiter's edits.
const $ = (id) => document.getElementById(id);

// What the recruiter has asked for so far. Edits are re-applied by the server to a fresh reading.
// last: the control just used (the server says what it changed). focus: the control to refocus after re-render.
// notice: the result of a write or undo, shown at the top of the next assistant turn.
const state = { text: "", mode: "auto", choices: {}, op: null, lastCount: null, lastNoun: null, answered: null,
                last: null, focus: null, firstReason: null, notice: null, busy: false };
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
  // Screen readers hear one short line, not the whole table.
  $("status").textContent = data.error ? data.error
    : data.mode.toUpperCase() + ". " + data.reason + (data.mode === "ask" ? "" : " " + results(data.count, data.noun) + ".");
  // Keep the recruiter's own turn in view above the reply, so it reads as an exchange.
  const before = turn.previousElementSibling;
  (before && before.classList.contains("user") ? before : turn).scrollIntoView({ block: "start" });
  return turn;
}

let thinking = null;   // "Reading your request…", shown only for a noticeable wait
function setBusy(on) {
  state.busy = on;
  $("chat").setAttribute("aria-busy", on ? "true" : "false");
  document.querySelectorAll("#ask-form button, .turn.live button, .turn.live select, .suggestion")
    .forEach((c) => { c.disabled = on; });
}

async function runSearch() {
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
  addAssistant(data);
  setBusy(false);
  restoreFocus();
}

// After a re-render, put focus back on the control the recruiter used (UX review fix 3).
// "question": a new request was sent, so focus its question if one is asked. Other re-runs (a study
// setting, an undo) leave focus where the recruiter is working.
function restoreFocus() {
  if (!state.focus) return;
  const turn = live();
  const target = !turn ? null : state.focus === "question" ? turn.querySelector("fieldset")
    : turn.querySelector('[data-slot="' + state.focus + '"]');
  if (target) target.focus();
  state.focus = null;
}

// ---- One assistant turn -------------------------------------------------------------------------

function assistantTurn(data, isLive) {
  const kind = data.error ? "error" : data.mode;   // the mode colours the turn's edge
  const turn = el("section", { class: "turn assistant " + (isLive ? "live" : "frozen") + " is-" + kind });
  turn.data = data;
  if (data.error) {
    turn.append(el("p", { class: "error" }, data.error));
    return turn;
  }
  if (isLive) remember(data);
  if (data._notice) turn.append(noticeLine(data._notice, isLive));
  turn.append(modeLine(data), whyBox(data.why));
  if (data.mode === "ask" && data.question) {
    turn.append(isLive ? questionCard(data.question) : askedLine(data.question));
    return turn;   // ask before searching: no results until the question is answered
  }
  if (data.mode === "show") {
    turn.append(isLive ? chipRow(data) : el("p", { class: "read-as" }, "Read as: " + data.read_as));
  } else {
    turn.append(el("p", { class: "read-as" }, "Read as: " + data.read_as));
    if (isLive) {
      const toShow = el("button", { type: "button", class: "link" }, "Edit this reading");
      toShow.addEventListener("click", () => act("Edit this reading", () => { state.mode = "show"; state.last = null; }));
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
  if (!state.last) state.firstReason = data.reason;
  if (state.last && state.firstReason && state.firstReason !== data.reason) data._first = state.firstReason;
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
  data._notice = state.notice;
  state.notice = null;
}

function modeLine(data) {
  const p = el("p", { class: "mode-line" });
  p.append(el("strong", { class: "mode mode-" + data.mode }, capital(data.mode)), el("span", { class: "reason" }, data.reason));
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
    const b = el("button", { type: "button", class: "option" }, capital(opt.label) + " → " + results(opt.count, opt.noun));
    b.addEventListener("click", () => act(capital(opt.label), () => {
      state.choices[q.slot] = i; state.mode = "show"; state.answered = q.slot;
      state.last = { slot: q.slot, answered: true }; state.focus = q.slot;
    }));
    options.append(b);
  });
  const best = q.options[q.default].label;
  const anyway = el("button", { type: "button", class: "link" }, "Search anyway with my best guess (" + best + ")");
  anyway.addEventListener("click", () => act("Search anyway (" + best + ")", () => { state.mode = "show"; }));
  card.append(options, anyway);
  return card;
}

function askedLine(q) {
  const p = el("p", { class: "asked" }, q.text + " ");
  p.append(el("span", { class: "muted" }, q.options.map((o) => capital(o.label) + " → " + results(o.count, o.noun)).join(" · ")));
  return p;
}

// Show: a chip for each assumption. Fixed parts are flat text; only choices look and act like controls
// (UX review fix 2): open choices are dropdowns marked ▾, the AND/OR operator is a one-click ⇄ toggle.
function chipRow(data) {
  const wrap = el("div");
  const row = el("div", { class: "chips", role: "group", "aria-label": "How I read your request" });
  data.chips.forEach((c) => row.append(chipFor(c)));
  const reset = el("button", { type: "button", class: "link" }, "Reset to my words");
  reset.addEventListener("click", () => act("Reset to my words", () => {
    Object.assign(state, { choices: {}, op: null, answered: null, last: null, mode: chosenMode(), focus: "question" });
  }));
  wrap.append(row, reset);
  return wrap;
}

function chipFor(chip) {
  if (chip.kind === "skill") return el("span", { class: "chip fixed" }, chip.text);
  if (chip.kind === "op") {
    const other = chip.value === "AND" ? "OR" : "AND";
    const b = el("button", { type: "button", class: "chip op" + (chip.guessed ? " guessed" : ""), "data-slot": "op",
                             title: chip.evidence, "aria-label": "Skills joined by " + chip.value + ". Switch to " + other + "." },
                 chip.value + " ⇄ " + other + (chip.guessed ? " (guessed)" : ""));
    b.addEventListener("click", () => act("Switch " + chip.value + " to " + other, () => {
      state.op = other; state.mode = "show"; state.last = { op: true }; state.focus = "op";
    }));
    return b;
  }
  if (!chip.options) return el("span", { class: "chip fixed" }, chip.text);
  const answered = chip.slot === state.answered ? " answered" : "";
  const wrap = el("label", { class: "chip choice" + (chip.guessed ? " guessed" : "") + answered, title: chip.evidence });
  const select = el("select", { "aria-label": "Change: " + chip.text, "data-slot": chip.slot });
  chip.options.forEach((label, i) => {
    const opt = el("option", { value: i }, label);
    if (i === chip.chosen) opt.selected = true;
    select.append(opt);
  });
  select.addEventListener("change", () => {
    const i = Number(select.value);
    act("Change to: " + chip.options[i], () => {
      state.choices[chip.slot] = i; state.mode = "show"; state.last = { slot: chip.slot }; state.focus = chip.slot;
    });
  });
  wrap.append(select, el("span", { class: "caret", "aria-hidden": "true" }, "▾"));
  if (chip.guessed) wrap.append(el("span", { class: "tag" }, "(guessed)"));
  return wrap;
}

// Every control in the live turn is a reply: say it in the recruiter's turn, change the state, re-run.
function act(said, change) {
  if (state.busy) return;
  addUser(said);
  change();
  runSearch();
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

// The result of a write or undo, at the top of the next turn. Only the latest one can be undone:
// undo always reverses the most recent write, so an older Undo button would undo the wrong thing.
function noticeLine(notice, isLive) {
  const n = el("p", { class: "notice" });
  n.append(el("span", {}, notice.text + " "));
  if (notice.canUndo && isLive) {
    const u = el("button", { type: "button", class: "link" }, "Undo");
    u.addEventListener("click", async () => {
      if (state.busy) return;
      addUser("Undo");
      let out;
      try { out = await post("/api/undo", {}); } catch (e) { out = { ok: false, error: "Could not reach the app." }; }
      state.notice = { text: out.ok ? out.done + "." : out.error, canUndo: false };
      state.last = null;
      runSearch();
    });
    n.append(u);
  }
  return n;
}

function fillPlan(plan) {
  const d = $("confirm");
  d.querySelector(".confirm-read-as").textContent = "Your search: " + (plan.read_as || "");
  d.querySelector(".confirm-summary").textContent = plan.summary || "";
  const list = d.querySelector(".confirm-changes");
  list.innerHTML = "";
  (plan.changes || []).forEach((c) => list.append(el("li", {}, c.label + (c.before ? "  (" + c.before + " → " + c.after + ")" : ""))));
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
  if (!plan) { addAssistant({ error: "Could not reach the app. Is python3 app.py still running?" }); return; }
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
  const { plan } = pending;
  const said = $("confirm-apply").textContent;
  const out = await post("/api/apply", { action: plan.action, job_id: plan.job_id, fingerprint: plan.fingerprint, search: searchPayload() });
  if (!out.ok) {  // refused: show what is true now, and let the recruiter confirm again
    if (out.plan) { pending.plan = Object.assign({ action: plan.action }, out.plan); fillPlan(pending.plan); }
    $("confirm").querySelector(".confirm-error").textContent = out.error;
    return;
  }
  $("confirm").close();
  addUser("Confirmed: " + said);
  state.notice = { text: out.done + ".", canUndo: true };
  state.last = null;
  runSearch();
});

// Esc and Cancel close the dialog without writing anything; focus goes back to the button that opened it.
$("confirm").addEventListener("close", () => {
  planSeq++;  // a job-picker reply still on its way must not reopen it
  const p = pending;
  $("job").innerHTML = '<option value="">Choose a job…</option>';
  if (p && p.trigger && document.body.contains(p.trigger)) p.trigger.focus();
});

// ---- Sending a request, examples, settings ------------------------------------------------------

function send(text) {
  text = text.trim();
  if (!text || state.busy) return;
  addUser(text);
  Object.assign(state, { text, mode: chosenMode(), choices: {}, op: null, lastCount: null,
                         answered: null, last: null, notice: null, focus: "question" });  // the question is next
  $("request").value = "";
  runSearch();
}

$("ask-form").addEventListener("submit", (e) => { e.preventDefault(); send($("request").value); });
document.querySelectorAll(".suggestion").forEach((b) => b.addEventListener("click", () => send(b.textContent)));

$("new-chat").addEventListener("click", () => {
  if (state.busy) return;
  document.querySelectorAll("#chat .turn:not(.welcome)").forEach((t) => t.remove());
  Object.assign(state, { text: "", choices: {}, op: null, lastCount: null, lastNoun: null, answered: null,
                         last: null, focus: null, firstReason: null, notice: null });
  $("status").textContent = "";
  $("request").focus();
});

// Changing a setting re-runs the current request from scratch, so each strategy can be compared.
function rerunWithSettings() {
  $("theta-value").textContent = Math.round(theta() * 100) + "%";
  if (!state.text || state.busy) return;
  const strategy = $("mode").selectedOptions[0].textContent;
  addNote("Study setting: " + strategy + ", ask below " + Math.round(theta() * 100) + "%. Reading “" + state.text + "” again.");
  Object.assign(state, { mode: chosenMode(), choices: {}, op: null, lastCount: null, answered: null, last: null, focus: null });
  runSearch();
}
$("mode").addEventListener("change", rerunWithSettings);
$("theta").addEventListener("change", rerunWithSettings);
$("theta").addEventListener("input", () => { $("theta-value").textContent = Math.round(theta() * 100) + "%"; });
