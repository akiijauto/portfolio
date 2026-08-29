const basePath = window.location.pathname.replace(/\/$/, "");
const socket = io({ path: `${basePath}/socket.io` });

const alertForm = document.getElementById("alert-form");
if (alertForm) {
  alertForm.action = `${basePath}/alert`;
}

const priceEls = {
  usdjpy: document.getElementById("price-usdjpy"),
  eurjpy: document.getElementById("price-eurjpy"),
  nikkei225: document.getElementById("price-nikkei225"),
  sp500: document.getElementById("price-sp500"),
};

const ctx = document.getElementById("market-chart");
const chart = new Chart(ctx, {
  type: "line",
  data: {
    labels: [],
    datasets: [
      { label: "USD/JPY", data: [], borderColor: "#2d6cdf", tension: 0.2, yAxisID: "y" },
    ],
  },
  options: {
    animation: false,
    scales: { y: { beginAtZero: false } },
  },
});

const MAX_POINTS = 60;

socket.on("market_update", (data) => {
  for (const key in priceEls) {
    if (data[key] !== null && data[key] !== undefined) {
      priceEls[key].textContent = data[key];
    }
  }

  const now = new Date().toLocaleTimeString("ja-JP");
  chart.data.labels.push(now);
  chart.data.datasets[0].data.push(data.usdjpy);
  if (chart.data.labels.length > MAX_POINTS) {
    chart.data.labels.shift();
    chart.data.datasets[0].data.shift();
  }
  chart.update();
});

socket.on("rate_alert", (alert) => {
  const message = `${alert.pair}が${alert.threshold}を超えました（現在: ${alert.rate}）`;
  if (window.Notification && Notification.permission === "granted") {
    new Notification("レートアラート", { body: message });
  } else {
    alert(message);
  }
});

const hint = document.getElementById("notification-permission-hint");
if (window.Notification && Notification.permission === "default") {
  hint.textContent = "ブラウザ通知を許可すると、アラート発生時にデスクトップ通知が届きます。";
  hint.onclick = () => Notification.requestPermission();
  hint.style.cursor = "pointer";
  hint.style.textDecoration = "underline";
}
