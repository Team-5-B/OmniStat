(() => {
  "use strict";

  const root = document.getElementById("daily-reconciliation");
  if (!root) return;

  const get = id => document.getElementById(id);
  const params = new URLSearchParams(window.location.search);
  const input = get("rd-day");
  const message = get("rd-message");
  const results = get("rd-results");
  const tbody = get("rd-records");

  let page = 1;
  const currency = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD"
  });

  function cell(row, value) {
    const td = document.createElement("td");
    td.textContent = value == null ? "—" : String(value);
    row.appendChild(td);
  }

  function showError(text) {
    message.textContent = text;
    results.hidden = true;
  }

  async function load() {
    const token = localStorage.getItem("token");

    if (!token) {
      showError("Please sign in to investigate daily revenue.");
      return;
    }

    if (!input.value) {
      showError("Choose a reporting day.");
      return;
    }

    message.textContent = "Loading sales evidence...";
    results.hidden = true;

    const query = new URLSearchParams({
      day: input.value,
      page: String(page),
      page_size: "25"
    });

    try {
      const response = await fetch(
        "/api/business/data-quality/day?" + query,
        {
          headers: {
            Authorization: "Bearer " + token
          },
          cache: "no-store"
        }
      );

      if (response.status === 401 || response.status === 403) {
        showError("This report requires an authorized business owner.");
        return;
      }

      if (!response.ok) {
        throw new Error("Unable to retrieve the daily sales report.");
      }

      const data = await response.json();

      get("rd-stored").textContent =
        data.stored.net_revenue == null
          ? "Missing"
          : currency.format(data.stored.net_revenue);

      get("rd-calculated").textContent =
        currency.format(data.recomputed.net_revenue);

      get("rd-difference").textContent =
        data.difference.net_revenue == null
          ? "N/A"
          : currency.format(data.difference.net_revenue);

      get("rd-status").textContent =
        data.status.replaceAll("_", " ");

      get("rd-explanation").textContent = data.explanation;

      tbody.replaceChildren();

      for (const item of data.records) {
        const row = document.createElement("tr");
        cell(row, item.product);
        cell(row, item.category);
        cell(row, item.quantity);
        cell(row, currency.format(item.net_revenue));
        cell(row, item.upload_filename || item.upload_id);
        cell(row, item.id);
        tbody.appendChild(row);
      }

      get("rd-page").textContent =
        `Page ${data.pagination.page} of ` +
        `${Math.max(1, data.pagination.total_pages)}`;

      get("rd-prev").disabled = !data.pagination.has_previous;
      get("rd-next").disabled = !data.pagination.has_next;

      message.textContent =
        data.recomputed.record_count === 0
          ? "No source sales records for this day."
          : `${data.recomputed.record_count} source records found.`;

      results.hidden = false;

    } catch (error) {
      showError(error.message);
    }
  }

  input.value = params.get("day") || "";

  get("rd-form").addEventListener("submit", event => {
    event.preventDefault();
    page = 1;
    load();
  });

  get("rd-prev").addEventListener("click", () => {
    if (page > 1) {
      page--;
      load();
    }
  });

  get("rd-next").addEventListener("click", () => {
    page++;
    load();
  });

  if (input.value) load();
})();
