// The page: send the request, then fill the fixed slots from the server's answer.
const $ = (id) => document.getElementById(id);

// What the recruiter has asked for so far. Edits are re-applied by the server to a fresh reading.
const state = { text: "", mode: "auto", choices: {}, op: null, lastCount: null, lastNoun: null, answered: null };
const chosenMode = () => $("mode").value;          // the strategy picked in the settings bar
const theta = () => Number($("theta").value);       // the rule's overlap threshold

async function runSearch() {
  const res = await fetch("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: state.text, mode: state.mode, choices: state.choices, op: state.op, theta: theta() }),
  });
  render(await res.json());
}

function show(id, on = true) { $(id).hidden = !on; }

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text) node.textContent = text;
  return node;
}

function renderModeLine(data) {
  $("mode-line").innerHTML = "";
  $("mode-line").append(el("strong", { class: "mode mode-" + data.mode }, data.mode.toUpperCase()),
                        el("span", {}, " · " + data.reason));
  show("mode-line");
}

// A chip for each assumption. Open choices are dropdowns; the AND/OR operator is one-click.
function chipFor(chip) {
  if (chip.kind === "skill") return el("span", { class: "chip" }, chip.text);
  if (chip.kind === "op") {
    const b = el("button", { type: "button", class: "chip op" + (chip.guessed ? " guessed" : ""),
                             title: chip.evidence, "aria-label": "Skills joined by " + chip.value + ". Click to switch." },
                 chip.value + " ⇄" + (chip.guessed ? " (guessed)" : ""));
    b.addEventListener("click", () => { state.op = chip.value === "AND" ? "OR" : "AND"; state.mode = "show"; runSearch(); });
    return b;
  }
  if (!chip.options) return el("span", { class: "chip" }, chip.text);
  const answered = chip.slot === state.answered ? " answered" : "";
  const wrap = el("label", { class: "chip choice" + (chip.guessed ? " guessed" : "") + answered, title: chip.evidence });
  const select = el("select", { "aria-label": "Change: " + chip.text });
  chip.options.forEach((label, i) => {
    const opt = el("option", { value: i }, label);
    if (i === chip.chosen) opt.selected = true;
    select.append(opt);
  });
  select.addEventListener("change", () => { state.choices[chip.slot] = Number(select.value); state.mode = "show"; runSearch(); });
  wrap.append(select);
  if (chip.guessed) wrap.append(el("span", { class: "tag" }, "(guessed)"));
  return wrap;
}

// Ask mode: one question, each option showing how many results it would give.
function renderQuestion(q) {
  const card = el("div", { class: "question", role: "group", "aria-labelledby": "question-text" });
  card.append(el("p", { id: "question-text", class: "question-text" }, q.text));
  const options = el("div", { class: "options" });
  q.options.forEach((opt, i) => {
    const b = el("button", { type: "button", class: "option" }, opt.label + " (" + opt.count + ")");
    b.addEventListener("click", () => {
      state.choices[q.slot] = i; state.mode = "show"; state.answered = q.slot; runSearch();
    });
    options.append(b);
  });
  const anyway = el("button", { type: "button", class: "link" },
                    "Search anyway with my best guess (" + q.options[q.default].label + ")");
  anyway.addEventListener("click", () => { state.mode = "show"; runSearch(); });
  card.append(options, anyway);
  return card;
}

function renderInterpretation(data) {
  const slot = $("interpretation");
  slot.innerHTML = "";
  if (data.mode === "ask" && data.question) {
    slot.append(renderQuestion(data.question));
  } else if (data.mode === "show") {
    const row = el("div", { class: "chips", role: "group", "aria-label": "How I read your request" });
    data.chips.forEach((c) => row.append(chipFor(c)));
    const reset = el("button", { type: "button", class: "link" }, "Reset to my words");
    reset.addEventListener("click", () => { state.choices = {}; state.op = null; state.answered = null; state.mode = chosenMode(); runSearch(); });
    slot.append(row, reset);
  } else {
    slot.append(el("p", { class: "read-as" }, "Read as: " + data.read_as));
    const toShow = el("button", { type: "button", class: "link" }, "Show filters");
    toShow.addEventListener("click", () => { state.mode = "show"; runSearch(); });
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
  const ignored = data.dropped.length ? " Ignored: " + data.dropped.join("; ") + "." : "";
  $("scope").textContent = data.searched + " " + data.not_searched + " Interpreter: " + data.interpreter + "." + ignored;
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

async function openPlan(action, trigger, jobId) {
  const plan = await post("/api/plan", { action, job_id: jobId, search: searchPayload() });
  if (!plan.action) plan.action = action;
  pending = { plan, trigger };
  fillPlan(plan);
  const d = $("confirm");
  if (!d.open) { d.showModal(); $("confirm-cancel").focus(); }  // the safe choice has focus first
}

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

function render(data) {
  show("error", false);
  if (data.error) {
    $("error").textContent = data.error;
    show("error");
    return;
  }
  renderModeLine(data);
  renderInterpretation(data);
  if (data.mode === "ask") {  // ask before searching: no results until the question is answered
    ["count", "results", "scope"].forEach((id) => show(id, false));
    state.lastCount = null;
    show("actions", false);
  } else {
    renderResults(data);
    renderActions(data);
  }
}

$("ask-form").addEventListener("submit", (e) => {
  e.preventDefault();
  Object.assign(state, { text: $("request").value, mode: chosenMode(), choices: {}, op: null, lastCount: null, answered: null });
  show("notice", false);
  runSearch();
});

// Changing a setting re-runs the current request from scratch, so each strategy can be compared.
function rerunWithSettings() {
  $("theta-value").textContent = Math.round(theta() * 100) + "%";
  if (!state.text) return;
  Object.assign(state, { mode: chosenMode(), choices: {}, op: null, lastCount: null, answered: null });
  runSearch();
}
$("mode").addEventListener("change", rerunWithSettings);
$("theta").addEventListener("change", rerunWithSettings);
$("theta").addEventListener("input", () => { $("theta-value").textContent = Math.round(theta() * 100) + "%"; });
