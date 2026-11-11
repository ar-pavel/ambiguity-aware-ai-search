// The page: send the request, then fill the fixed slots from the server's answer.
const $ = (id) => document.getElementById(id);

// What the recruiter has asked for so far. Edits are re-applied by the server to a fresh reading.
// last: the control just used (the server says what it changed). focus: the control to refocus after re-render.
const state = { text: "", mode: "auto", choices: {}, op: null, lastCount: null, lastNoun: null, answered: null,
                last: null, focus: null, firstReason: null };
const chosenMode = () => $("mode").value;          // the strategy picked in the settings bar
const theta = () => Number($("theta").value);       // the rule's overlap threshold

// While waiting (a live model can take seconds): say so, and stop further clicks (UX review fix 4).
function setBusy(on) {
  document.querySelector("main").setAttribute("aria-busy", on ? "true" : "false");
  document.querySelectorAll("#ask-form button, #interpretation button, #interpretation select, #actions button")
    .forEach((c) => { c.disabled = on; });
}

async function runSearch() {
  planSeq++;  // a confirmation for the old results must not open over the new ones
  setBusy(true);
  const slow = setTimeout(() => {   // only for a noticeable wait, so fast answers don't flicker
    $("mode-line").textContent = "Reading your request…";
    show("mode-line");
  }, 300);
  try {
    const res = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: state.text, mode: state.mode, choices: state.choices, op: state.op,
                             theta: theta(), last: state.last }),
    });
    render(await res.json());
  } catch (e) {
    render({ error: "Could not reach the app. Is python3 app.py still running?" });
  } finally {
    clearTimeout(slow);
    setBusy(false);
    restoreFocus();
  }
}

// After a re-render, put focus back on the control the recruiter used (UX review fix 3).
// "question": a new request was sent, so focus its question if one is asked. Other re-runs (a study
// setting, an undo) leave focus where the recruiter is working.
function restoreFocus() {
  if (!state.focus) return;
  const target = state.focus === "question" ? document.querySelector("#interpretation fieldset")
    : document.querySelector('#interpretation [data-slot="' + state.focus + '"]');
  if (target) target.focus();
  state.focus = null;
}

function show(id, on = true) { $(id).hidden = !on; }

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text) node.textContent = text;
  return node;
}

// One assistant turn: the badge and what happened. After an edit, the first reason stays below, muted.
function renderModeLine(data) {
  if (!state.last) state.firstReason = data.reason;
  $("mode-line").innerHTML = "";
  $("mode-line").append(el("strong", { class: "mode mode-" + data.mode }, data.mode.toUpperCase()),
                        el("span", {}, " · " + data.reason));
  if (state.last && state.firstReason && state.firstReason !== data.reason) {
    $("mode-line").append(el("span", { class: "first-reason" }, "At first: " + state.firstReason));
  }
  show("mode-line");
}

// A chip for each assumption. Fixed parts are flat text; only choices look and act like controls
// (UX review fix 2): open choices are dropdowns marked ▾, the AND/OR operator is a one-click ⇄ toggle.
function chipFor(chip) {
  if (chip.kind === "skill") return el("span", { class: "chip fixed" }, chip.text);
  if (chip.kind === "op") {
    const other = chip.value === "AND" ? "OR" : "AND";
    const b = el("button", { type: "button", class: "chip op" + (chip.guessed ? " guessed" : ""), "data-slot": "op",
                             title: chip.evidence, "aria-label": "Skills joined by " + chip.value + ". Switch to " + other + "." },
                 chip.value + " ⇄ " + other + (chip.guessed ? " (guessed)" : ""));
    b.addEventListener("click", () => {
      state.op = other; state.mode = "show"; state.last = { op: true }; state.focus = "op"; runSearch();
    });
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
    state.choices[chip.slot] = Number(select.value); state.mode = "show";
    state.last = { slot: chip.slot }; state.focus = chip.slot; runSearch();
  });
  wrap.append(select, el("span", { class: "caret", "aria-hidden": "true" }, "▾"));
  if (chip.guessed) wrap.append(el("span", { class: "tag" }, "(guessed)"));
  return wrap;
}

// Ask mode: one question, each option saying what it would give (UX review fix 5).
const capital = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const results = (n, noun) => n + " " + noun + (n === 1 ? "" : "s");

function renderQuestion(q) {
  const card = el("fieldset", { class: "question", tabindex: "-1" });
  card.append(el("legend", { class: "question-text" }, q.text));
  const options = el("div", { class: "options" });
  q.options.forEach((opt, i) => {
    const b = el("button", { type: "button", class: "option" }, capital(opt.label) + " → " + results(opt.count, opt.noun));
    b.addEventListener("click", () => {
      state.choices[q.slot] = i; state.mode = "show"; state.answered = q.slot;
      state.last = { slot: q.slot, answered: true }; state.focus = q.slot; runSearch();
    });
    options.append(b);
  });
  const anyway = el("button", { type: "button", class: "link" },
                    "Search anyway with my best guess (" + q.options[q.default].label + ")");
  anyway.addEventListener("click", () => { state.mode = "show"; state.focus = null; runSearch(); });
  card.append(options, anyway);
  return card;
}

function renderInterpretation(data) {
  const slot = $("interpretation");
  slot.innerHTML = "";
  if (data.mode === "ask" && data.question) {
    const card = renderQuestion(data.question);
    slot.append(card);
    show("interpretation");
    return;
  } else if (data.mode === "show") {
    const row = el("div", { class: "chips", role: "group", "aria-label": "How I read your request" });
    data.chips.forEach((c) => row.append(chipFor(c)));
    const reset = el("button", { type: "button", class: "link" }, "Reset to my words");
    reset.addEventListener("click", () => {
      Object.assign(state, { choices: {}, op: null, answered: null, last: null, mode: chosenMode(), focus: "question" });
      runSearch();
    });
    slot.append(row, reset);
  } else {
    slot.append(el("p", { class: "read-as" }, "Read as: " + data.read_as));
    const toShow = el("button", { type: "button", class: "link" }, "Edit this reading");
    toShow.addEventListener("click", () => { state.mode = "show"; state.last = null; runSearch(); });
    slot.append(toShow);
  }
  show("interpretation");
}

function renderResults(data) {
  // "(was N)" only compares like with like: not 5 candidates with 1 job.
  const was = state.lastCount !== null && state.lastNoun === data.noun && state.lastCount !== data.count
    ? " (was " + state.lastCount + ")" : "";
  $("count").textContent = data.count + " " + data.noun + (data.count === 1 ? "" : "s") + was;
  state.lastCount = data.count;
  state.lastNoun = data.noun;
  // The server sends headers and rows as plain text, for candidates or jobs alike.
  const head = $("results").querySelector("thead");
  const body = $("results").querySelector("tbody");
  head.innerHTML = ""; body.innerHTML = "";
  const hr = el("tr");
  data.table.headers.forEach((h) => hr.append(el("th", { scope: "col" }, h)));
  head.append(hr);
  for (const cells of data.table.rows) {
    const row = el("tr");
    cells.forEach((v) => row.append(el("td", {}, v)));
    body.append(row);
  }
  // Above the table, ignored words first: a dropped word is a silent change otherwise (UX review fix 7).
  $("ignored").textContent = data.dropped.length ? "Ignored: " + data.dropped.join("; ") + "." : "";
  show("ignored", data.dropped.length > 0);
  $("scope").textContent = data.searched + " · " + data.not_searched + " · Interpreter: " + data.interpreter + ".";
  show("count"); show("results", data.count > 0); show("scope");
}

// ---- Write actions: plan -> confirm in a dialog -> apply -> undo -------------------------------

const searchPayload = () => ({ text: state.text, mode: state.mode, choices: state.choices, op: state.op, theta: theta() });
let pending = null;   // the plan shown in the dialog, and the button that opened it

async function post(path, body) {
  const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return res.json();
}

function renderActions(data) {
  const bar = $("actions");
  bar.innerHTML = "";
  const action = data.target === "jobs" ? ["close", "Close these jobs…"] : ["shortlist", "Shortlist for a job…"];
  const b = el("button", { type: "button", class: "secondary" }, action[1]);
  b.addEventListener("click", () => openPlan(action[0], b, null));
  bar.append(b);
  show("actions", data.mode !== "ask" && data.count > 0);
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
  if (!plan) { setNotice("Could not reach the app. Is python3 app.py still running?", false); return; }
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
  const out = await post("/api/apply", { action: plan.action, job_id: plan.job_id, fingerprint: plan.fingerprint, search: searchPayload() });
  if (!out.ok) {  // refused: show what is true now, and let the recruiter confirm again
    if (out.plan) { pending.plan = Object.assign({ action: plan.action }, out.plan); fillPlan(pending.plan); }
    $("confirm").querySelector(".confirm-error").textContent = out.error;
    return;
  }
  $("confirm").close();
  setNotice(out.done + ".", true);
  runSearch();
});

// Esc and Cancel close the dialog without writing anything; focus goes back to the button that opened it.
$("confirm").addEventListener("close", () => {
  planSeq++;  // a job-picker reply still on its way must not reopen it
  const p = pending;
  $("job").innerHTML = '<option value="">Choose a job…</option>';
  if (p && p.trigger && document.body.contains(p.trigger)) p.trigger.focus();
});

function setNotice(text, canUndo) {
  const n = $("notice");
  n.innerHTML = "";
  n.append(el("span", {}, text + " "));
  if (canUndo) {
    const u = el("button", { type: "button", class: "link" }, "Undo");
    u.addEventListener("click", async () => {
      const out = await post("/api/undo", {});
      setNotice(out.ok ? out.done + "." : out.error, false);
      runSearch();
      $("notice").focus();
    });
    n.append(u);
  }
  n.tabIndex = -1;
  show("notice");
}

// The rule's comparison, row by row. Stays open or closed as the recruiter left it.
function renderWhy(why) {
  const body = $("why").querySelector(".why-body");
  body.innerHTML = "";
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
    body.append(t);
  }
  why.notes.forEach((n) => body.append(el("p", { class: "why-note" }, n)));
  show("why");
}

function render(data) {
  show("error", false);
  if (data.error) {
    $("error").textContent = data.error;
    show("error");
    show("why", false);
    return;
  }
  renderModeLine(data);
  renderWhy(data.why);
  renderInterpretation(data);
  if (data.mode === "ask") {  // ask before searching: no results until the question is answered
    ["count", "results", "scope", "ignored"].forEach((id) => show(id, false));
    state.lastCount = null;
    show("actions", false);
  } else {
    renderResults(data);
    renderActions(data);
  }
}

$("ask-form").addEventListener("submit", (e) => {
  e.preventDefault();
  Object.assign(state, { text: $("request").value, mode: chosenMode(), choices: {}, op: null, lastCount: null,
                         answered: null, last: null, focus: "question" });  // the question is the next thing to deal with
  show("notice", false);
  runSearch();
});

// Changing a setting re-runs the current request from scratch, so each strategy can be compared.
function rerunWithSettings() {
  $("theta-value").textContent = Math.round(theta() * 100) + "%";
  if (!state.text) return;
  Object.assign(state, { mode: chosenMode(), choices: {}, op: null, lastCount: null, answered: null, last: null, focus: null });
  runSearch();
}
$("mode").addEventListener("change", rerunWithSettings);
$("theta").addEventListener("change", rerunWithSettings);
$("theta").addEventListener("input", () => { $("theta-value").textContent = Math.round(theta() * 100) + "%"; });
