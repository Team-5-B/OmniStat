(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const dollars = new Intl.NumberFormat("en-US", {style: "currency", currency: "USD"});
  const numeric = new Intl.NumberFormat("en-US", {maximumFractionDigits: 1});
  const {search} = window.location;
  const params = new URLSearchParams(search);
  let horizon = ["week", "month", "quarter", "year"].includes(params.get("horizon")) ? params.get("horizon") : "week";
  let catalogue = [];
  let requestID = 0;
  let current = null;

  const add = (parent, tag, value, className) => {
    const el = document.createElement(tag);
    if (value != null) el.textContent = String(value);
    if (className) el.className = className;
    parent.appendChild(el);
    return el;
  };
  const showStatus = text => { $("forecast-status").textContent = text; };
  const token = () => localStorage.getItem("token");

  function selectOptions(select, values, placeholder, selected) {
    select.replaceChildren();
    const blank = add(select, "option", placeholder);
    blank.value = "";
    values.forEach(value => {
      const opt = add(select, "option", value);
      opt.value = value;
    });
    if (selected && values.includes(selected)) select.value = selected;
  }

  function updateCatalog() {
    const selectedCategory = $("forecast-category").value;
    const selectedProduct = $("forecast-product").value;
    const categories = [...new Set(catalogue.map(p => p.category))].sort();
    selectOptions($("forecast-category"), categories, "All categories", selectedCategory);
    const products = [...new Set(catalogue.filter(p => !selectedCategory || p.category === selectedCategory).map(p => p.product))].sort();
    selectOptions($("forecast-product"), products, "All products", selectedProduct);
  }

  function drawChart(data) {
    const host = $("forecast-chart");
    host.replaceChildren();
    let points = data.daily;
    if (data.days > 30) {
      points = (data.days > 100 ? data.month_buckets : data.week_buckets).map(x => ({date: x.period, units: x.units}));
    }
    if (!points.length) { add(host, "p", "No forecast data available."); return; }
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 760 280");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", `Forecasted net units over ${data.days} days`);
    const node = (tag, attrs, content, parent=svg) => {
      const el = document.createElementNS(ns, tag);
      Object.entries(attrs || {}).forEach(([k, v]) => el.setAttribute(k, String(v)));
      if (content != null) el.textContent = content;
      parent.appendChild(el);
      return el;
    };
    const defs = node("defs");
    const grad = node("linearGradient", {id: "forecast-gradient", x1: "0", y1: "0", x2: "0", y2: "1"}, null, defs);
    node("stop", {offset: "0%", "stop-color": "#5cebdc", "stop-opacity": ".35"}, null, grad);
    node("stop", {offset: "100%", "stop-color": "#5cebdc", "stop-opacity": "0"}, null, grad);
    const values = points.map(x => Number(x.units || 0));
    const max = Math.max(1, ...values) * 1.12;
    const x = i => 55 + i * (676 / Math.max(1, values.length - 1));
    const y = v => 229 - v / max * 196;
    for (let j=0;j<=4;j++) {
      const yy = y(max * j/4);
      node("line", {x1:55,y1:yy,x2:733,y2:yy,stroke:"#253e5a","stroke-width":1});
      node("text", {x:46,y:yy+4,fill:"#8dadd0","text-anchor":"end","font-size":11}, numeric.format(max*j/4));
    }
    const path = values.map((v,i) => `${i?"L":"M"} ${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
    const area = `${path} L ${x(values.length-1)} 229 L 55 229 Z`;
    node("path", {d:area,fill:"url(#forecast-gradient)"});
    node("path", {d:path,fill:"none",stroke:"#68edda","stroke-width":3,"stroke-linecap":"round","stroke-linejoin":"round"});
    points.forEach((p,i) => {
      if (values.length <= 35 || i % Math.ceil(values.length / 16) === 0) {
        node("circle", {cx:x(i),cy:y(values[i]),r:3.3,fill:"#a6fff0",stroke:"#183b4e","stroke-width":1});
      }
    });
    const indices = [...new Set([0,Math.floor((points.length-1)/2),points.length-1])];
    indices.forEach(i => node("text", {x:x(i),y:260,fill:"#8ea9c8","text-anchor":"middle","font-size":11}, String(points[i].date).slice(-12)));
    host.appendChild(svg);
  }

  function drawBuckets(data) {
    const body = $("forecast-buckets");
    body.replaceChildren();
    const buckets = data.days > 90 ? data.quarter_buckets : (data.days > 30 ? data.month_buckets : data.week_buckets);
    buckets.forEach(b => {
      const row = add(body, "tr");
      add(row, "td", b.period);
      add(row, "td", numeric.format(b.units));
      add(row, "td", dollars.format(b.revenue));
    });
    if (!buckets.length) { const row=add(body,"tr"); const cell=add(row,"td","No future periods available.");cell.colSpan=3; }
  }

  function drawProducts(products) {
    const body = $("forecast-products");
    body.replaceChildren();
    products.forEach(p => {
      const row = add(body,"tr");
      const cell=add(row,"td");
      add(cell,"strong",p.product);
      add(cell,"small",p.category);
      add(row,"td",p.expected_net_units == null ? "Not enough history" : numeric.format(p.expected_net_units));
      add(row,"td",p.unit_planning_range_high == null ? "—" : numeric.format(p.unit_planning_range_high));
      add(row,"td",p.expected_net_revenue == null ? "—" : dollars.format(p.expected_net_revenue));
    });
    if (!products.length) { const row=add(body,"tr"); const cell=add(row,"td","No products in the selected scope.");cell.colSpan=4; }
  }

  function render(data) {
    const f = data.forecast;
    current = data;
    $("forecast-ready").hidden = false;
    $("kpi-units").textContent = f.totals ? numeric.format(f.totals.expected_net_units) : "N/A";
    $("kpi-revenue").textContent = f.totals ? dollars.format(f.totals.expected_net_revenue) : "N/A";
    $("kpi-range").textContent = f.totals ? `${numeric.format(f.totals.unit_planning_range_low)} – ${numeric.format(f.totals.unit_planning_range_high)}` : "N/A";
    $("kpi-error").textContent = f.backtest && f.backtest.wape_pct !== null ? `${f.backtest.wape_pct}%` : "N/A";
    $("chart-model").textContent = f.method ? f.method.replace("_"," ") : "History required";
    $("evidence-version").textContent = f.model_version;
    $("evidence-span").textContent = `${f.history_span_days} calendar days`;
    $("evidence-active").textContent = String(f.active_sales_days);
    $("evidence-upload").textContent = data.source_last_processed_at ? new Date(data.source_last_processed_at).toLocaleString() : "Unknown";
    const warnings=$("forecast-warnings"); warnings.replaceChildren();
    f.warnings.forEach(w => add(warnings,"li",w));
    const alertHost=$("forecast-alerts"); alertHost.replaceChildren();
    data.alerts.forEach(a => {
      const box=add(alertHost,"div",null,`alert ${a.level === "warning" ? "warning" : ""}`);
      add(box,"strong",a.type.replaceAll("_"," ").toUpperCase());
      add(box,"span",a.message);
    });
    drawChart(f);
    drawBuckets(f);
    drawProducts(data.products);
    if (f.status === "ready") {
      showStatus(`Outlook ready · ${f.forecast_start} to ${f.forecast_end} · ${f.confidence.replaceAll("_", " ")}`);
    } else {
      showStatus(`Insufficient history: ${f.history_span_days} calendar days / ${f.active_sales_days} active days; ${f.minimum_history_days} / ${f.minimum_active_days} needed for this horizon.`);
    }
  }

  async function load() {
    const bearer=token();
    if (!bearer) { window.location.href="signin.html"; return; }
    const thisRequest = ++requestID;
    showStatus("Calculating forecasts from your authorized business history…");
    $("forecast-ready").hidden=true;
    $("reorder-result").textContent="Choose a product and supply stock inputs to plan an order.";
    const query = new URLSearchParams({horizon,top:"30"});
    const category=$("forecast-category").value;
    const product=$("forecast-product").value;
    if (category) query.set("category",category);
    if (category && product) query.set("product",product);
    try {
      const result=await fetch("/api/forecast/overview?"+query,{headers:{Authorization:"Bearer "+bearer},cache:"no-store"});
      if (thisRequest!==requestID) return;
      if (result.status===401 || result.status===403) { showStatus("Owner access required; sign in with the authorized business owner account.");return; }
      if (!result.ok) throw Error(`Forecast API returned HTTP ${result.status}`);
      const payload=await result.json();
      if (thisRequest!==requestID) return;
      if (!category && !product) catalogue=payload.products;
      updateCatalog();
      render(payload);
      window.dispatchEvent(new Event("omnistat:forecast-filters-updated"));
      const state=new URLSearchParams({horizon});
      if (category) state.set("category",category);
      if (product) state.set("product",product);
      history.replaceState(null,"","forecast-studio.html?"+state);
    } catch(err) {
      if(thisRequest!==requestID) return;
      showStatus("Forecast unavailable: "+(err.message || "Unexpected network error"));
    }
  }

  document.querySelectorAll(".horizon").forEach(button=>button.addEventListener("click",()=>{
    horizon=button.dataset.horizon;
    document.querySelectorAll(".horizon").forEach(b=>{
      const selected=b===button;
      b.classList.toggle("is-active",selected);
      b.setAttribute("aria-pressed",String(selected));
    });
    load();
  }));
  $("forecast-category").addEventListener("change",()=>{
    updateCatalog();
    $("forecast-product").value="";
    load();
  });
  $("forecast-product").addEventListener("change",load);

  $("reorder-form").addEventListener("submit", async evt=>{
    evt.preventDefault();
    const category=$("forecast-category").value;
    const product=$("forecast-product").value;
    if (!category || !product) { $("reorder-result").textContent="Select a specific category and product before calculating purchases."; return; }
    const submit=$("reorder-submit");
    submit.disabled=true;
    $("reorder-result").textContent="Calculating protected-demand scenario…";
    const payload={
      category,product,
      on_hand:Number($("reorder-stock").value),
      lead_time_days:Number($("reorder-lead").value),
      safety_days:Number($("reorder-safety").value),
      pack_size:Number($("reorder-pack").value)
    };
    try {
      const response=await fetch("/api/forecast/reorder-scenario",{
        method:"POST",headers:{Authorization:"Bearer "+token(),"Content-Type":"application/json"},
        body:JSON.stringify(payload)
      });
      const answer=await response.json();
      if(!response.ok) throw Error(typeof answer.detail === "string" ? answer.detail : `Scenario unavailable (HTTP ${response.status})`);
      const r=answer.scenario;
      const result=$("reorder-result");
      result.replaceChildren();
      if(r.status !== "scenario_only") { add(result,"p","Insufficient history to calculate a product reorder scenario.");return; }
      add(result,"small","HUMAN-REVIEW PLANNING ESTIMATE");
      add(result,"strong",`${numeric.format(r.suggested_product_units)} product units`);
      add(result,"p",`${numeric.format(r.suggested_packs)} pack(s), over ${r.planning_days} days; predicted ${numeric.format(r.forecast_units_during_protection)} net units, with ${numeric.format(r.on_hand_units_supplied)} on hand.`);
      add(result,"small","No inventory modified, no supplier order placed. This is not an ingredient-level purchase plan.");
    } catch(err){$("reorder-result").textContent=err.message;}
    finally{submit.disabled=false;}
  });

  const selected = document.querySelector(`.horizon[data-horizon="${horizon}"]`);
  if(selected) selected.click(); else load();
})();
