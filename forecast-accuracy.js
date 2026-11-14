/* DemandPulse: historical forecast replay, using the authorized ForecastStudio API. */
(() => {
  "use strict";
  const el = id => document.getElementById(id);
  const root = el("accuracy-panel");
  if (!root) return;
  const number = new Intl.NumberFormat("en-US", {maximumFractionDigits: 1});
  const money = new Intl.NumberFormat("en-US", {style: "currency", currency: "USD"});
  const status = el("accuracy-status");
  const select = el("accuracy-window");
  let newest = 0;

  function add(parent, tag, value) {
    const node = document.createElement(tag);
    if (value !== undefined) node.textContent = String(value);
    parent.appendChild(node);
    return node;
  }

  function drawDaily(records) {
    const host = el("accuracy-daily");
    host.replaceChildren();
    if (!records.length) {
      add(host, "p", "No historical comparison is available for this period.");
      return;
    }
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 760 230");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Forecasted and observed net units by completed day");
    const shape = (tag, attrs, content) => {
      const node = document.createElementNS(ns, tag);
      Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, value));
      if (content !== undefined) node.textContent = content;
      svg.appendChild(node);
      return node;
    };
    const values = records.flatMap(row => [row.actual_net_units, row.expected_units]);
    const minimum = Math.min(0, ...values);
    const maximum = Math.max(1, ...values);
    const x = i => 54 + i * 670 / Math.max(records.length - 1, 1);
    const y = value => 195 - ((value - minimum) / (maximum - minimum)) * 160;
    [0, 1, 2, 3].forEach(i => {
      const value = minimum + (maximum - minimum) * i / 3;
      shape("line", {x1: "54", x2: "728", y1: String(y(value)), y2: String(y(value)), stroke: "#324866"});
      shape("text", {x: "45", y: String(y(value) + 4), "text-anchor": "end", fill: "#99acc9", "font-size": "11"}, number.format(value));
    });
    for (const [field, color] of [["expected_units", "#69edda"], ["actual_net_units", "#a7a2ff"]]) {
      const d = records.map((item, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(item[field]).toFixed(1)}`).join(" ");
      shape("path", {d, stroke: color, "stroke-width": "3", fill: "none", "stroke-linecap": "round", "stroke-linejoin": "round"});
    }
    for (const i of new Set([0, Math.floor((records.length - 1) / 2), records.length - 1])) {
      shape("text", {x: String(x(i)), y: "219", "text-anchor": "middle", fill: "#a9bdd7", "font-size": "11"}, records[i].day.slice(5));
    }
    host.appendChild(svg);
  }

  async function load() {
    const token = localStorage.getItem("token");
    if (!token) {
      status.textContent = "Sign in as the business owner to view forecast accuracy.";
      root.querySelector(".accuracy-results").hidden = true;
      return;
    }
    const request = ++newest;
    status.textContent = "Replaying a historical forecast without using future sales…";
    root.querySelector(".accuracy-results").hidden = true;
    const query = new URLSearchParams({window: select.value});
    const category = el("forecast-category")?.value || "";
    const product = el("forecast-product")?.value || "";
    if (category) query.set("category", category);
    if (category && product) query.set("product", product);
    try {
      const response = await fetch("/api/forecast/accuracy?" + query, {
        headers: {Authorization: "Bearer " + token}, cache: "no-store"
      });
      if (request !== newest) return;
      if (response.status === 401 || response.status === 403) {
        status.textContent = "Only the authorized business owner can review forecast accuracy.";
        return;
      }
      if (!response.ok) throw Error("Accuracy endpoint returned HTTP " + response.status);
      const payload = await response.json();
      if (request !== newest) return;
      const report = payload.accuracy;
      if (report.status === "insufficient_history") {
        status.textContent = "Not enough earlier sales history to replay this period. No forecast comparison was invented.";
        return;
      }
      el("accuracy-predicted").textContent = number.format(report.expected_units);
      el("accuracy-observed").textContent = number.format(report.actual_net_units);
      el("accuracy-difference").textContent = (report.signed_unit_difference > 0 ? "+" : "") + number.format(report.signed_unit_difference);
      el("accuracy-error").textContent = report.unit_wape_pct === null ? "N/A" : report.unit_wape_pct + "%";
      el("accuracy-period").textContent = `${report.holdout_start} – ${report.holdout_end} · ${report.observed_activity_days}/${report.window_days} days with sales rows`;
      el("accuracy-revenue").textContent = `Net revenue: baseline ${money.format(report.expected_revenue)}, observed ${money.format(report.actual_net_revenue)} (difference ${money.format(report.signed_revenue_difference)}).`;
      const alerts = el("accuracy-alerts");
      alerts.replaceChildren();
      for (const item of report.alerts) {
        const entry = add(alerts, "li", item.message);
        entry.className = "accuracy-alert " + item.level;
      }
      if (!report.alerts.length) add(alerts, "li", "No threshold-based deviations were flagged for this replay.");
      drawDaily(report.daily);
      root.querySelector(".accuracy-results").hidden = false;
      status.textContent = report.status === "evaluated"
        ? "Historical replay complete. These predictions were reconstructed, not previously saved."
        : "Limited observed activity: confirm your POS uploads before interpreting the chart.";
    } catch (err) {
      if (request === newest) status.textContent = "Accuracy replay unavailable: " + (err.message || "Unexpected error");
    }
  }

  select.addEventListener("change", load);
  window.addEventListener("omnistat:forecast-filters-updated", load);
  load();
})();
