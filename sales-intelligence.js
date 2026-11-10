/* Siddartha — dynamic Sales Intelligence view. All values come from the API. */
(() => {
  "use strict";
  const root = document.getElementById("sales-intelligence");
  if (!root) return;
  const el = id => document.getElementById(id);
  const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
  const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
  const colors = ["#2866e5", "#14b8b3", "#f1b84b", "#aa84ec", "#56b786", "#ed808a"];
  let lastData = null;

  const text = (id, value) => { const node = el(id); if (node) node.textContent = value; };
  const append = (tag, parent, content, className) => {
    const node = document.createElement(tag);
    if (content !== undefined && content !== null) node.textContent = String(content);
    if (className) node.className = className;
    parent.appendChild(node);
    return node;
  };
  const formatDate = iso => new Date(`${iso}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const pct = value => value === null || value === undefined ? "N/A" : `${value > 0 ? "+" : ""}${Number(value).toFixed(1)}%`;
  const setStatus = (value, isError = false) => {
    text("si-status", value);
    el("si-status").classList.toggle("si-error", isError);
  };

  function lineChart(points) {
    const holder = el("si-trend");
    holder.replaceChildren();
    if (!points.length) return;
    const W = 800, H = 280, L = 68, R = 20, T = 15, B = 42;
    const vals = points.map(p => Number(p.revenue) || 0);
    const high = Math.max(...vals, 0), low = Math.min(...vals, 0);
    const span = Math.max(1, high - low);
    const max = high + span * .15;
    const min = Math.min(0, low - span * .10);
    const y = val => T + (max - val) * (H - T - B) / Math.max(1, max - min);
    const x = i => L + i * (W - L - R) / Math.max(1, vals.length - 1);
    const svgNS = "http://www.w3.org/2000/svg";
    const svgNode = (tag, attrs, parent) => {
      const node = document.createElementNS(svgNS, tag);
      Object.entries(attrs || {}).forEach(([name,value]) => node.setAttribute(name, String(value)));
      (parent || svg).appendChild(node);
      return node;
    };
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Daily net sales trend over selected reporting period");
    holder.appendChild(svg);
    const defs = svgNode("defs");
    const gradient = svgNode("linearGradient", {id:"si-chart-fade",x1:0,y1:0,x2:0,y2:1}, defs);
    svgNode("stop", {offset:"0%", "stop-color":"#4c97f7", "stop-opacity":"0.35"}, gradient);
    svgNode("stop", {offset:"100%", "stop-color":"#4c97f7", "stop-opacity":"0.01"}, gradient);
    for (let i = 0; i <= 4; i++) {
      const value = min + (max - min) * i / 4;
      const yy = y(value);
      svgNode("line", {x1:L,y1:yy,x2:W-R,y2:yy,stroke:"#e6edf8","stroke-width":1});
      const label = svgNode("text", {x:L-10,y:yy+4,"text-anchor":"end",fill:"#7889a4","font-size":12});
      label.textContent = usd.format(value).replace(".00", "");
    }
    const ticks = Math.min(6, points.length - 1);
    for (let i = 0; i <= ticks; i++) {
      const index = Math.round(i * (points.length - 1) / Math.max(1,ticks));
      const label = svgNode("text", {x:x(index),y:H-15,"text-anchor":"middle",fill:"#7889a4","font-size":12});
      label.textContent = formatDate(points[index].date);
    }
    const poly = vals.map((value,index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
    const baseline = y(0).toFixed(1);
    const area = `${poly} L${x(vals.length-1).toFixed(1)},${baseline} L${x(0).toFixed(1)},${baseline} Z`;
    svgNode("path", {d:area, fill:"url(#si-chart-fade)"});
    svgNode("path", {d:poly, fill:"none", stroke:"#2866e5", "stroke-width":3.5,"stroke-linecap":"round","stroke-linejoin":"round"});
    const interval = Math.max(1, Math.ceil(points.length / 45));
    points.forEach((item,index) => {
      if (index % interval !== 0 && index !== points.length - 1) return;
      const dot = svgNode("circle", {cx:x(index), cy:y(vals[index]), r:3.2, fill:"#2866e5", stroke:"white", "stroke-width":1.5});
      svgNode("title", {}, dot).textContent = `${formatDate(item.date)}: ${usd.format(vals[index])}`;
    });
  }

  function categoryDonut(categories, netSales) {
    const positive = categories.filter(c => c.revenue > 0);
    const total = positive.reduce((sum,c) => sum + c.revenue, 0);
    const sorted = positive.slice(0,5);
    if (positive.length > 5) sorted.push({category:"Other categories", revenue:positive.slice(5).reduce((sum,c)=>sum+c.revenue,0)});
    const legend = el("si-category-legend");
    legend.replaceChildren();
    const chart = el("si-donut");
    let end = 0;
    const stops = [];
    sorted.forEach((item,index) => {
      const start = end;
      end = start + item.revenue / Math.max(0.01, total) * 100;
      stops.push(`${colors[index]} ${start.toFixed(2)}% ${end.toFixed(2)}%`);
      const row = append("li",legend);
      const dot = append("span",row,"","si-dot"); dot.style.backgroundColor = colors[index];
      append("span",row,item.category,"si-name");
      append("span",row,`${(item.revenue / total * 100).toFixed(1)}%`,"si-share");
    });
    chart.style.background = stops.length ? `conic-gradient(${stops.join(", ")})` : "#e9eff8";
    text("si-donut-total",usd.format(netSales));
    const losses = categories.filter(c => c.revenue < 0);
    text("si-category-note", losses.length
      ? `${losses.length} category/categories have negative net revenue (shown in data, excluded from donut proportions).`
      : "Shares are based on positive category net revenue; returns are included in each category total.");
  }

  function productsTable(products, sortedBy) {
    const table = el("si-products-body");
    table.replaceChildren();
    const rank = products.slice().sort((a,b) => sortedBy === "units"
      ? b.units_sold-a.units_sold || b.revenue-a.revenue
      : b.revenue-a.revenue || b.units_sold-a.units_sold);
    rank.slice(0,10).forEach(product => {
      const row = append("tr",table);
      append("td",row,product.product);
      append("td",row,product.category,"si-secondary");
      append("td",row,integer.format(product.units_sold));
      append("td",row,usd.format(product.revenue));
      append("td",row,product.revenue_share_pct === null ? "N/A" : `${product.revenue_share_pct.toFixed(1)}%`);
      const trend = append("td",row,pct(product.growth_pct));
      if (product.growth_pct !== null) trend.className = product.growth_pct >= 0 ? "si-positive" : "si-negative";
    });
  }

  function categoryTable(categories) {
    const table = el("si-category-body"); table.replaceChildren();
    categories.forEach(item => {
      const row = append("tr",table);
      append("td",row,item.category);
      append("td",row,integer.format(item.units_sold));
      append("td",row,usd.format(item.revenue));
      append("td",row,usd.format(item.previous_revenue));
      const growth = append("td",row,pct(item.growth_pct));
      if (item.growth_pct !== null) growth.className = item.growth_pct >= 0 ? "si-positive" : "si-negative";
    });
  }

  function weekdayBars(weekdays) {
    const target = el("si-weekday-bars"); target.replaceChildren();
    const limit = Math.max(1,...weekdays.map(d => Math.max(0, d.average_daily_revenue)));
    weekdays.forEach(day => {
      const row = append("div",target,null,"si-weekday-row");
      append("span",row,day.weekday,"si-weekday-name");
      const track = append("div",row,null,"si-weekday-track");
      const fill = append("span",track,null,"si-weekday-fill");
      fill.style.width = `${Math.max(0,day.average_daily_revenue)/limit*100}%`;
      append("span",row,usd.format(day.average_daily_revenue),"si-weekday-money");
    });
  }

  function renderTrend(data) {
    const mode = el("si-granularity").value;
    const trend = mode === "monthly"
      ? data.monthly_revenue.map(item => ({date:item.month+"-01", revenue:item.revenue}))
      : data.revenue_trend;
    lineChart(trend);
  }

  function render(data) {
    lastData = data;
    el("si-empty").hidden = !!data.has_data;
    el("si-content").hidden = !data.has_data;
    if (!data.has_data) {
      text("si-empty-period", `No sales found for the last ${data.period.days} days. Upload a report or try another period.`);
      return;
    }
    text("si-net-sales",usd.format(data.kpis.net_sales));
    text("si-units",integer.format(data.kpis.units_sold));
    text("si-products",integer.format(data.kpis.unique_products));
    text("si-growth",pct(data.kpis.growth_pct));
    const growthNode = el("si-growth");
    growthNode.className = data.kpis.growth_pct === null ? "" : data.kpis.growth_pct >= 0 ? "si-positive" : "si-negative";
    text("si-growth-note",`vs. prior ${data.period.days} days (${usd.format(data.kpis.previous_net_sales)})`);
    text("si-current-window",`${formatDate(data.period.start_date)} – ${formatDate(data.period.end_date)}`);
    renderTrend(data);
    categoryDonut(data.category_mix, data.kpis.net_sales);
    productsTable(data.product_performance,el("si-ranking").value);
    categoryTable(data.category_mix);
    weekdayBars(data.weekday_performance);
    const slow = el("si-slow-movers"); slow.replaceChildren();
    if (!data.slow_movers.length) append("li",slow,"No products with positive net units in this period.");
    data.slow_movers.forEach(p => {
      const li = append("li", slow);
      append("span",li,p.product);
      append("small",li,`${integer.format(p.units_sold)} units`);
    });
    const insights = el("si-insights"); insights.replaceChildren();
    data.insights.forEach(item => {
      const li = append("li",insights);
      append("strong",li,item.title);
      append("span",li,item.detail);
    });
    text("si-updated",data.last_upload_at
      ? `Last upload: ${new Date(data.last_upload_at).toLocaleString()}`
      : "No successful upload timestamp available");
  }

  async function refresh() {
    const token = localStorage.getItem("token");
    if (!token) { window.location.href = "signin.html"; return; }
    const days = el("si-range").value;
    setStatus("Loading sales intelligence…");
    try {
      const result = await fetch(`/api/dashboard/analytics?days=${encodeURIComponent(days)}`, {
        headers: {Authorization: `Bearer ${token}`}, cache:"no-store"
      });
      if (result.status === 401 || result.status === 403) throw new Error("Your session no longer has access. Sign in again.");
      if (!result.ok) throw new Error(`Analytics request failed (HTTP ${result.status}). Check that the database migration is applied.`);
      const data = await result.json();
      render(data);
      setStatus(`Showing actual CSV sales from ${formatDate(data.period.start_date)} to ${formatDate(data.period.end_date)}.`);
    } catch (error) {
      el("si-content").hidden = true;
      el("si-empty").hidden = true;
      setStatus(error.message,true);
    }
  }

  el("si-range").addEventListener("change",refresh);
  el("si-ranking").addEventListener("change",() => { if (lastData) productsTable(lastData.product_performance,el("si-ranking").value); });
  el("si-granularity").addEventListener("change",() => { if (lastData) renderTrend(lastData); });
  el("si-upload-shortcut").addEventListener("click",() => {
    const upload = document.querySelector(".upload-section");
    if (upload) upload.scrollIntoView({behavior:"smooth",block:"start"});
  });
  // Extra links keep existing Inventory/Reports/Account navigation intact.
  const nav = document.querySelector(".top-nav .nav-links");
  if (nav && !nav.querySelector('[href="#sales-intelligence"]')) {
    const link = document.createElement("a"); link.href = "#sales-intelligence";
    link.textContent = "Product Analytics"; nav.appendChild(link);
    const uploadLink = document.createElement("a"); uploadLink.href = "#sales-upload-area";
    uploadLink.textContent = "Upload Sales"; nav.appendChild(uploadLink);
  }
  const upload = document.querySelector(".upload-section");
  if (upload && !upload.id) upload.id = "sales-upload-area";
  refresh();
})();

/* Owner-only sales reconciliation status */
(() => {
  "use strict";

  const panel = document.getElementById("si-data-quality");
  const range = document.getElementById("si-range");

  if (!panel || !range) return;

  const get = id => document.getElementById(id);

  const badge = get("si-quality-status");
  const message = get("si-quality-message");

  const format = new Intl.NumberFormat("en-US");

  let latestRequest = 0;

  function setState(type, title, description) {
    badge.className = "si-quality-badge is-" + type;
    badge.textContent = title;
    message.textContent = description;
  }

  async function refreshQuality() {
    const token = localStorage.getItem("token");

    if (!token) {
      panel.hidden = true;
      return;
    }

    const request = ++latestRequest;
    const days = range.value;

    panel.hidden = false;

    setState(
      "loading",
      "Checking",
      "Comparing sales records with dashboard totals..."
    );

    try {
      const response = await fetch(
        "/api/business/data-quality?days="
          + encodeURIComponent(days),
        {
          headers: {
            Authorization: "Bearer " + token
          },
          cache: "no-store"
        }
      );

      if (request !== latestRequest) return;

      if (
        response.status === 401 ||
        response.status === 403
      ) {
        panel.hidden = true;
        return;
      }

      if (!response.ok) {
        throw new Error(
          "Database verification unavailable (HTTP "
          + response.status + ")."
        );
      }

      const data = await response.json();

      if (request !== latestRequest) return;

      const uploads = Number(data.uploads?.processed || 0);
      const records = Number(data.line_items?.count || 0);
      const mismatches = Number(data.mismatch_days || 0);

      get("si-quality-uploads").textContent =
        format.format(uploads);

      get("si-quality-records").textContent =
        format.format(records);

      get("si-quality-mismatches").textContent =
        format.format(mismatches);

      if (mismatches > 0) {
        const dates = (data.issues || [])
          .slice(0, 3)
          .map(issue => issue.date)
          .join(", ");

        setState(
          "warning",
          "Needs Review",
          mismatches + " day(s) have inconsistent totals."
            + (dates ? " Affected dates: " + dates : "")
        );

      } else if (records === 0) {
        setState(
          "empty",
          "No Sales Data",
          "No sales records found for this reporting period."
        );

      } else {
        setState(
          "good",
          "Totals Match",
          "Sales records match daily dashboard totals "
            + "for the last " + days + " days."
        );
      }

    } catch (error) {
      if (request !== latestRequest) return;

      setState(
        "error",
        "Unavailable",
        error.message || "Unable to verify database totals."
      );
    }
  }

  range.addEventListener("change", refreshQuality);

  document.addEventListener(
    "omnistat:upload-complete",
    refreshQuality
  );

  refreshQuality();
})();
