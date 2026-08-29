const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const jsonHeaders = { "Content-Type": "application/json", "X-CSRFToken": csrfToken };

const itemRows = document.getElementById("item-rows");
const notesEl = document.getElementById("notes");
const charCountEl = document.getElementById("char-count");
const inputError = document.getElementById("input-error");
const predictBtn = document.getElementById("predict-btn");

function switchTab(tabId) {
  document.querySelectorAll(".tab-pane").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach((el) => el.classList.remove("active"));
  document.getElementById(tabId).classList.add("active");
  document.querySelector(`.tab-btn[data-tab="${tabId}"]`).classList.add("active");
}

function escHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function addItemRow(name = "", stock = "", usage = "", lead = "", lot = "") {
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input type="text" class="f-name" value="${escHtml(name)}" placeholder="例: コーヒー豆(1kg)"></td>
    <td><input type="number" class="f-stock" min="0" value="${stock}"></td>
    <td><input type="number" class="f-usage" min="0" step="0.1" value="${usage}"></td>
    <td><input type="number" class="f-lead" min="0" value="${lead}"></td>
    <td><input type="number" class="f-lot" min="0" value="${lot}"></td>
    <td><button class="row-remove" onclick="this.closest('tr').remove()">削除</button></td>
  `;
  itemRows.appendChild(tr);
}

function loadSampleData() {
  itemRows.innerHTML = "";
  const sample = [
    ["コーヒー豆(1kg)", 4, 1.2, 5, 5],
    ["紙コップ(100個入)", 2, 0.8, 7, 3],
    ["牛乳(1L)", 6, 3, 2, 6],
    ["紙ナプキン(500枚入)", 1, 0.1, 10, 2],
  ];
  sample.forEach((row) => addItemRow(...row));
  notesEl.value = "来週末は近隣でイベントがあり、来客数が通常の1.5倍程度を見込んでいる。";
  charCountEl.textContent = notesEl.value.length;
}

notesEl.addEventListener("input", () => {
  charCountEl.textContent = notesEl.value.length;
});

function collectItems() {
  const items = [];
  for (const tr of itemRows.querySelectorAll("tr")) {
    const name = tr.querySelector(".f-name").value.trim();
    const stock = tr.querySelector(".f-stock").value;
    const usage = tr.querySelector(".f-usage").value;
    const lead = tr.querySelector(".f-lead").value;
    const lot = tr.querySelector(".f-lot").value;
    if (!name || stock === "" || usage === "" || lead === "" || lot === "") continue;
    items.push({
      name,
      current_stock: parseFloat(stock),
      avg_daily_usage: parseFloat(usage),
      lead_time_days: parseFloat(lead),
      order_lot: parseFloat(lot),
    });
  }
  return items;
}

async function doPredict() {
  inputError.style.display = "none";
  const items = collectItems();
  if (items.length === 0) {
    inputError.textContent = "⚠️ 1件以上、商品名と全項目を入力してください";
    inputError.style.display = "block";
    return;
  }

  predictBtn.disabled = true;
  predictBtn.textContent = "予測中...";

  try {
    const res = await fetch("api/predict", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ items, notes: notesEl.value }),
    });
    const data = await res.json();
    if (data.ok) {
      renderResult(data.result);
      switchTab("tab-result");
    } else {
      inputError.textContent = "⚠️ " + (data.error || "予測に失敗しました");
      inputError.style.display = "block";
    }
  } catch (e) {
    inputError.textContent = "⚠️ 通信エラーが発生しました。しばらく待ってから再試行してください。";
    inputError.style.display = "block";
  } finally {
    predictBtn.disabled = false;
    predictBtn.textContent = "AIで発注タイミングを予測する";
  }
}

const URGENCY_CLASS = { "緊急": "urgency-high", "早めに発注": "urgency-mid", "様子見": "urgency-low" };

function renderResult(result) {
  document.getElementById("result-empty").style.display = "none";
  document.getElementById("result-content").style.display = "block";

  const listEl = document.getElementById("items-list");
  listEl.innerHTML = "";
  const items = result.items || [];
  items.forEach((it) => {
    const cls = URGENCY_CLASS[it.urgency] || "urgency-low";
    const card = document.createElement("div");
    card.className = "card item-card";
    card.innerHTML = `
      <div class="card-header">
        <span class="item-name">${escHtml(it.name || "")}</span>
        <span class="urgency-badge ${cls}">${escHtml(it.urgency || "")}</span>
      </div>
      <div class="item-meta">在庫が尽きるまでの予測: 約${escHtml(it.days_until_stockout ?? "?")}日 / 推奨発注量: ${escHtml(it.recommended_order_qty ?? "?")}個</div>
      <p class="item-advice">${escHtml(it.reorder_advice || "")}</p>
      ${it.note ? `<p class="item-note">${escHtml(it.note)}</p>` : ""}
    `;
    listEl.appendChild(card);
  });

  renderList("concern-list", result.overall_concerns || []);
  renderList("suggestion-list", result.suggestions || []);
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

// 初期表示
addItemRow();
