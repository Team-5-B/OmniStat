// Nicholas - Tasks 2.7 and 2.8: revenue chart and KPI cards.
// Nicholas - Task 3.11: real numbers now come from GET /api/dashboard/summary (Siddartha's 3.6) instead of sample data.

// Formatting helpers 
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const count = new Intl.NumberFormat("en-US");

function shortDate(date) {
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// Task 2.8: KPI cards 
// Fills in sneha's existing cards by matching their titles, so the card html doesn't need to change.
function setCard(title, value) {
    for (const card of document.querySelectorAll(".dashboard-cards .card")) {
        if (card.querySelector("h2").textContent.trim() === title) {
            card.querySelector("p").textContent = value;
        }
    }
}

// Task 3.11: KPI cards from the summary endpoint
function renderKpis(kpis) {
    setCard("Total Sales", money.format(kpis.total_revenue));
    setCard("Items Sold", count.format(kpis.items_sold_count));
    // no inventory data until sprint 3, so show a dash instead of a fake number.
    setCard("Inventory Items", "—");
}

// Task 2.7: revenue chart 
function renderRevenueChart(days) {
    const canvas = document.getElementById("revenue-chart");

    new Chart(canvas, {
        type: "line",
        data: {
            labels: days.map((day) => shortDate(day.date)),
            datasets: [{
                label: "Revenue",
                data: days.map((day) => day.revenue),
                borderColor: "#2563eb",
                backgroundColor: "rgba(37, 99, 235, 0.08)",
                fill: true,
                tension: 0.3,
                pointRadius: 0,
                pointHoverRadius: 5,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: { label: (item) => " " + money.format(item.parsed.y) },
                },
            },
            scales: {
                x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } },
                y: {
                    beginAtZero: true,
                    ticks: { callback: (value) => money.format(value).replace(".00", "") },
                },
            },
        },
    });
}

// Task 3.11: message shown in the chart area when there's nothing to chart
function showChartMessage(text) {
    document.querySelector(".chart-box").hidden = true;
    const message = document.getElementById("chart-message");
    message.textContent = text;
    message.hidden = false;
}

// Task 3.11: load the summary and fill in the dashboard
async function loadDashboard() {
    const token = localStorage.getItem("token");
    if (!token) return; // the check in dashboard.html already sends them to sign in

    try {
        const response = await fetch("/api/dashboard/summary", {
            headers: { "Authorization": "Bearer " + token },
        });

        // expired or bad token: same as being logged out.
        if (response.status === 401) {
            localStorage.removeItem("token");
            window.location.href = "signin.html";
            return;
        }
        if (!response.ok) {
            throw new Error("Summary request failed: " + response.status);
        }

        const summary = await response.json();
        renderKpis(summary.kpis);

        // empty state: a new business with no uploads yet.
        if (!summary.has_data) {
            showChartMessage("No sales data yet. Upload your first POS report below to see your revenue here.");
            return;
        }

        // "2026-11-03" read as local time, so the label doesn't shift back a day in US time zones.
        const days = summary.revenue_30_days.map((day) => ({
            date: new Date(day.date + "T00:00:00"),
            revenue: day.revenue,
        }));
        renderRevenueChart(days);
    } catch (error) {
        console.error(error);
        showChartMessage("Couldn't load your sales data. Try refreshing the page.");
    }
}

loadDashboard();