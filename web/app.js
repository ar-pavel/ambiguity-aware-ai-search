// The page: send the request, then fill the fixed slots from the server's answer.
const $ = (id) => document.getElementById(id);
const NOTICE = { immediate: "now", "2w": "2 weeks", "1m": "1 month", "3m": "3 months" };

async function runSearch(body) {
  const res = await fetch("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

function show(id, on = true) { $(id).hidden = !on; }

function renderModeLine(data) {
  $("mode-line").innerHTML = "";
  const badge = document.createElement("strong");
  badge.className = "mode mode-" + data.mode;
  badge.textContent = data.mode.toUpperCase();
  const why = document.createElement("span");
  why.textContent = " · " + data.reason;
  $("mode-line").append(badge, why);
  show("mode-line");
}

function renderInterpretation(data) {
  const slot = $("interpretation");
  slot.innerHTML = "";
  const line = document.createElement("p");
  line.className = "read-as";
  line.textContent = "Read as: " + data.read_as;
  slot.append(line);
  show("interpretation");
}

function renderResults(data) {
  $("count").textContent = data.count + (data.count === 1 ? " candidate" : " candidates");
  const body = $("results").querySelector("tbody");
  body.innerHTML = "";
  for (const c of data.results) {
    const row = document.createElement("tr");
    for (const v of [c.name, c.current_title, c.skills.join(", "), c.years_experience,
                     c.city, c.work_mode, NOTICE[c.notice]]) {
      const cell = document.createElement("td");
      cell.textContent = v;
      row.append(cell);
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
  renderResults(data);
}

$("ask-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  render(await runSearch({ text: $("request").value }));
});
