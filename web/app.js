// The page: send the request, then fill the fixed slots from the server's answer.
const $ = (id) => document.getElementById(id);
const NOTICE = { immediate: "now", "2w": "2 weeks", "1m": "1 month", "3m": "3 months" };

// What the recruiter has asked for so far. Edits are re-applied by the server to a fresh reading.
const state = { text: "", mode: "auto", choices: {}, op: null, lastCount: null, answered: null };

async function runSearch() {
  const res = await fetch("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: state.text, mode: state.mode, choices: state.choices, op: state.op }),
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

// Ask mode: one question, each option showing how many candidates it would give.
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
    reset.addEventListener("click", () => { state.choices = {}; state.op = null; state.answered = null; state.mode = "auto"; runSearch(); });
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
  const was = state.lastCount !== null && state.lastCount !== data.count ? " (was " + state.lastCount + ")" : "";
  $("count").textContent = data.count + (data.count === 1 ? " candidate" : " candidates") + was;
  state.lastCount = data.count;
  const body = $("results").querySelector("tbody");
  body.innerHTML = "";
  for (const c of data.results) {
    const row = el("tr");
    for (const v of [c.name, c.current_title, c.skills.join(", "), c.years_experience, c.city, c.work_mode, NOTICE[c.notice]]) {
      row.append(el("td", {}, String(v)));
    }
    body.append(row);
  }
  $("scope").textContent = data.searched + " " + data.not_searched;
  show("count"); show("results", data.count > 0); show("scope");
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
  } else {
    renderResults(data);
  }
}

$("ask-form").addEventListener("submit", (e) => {
  e.preventDefault();
  Object.assign(state, { text: $("request").value, mode: "auto", choices: {}, op: null, lastCount: null, answered: null });
  runSearch();
});
