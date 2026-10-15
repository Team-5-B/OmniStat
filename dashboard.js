// Nicholas - Tasks 2.7 and 2.8: revenue chart and KPI cards with SAMPLE data.
// When the CSV parser is done (sprint 2), replace makeSampleData() with real numbers from the backend. Everything below it stays the same.

// Sample data -
// Makes 30 days of fake sales. Same numbers every refresh (no Math.random), with busier weekends so it looks like a real store.

// TODO (sprint 2): replace with real daily sales from the backend once the CSV parser is done.
function makeSampleData() {
    const days = [];
    const today = new Date();

    for (let i = 29; i >= 0; i--) {
        const date = new Date(today);
        date.setDate(today.getDate() - i);

        const weekday = date.getDay(); // 0 = Sunday, 6 = Saturday
        const isWeekend = weekday === 0 || weekday === 6;
        const wiggle = Math.sin(i * 1.7) * 220; // fake day to day variation

        const revenue = Math.round(1800 + (isWeekend ? 650 : 0) + wiggle);
        const transactions = Math.round(revenue / 24 + Math.cos(i) * 6);

        days.push({ date, revenue, transactions });
    }
    return days;
}

// Fake number of products in stock, until the inventory page exists.
// TODO (sprint 2): replace with the real item count once the inventory page exists.
const SAMPLE_INVENTORY_ITEMS = 148;

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

function renderKpis(days) {
    const totalSales = days.reduce((sum, day) => sum + day.revenue, 0);
    const totalOrders = days.reduce((sum, day) => sum + day.transactions, 0);

    setCard("Total Sales", money.format(totalSales));
    setCard("Total Orders", count.format(totalOrders));
    setCard("Inventory Items", count.format(SAMPLE_INVENTORY_ITEMS));
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

// Run it 
const days = makeSampleData();
renderKpis(days);
renderRevenueChart(days);