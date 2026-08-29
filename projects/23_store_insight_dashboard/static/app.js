const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const jsonHeaders = { "Content-Type": "application/json", "X-CSRFToken": csrfToken };

const dataRows = document.getElementById("data-rows");
const notesEl = document.getElementById("notes");
const charCountEl = document.getElementById("char-count");
const inputError = document.getElementById("input-error");
const analyzeBtn = document.getElementById("analyze-btn");

let chart = null;

function switchTab(tabId) {
  document.querySelectorAll(".tab-pane").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach((el) => el.classList.remove("active"));
  document.getElementById(tabId).classList.add("active");
  document.querySelector(`.tab-btn[data-tab="${tabId}"]`).classList.add("active");
}

function escHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function addRow(date = "", sales = "", customers = "", staff = "") {
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input type="date" class="f-date" value="${date}"></td>
    <td><input type="number" class="f-sales" min="0" value="${sales}"></td>
    <td><input type="number" class="f-customers" min="0" value="${customers}"></td>
    <td><input type="number" class="f-staff" min="0" value="${staff}"></td>
    <td><button class="row-remove" onclick="this.closest('tr').remove()">削除</button></td>
  `;
  dataRows.appendChild(tr);
}

function loadSampleData() {
  dataRows.innerHTML = "";
  const sample = [
    ["2026-06-08", 182000, 64, 3],
    ["2026-06-09", 195000, 70, 3],
    ["2026-06-10", 121000, 48, 2],
    ["2026-06-11", 118000, 45, 2],
    ["2026-06-12", 134000, 52, 2],
    ["2026-06-13", 226000, 81, 4],
    ["2026-06-14", 248000, 90, 4],
  ];
  sample.forEach((row) => addRow(...row));
  notesEl.value = "週末はレジ前に行列ができて待ち時間のクレームが数件あった。火曜・水曜は客数が少なく、スタッフが手持ち無沙汰になっている時間帯がある。SNSクーポンを使った客は単価が高い傾向。";
  charCountEl.textContent = notesEl.value.length;
}

notesEl.addEventListener("input", () => {
  charCountEl.textContent = notesEl.value.length;
});

function collectRecords() {
  const records = [];
  for (const tr of dataRows.querySelectorAll("tr")) {
    const date = tr.querySelector(".f-date").value;
    const sales = tr.querySelector(".f-sales").value;
    const customers = tr.querySelector(".f-customers").value;
    const staff = tr.querySelector(".f-staff").value;
    if (!date || sales === "" || customers === "" || staff === "") continue;
    records.push({ date, sales: parseInt(sales, 10), customers: parseInt(customers, 10), staff: parseInt(staff, 10) });
  }
  return records;
}

async function doAnalyze() {
  inputError.style.display = "none";
  const records = collectRecords();
  if (records.length === 0) {
    inputError.textContent = "⚠️ 1行以上、日付・売上・客数・スタッフ人数をすべて入力してください";
    inputError.style.display = "block";
    return;
  }

  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "分析中...";

  try {
    const res = await fetch("api/analyze", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ records, notes: notesEl.value }),
    });
    const data = await res.json();
    if (data.ok) {
      renderDashboard(records, data.result);
      switchTab("tab-dashboard");
    } else {
      inputError.textContent = "⚠️ " + (data.error || "分析に失敗しました");
      inputError.style.display = "block";
    }
  } catch (e) {
    inputError.textContent = "⚠️ 通信エラーが発生しました。しばらく待ってから再試行してください。";
    inputError.style.display = "block";
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "AIで分析する";
  }
}

function renderDashboard(records, result) {
  document.getElementById("dashboard-empty").style.display = "none";
  document.getElementById("dashboard-content").style.display = "block";

  const labels = records.map((r) => r.date);
  const sales = records.map((r) => r.sales);
  const customers = records.map((r) => r.customers);

  if (chart) chart.destroy();
  chart = new Chart(document.getElementById("trend-chart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "売上(円)", data: sales, borderColor: "#6d28d9", backgroundColor: "rgba(109,40,217,.1)", yAxisID: "y", tension: .3 },
        { label: "客数(人)", data: customers, borderColor: "#22c55e", backgroundColor: "rgba(34,197,94,.1)", yAxisID: "y1", tension: .3 },
      ],
    },
    options: {
      scales: {
        y:  { type: "linear", position: "left", title: { display: true, text: "売上(円)" } },
        y1: { type: "linear", position: "right", title: { display: true, text: "客数(人)" }, grid: { drawOnChartArea: false } },
      },
    },
  });

  document.getElementById("trend-summary").textContent = result.trend_summary || "";

  renderList("good-points", result.good_points || []);
  renderList("concern-points", result.concern_points || []);

  const actionList = document.getElementById("action-list");
  actionList.innerHTML = "";
  const actions = result.improvement_actions || [];
  if (actions.length === 0) {
    actionList.innerHTML = '<p class="insight-empty">提案はありません</p>';
  } else {
    actions.forEach((a) => {
      const div = document.createElement("div");
      div.className = "action-card";
      div.innerHTML = `
        <div class="action-head">
          <span class="action-title">${escHtml(a.title || "")}</span>
          <span class="priority priority-${escHtml(a.priority || "中")}">優先度: ${escHtml(a.priority || "中")}</span>
        </div>
        <div class="action-desc">${escHtml(a.description || "")}</div>
      `;
      actionList.appendChild(div);
    });
  }
}

function renderList(id, items) {
  const ul = document.getElementById(id);
  ul.innerHTML = "";
  if (items.length === 0) {
    ul.innerHTML = '<li class="insight-empty" style="padding-left:0;">該当する項目はありませんでした</li>';
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    ul.appendChild(li);
  });
}

// 初期表示: 1行追加
addRow();
