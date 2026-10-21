"use strict";

const table = document.getElementById("results");
const body = table.tBodies[0];
const headers = Array.from(table.tHead.rows[0].cells);
const toggles = Array.from(document.querySelectorAll("button.toggle"));
const metric = document.getElementById("metric");
const preset = document.getElementById("preset");
const families = Array.from(document.querySelectorAll("button.family-toggle"));
const columns = new Map(toggles.map(button => [button.dataset.col, []]));
for (const cell of table.querySelectorAll("[data-col]")) columns.get(cell.dataset.col).push(cell);
const rows = () => Array.from(body.rows);
let sorted = { index: null, descending: false };

function highlight() {
  for (const row of rows()) {
    const candidates = Array.from(row.cells).filter(cell => {
      cell.classList.remove("best");
      return cell.dataset.status === "successful" && !cell.hidden;
    });
    // The fully observable MDP is an over-approximation of the POMDP,
    // even when its own result is exact. Compare its value with discretisation.
    // Display choices affect sorting, but not which POMDP bound is best.
    for (const families of [["cutoff", "clipping"], ["discretisation", "MDP"]]) {
      let group = candidates.filter(cell => families.includes(cell.dataset.family)
        && cell.dataset.quality !== "" && Number.isFinite(Number(cell.dataset.quality)));
      const under = families[0] === "cutoff";
      const exact = under ? group.filter(cell => cell.dataset.relation === "=") : [];
      if (exact.length) group = exact;
      const maximise = (row.dataset.direction === "max") === under;
      const values = group.map(cell => Number(cell.dataset.quality));
      const best = maximise ? Math.max(...values) : Math.min(...values);
      const tightest = exact.length ? exact : group.filter(cell => Number(cell.dataset.quality) === best);
      const timed = tightest.filter(cell => cell.dataset.runtime !== ""
        && Number.isFinite(Number(cell.dataset.runtime)));
      const fastest = Math.min(...timed.map(cell => Number(cell.dataset.runtime)));
      for (const cell of timed.length ? timed : tightest) {
        if (!timed.length || Number(cell.dataset.runtime) === fastest) cell.classList.add("best");
      }
    }
  }
}

function setColumn(button, visible) {
  button.classList.toggle("on", visible);
  button.setAttribute("aria-pressed", String(visible));
  for (const cell of columns.get(button.dataset.col)) cell.hidden = !visible;
}

function updateSelection() {
  const visible = toggles.filter(button => button.getAttribute("aria-pressed") === "true");
  document.getElementById("column-count").textContent = `${visible.length} / ${toggles.length} configurations`;
  for (const family of families) {
    const group = toggles.filter(button => button.dataset.family === family.dataset.family);
    const count = group.filter(button => button.getAttribute("aria-pressed") === "true").length;
    family.setAttribute("aria-pressed", count === group.length ? "true" : count === 0 ? "false" : "mixed");
  }
}

function sortTable(index, descending) {
  const header = headers[index];
  const numeric = header.dataset.kind !== "text";
  const value = cell => {
    if (header.dataset.kind === "run") {
      if (cell.dataset.status !== "successful") return null;
      const raw = metric.value === "bound" ? cell.dataset.bound
        : metric.value === "states" ? cell.dataset.states : cell.dataset.runtime;
      return raw !== "" && Number.isFinite(Number(raw)) ? Number(raw) : null;
    }
    if (!numeric) return cell.dataset.sort;
    const raw = cell.dataset.sort;
    return raw !== "" && Number.isFinite(Number(raw)) ? Number(raw) : null;
  };
  rows().sort((a, b) => {
    const x = value(a.cells[index]), y = value(b.cells[index]);
    // Failures and missing data stay after successful runs in both directions.
    if (x === null || y === null) return x === y ? 0 : x === null ? 1 : -1;
    const comparison = numeric ? x - y : x.localeCompare(y);
    return descending ? -comparison : comparison;
  }).forEach(row => body.appendChild(row));
  for (const cell of headers) cell.removeAttribute("aria-sort");
  header.setAttribute("aria-sort", descending ? "descending" : "ascending");
  sorted = { index, descending };
}

headers.forEach((header, index) => header.querySelector("button").addEventListener("click", () => {
  sortTable(index, sorted.index === index ? !sorted.descending : false);
}));
for (const button of toggles) button.addEventListener("click", () => {
  setColumn(button, button.getAttribute("aria-pressed") !== "true");
  preset.value = "custom";
  updateSelection();
  highlight();
});
for (const family of families) family.addEventListener("click", () => {
  const visible = family.getAttribute("aria-pressed") !== "true";
  for (const button of toggles.filter(button => button.dataset.family === family.dataset.family)) {
    setColumn(button, visible);
  }
  preset.value = "custom";
  updateSelection();
  highlight();
});
for (const button of document.querySelectorAll("[data-all]")) button.addEventListener("click", () => {
  for (const toggle of toggles) setColumn(toggle, button.dataset.all === "true");
  preset.value = button.dataset.all === "true" ? "all" : "custom";
  updateSelection();
  highlight();
});
preset.addEventListener("change", () => {
  for (const toggle of toggles) {
    setColumn(toggle, preset.value === "all" || toggle.dataset.compact === "true");
  }
  updateSelection();
  highlight();
});
metric.addEventListener("change", () => {
  document.body.dataset.metric = metric.value;
  if (sorted.index !== null) sortTable(sorted.index, sorted.descending);
  highlight();
});
const filter = document.getElementById("filter");
function filterRows() {
  const terms = filter.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
  for (const row of rows()) row.hidden = !terms.every(term => row.dataset.search.includes(term));
  document.getElementById("row-count").textContent = `${rows().filter(row => !row.hidden).length} / ${rows().length} benchmarks`;
}
filter.addEventListener("input", filterRows);
document.body.dataset.metric = metric.value;
updateSelection();
filterRows();
highlight();
