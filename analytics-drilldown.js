(() => {
  "use strict";

  const get = id => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const level = document.body.dataset.analyticsLevel;

  const category = params.get("category") || "";
  const product = params.get("product") || "";

  const money = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD"
  });

  const number = new Intl.NumberFormat("en-US");

  const percent = value =>
    value == null
      ? "N/A"
      : `${value > 0 ? "+" : ""}${Number(value).toFixed(1)}%`;

  const daysInput = get("analytics-days");

  if (["7", "30", "90"].includes(params.get("days"))) {
    daysInput.value = params.get("days");
  }

  if (!category || (level === "product" && !product)) {
    get("analytics-status").textContent =
      "Missing category or product. Return to the dashboard.";
    return;
  }

  const back = get("analytics-back");

  if (back) {
    back.textContent = category;

    back.href = "category-analytics.html?" +
      new URLSearchParams({
        category,
        days: daysInput.value
      });
  }

  function add(parent, tag, content) {
    const element = document.createElement(tag);

    if (content !== undefined) {
      element.textContent = String(content);
    }

    parent.appendChild(element);
    return element;
  }

  function renderTrend(points) {
    const target = get("analytics-chart");
    target.replaceChildren();

    if (!points.length) return;

    const values = points.map(item => Number(item.revenue) || 0);

    const minimum = Math.min(0, ...values);
    const maximum = Math.max(1, ...values);

    const width = 720;
    const height = 230;

    const x = index =>
      60 + index * 630 / Math.max(1, points.length - 1);

    const y = value =>
      20 + (maximum - value) * 160 /
        Math.max(1, maximum - minimum);

    const namespace = "http://www.w3.org/2000/svg";

    const svg = document.createElementNS(namespace, "svg");

    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Daily net sales trend");

    const draw = (tag, attributes, content) => {
      const element = document.createElementNS(namespace, tag);

      Object.entries(attributes).forEach(([key, value]) => {
        element.setAttribute(key, value);
      });

      if (content !== undefined) {
        element.textContent = content;
      }

      svg.appendChild(element);
    };

    for (let index = 0; index < 4; index++) {
      const value =
        minimum + (maximum - minimum) * index / 3;

      const position = y(value);

      draw("line", {
        x1: 60,
        x2: 690,
        y1: position,
        y2: position,
        stroke: "#dce7f4"
      });

      draw("text", {
        x: 53,
        y: position + 4,
        "text-anchor": "end",
        fill: "#71839b",
        "font-size": 11
      }, money.format(value));
    }

    const path = values.map((value, index) =>
      `${index ? "L" : "M"}${x(index)} ${y(value)}`
    ).join(" ");

    draw("path", {
      d: path,
      fill: "none",
      stroke: "#2868d5",
      "stroke-width": 3
    });

    const labels = [
      0,
      Math.floor((points.length - 1) / 2),
      points.length - 1
    ];

    labels.forEach(index => {
      draw("text", {
        x: x(index),
        y: 215,
        "text-anchor": "middle",
        fill: "#71839b",
        "font-size": 11
      }, points[index].date.slice(5));
    });

    target.appendChild(svg);
  }

  function render(data) {
    get("analytics-title").textContent =
      level === "category" ? data.category : data.product;

    get("analytics-subtitle").textContent =
      `${data.category} | ` +
      `${data.period.start_date} to ${data.period.end_date}`;

    get("analytics-revenue").textContent =
      money.format(data.kpis.net_sales);

    get("analytics-units").textContent =
      number.format(data.kpis.units_sold);

    get("analytics-growth").textContent =
      percent(data.kpis.growth_pct);

    const share = data.kpis.category_share_pct;

    get("analytics-share").textContent =
      share == null ? "N/A" : `${Number(share).toFixed(1)}%`;

    renderTrend(data.revenue_trend || []);

    const insights = get("analytics-insights");
    insights.replaceChildren();

    (data.insights || []).forEach(item => {
      const listItem = add(insights, "li");

      add(listItem, "strong", item.title);
      add(listItem, "span", item.detail);
    });

    const products = get("analytics-products");

    if (products) {
      products.replaceChildren();

      (data.product_performance || []).forEach(item => {
        const row = add(products, "tr");
        const cell = add(row, "td");

        const link = add(cell, "a", item.product);

        link.href = "product-analytics.html?" +
          new URLSearchParams({
            category: data.category,
            product: item.product,
            days: daysInput.value
          });

        add(row, "td", number.format(item.units_sold));
        add(row, "td", money.format(item.revenue));
        add(row, "td", percent(item.growth_pct));
      });

      if (!products.children.length) {
        const row = add(products, "tr");
        const cell = add(row, "td", "No products in this period.");
        cell.colSpan = 4;
      }
    }

    const weekdays = get("analytics-weekdays");
    weekdays.replaceChildren();

    const weekdayData = data.weekday_performance || [];

    const maximum = Math.max(
      1,
      ...weekdayData.map(item =>
        Math.max(0, item.average_daily_revenue)
      )
    );

    weekdayData.forEach(item => {
      const row = add(weekdays, "div");
      row.className = "analytics-weekday";

      add(row, "span", item.weekday);

      const track = add(row, "div");
      track.className = "analytics-track";

      const fill = add(track, "span");
      fill.className = "analytics-fill";

      fill.style.width =
        `${Math.max(0, item.average_daily_revenue) / maximum * 100}%`;

      add(row, "span", money.format(item.average_daily_revenue));
    });

    get("analytics-status").textContent = data.has_data
      ? "Showing sales analytics for your business."
      : "No sales found for this reporting period.";
  }

  let latestRequest = 0;

  async function load() {
    const token = localStorage.getItem("token");

    if (!token) {
      location.href = "signin.html";
      return;
    }

    const request = ++latestRequest;

    get("analytics-status").textContent = "Loading analytics...";

    const query = new URLSearchParams({
      category,
      days: daysInput.value
    });

    if (level === "product") {
      query.set("product", product);
    }

    const endpoint = level === "product"
      ? "/api/dashboard/product-analytics"
      : "/api/dashboard/category-analytics";

    try {
      const response = await fetch(`${endpoint}?${query}`, {
        headers: {
          Authorization: `Bearer ${token}`
        },
        cache: "no-store"
      });

      if (request !== latestRequest) return;

      if (response.status === 401) {
        location.href = "signin.html";
        return;
      }

      if (!response.ok) {
        throw new Error(
          `Analytics unavailable (HTTP ${response.status}).`
        );
      }

      render(await response.json());

    } catch (error) {
      if (request === latestRequest) {
        get("analytics-status").textContent = error.message;
      }
    }
  }

  daysInput.addEventListener("change", () => {
    params.set("days", daysInput.value);

    history.replaceState(
      null,
      "",
      location.pathname + "?" + params
    );

    if (back) {
      back.href = "category-analytics.html?" +
        new URLSearchParams({
          category,
          days: daysInput.value
        });
    }

    load();
  });

  load();
})();
