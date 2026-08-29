const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const jsonHeaders = { "Content-Type": "application/json", "X-CSRFToken": csrfToken };

const staffRows = document.getElementById("staff-rows");
const reqRows = document.getElementById("req-rows");
const notesEl = document.getElementById("notes");
const charCountEl = document.getElementById("char-count");
const inputError = document.getElementById("input-error");
const generateBtn = document.getElementById("generate-btn");

const DAYS = ["月", "火", "水", "木", "金", "土", "日"];

function switchTab(tabId) {
  document.querySelectorAll(".tab-pane").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach((el) => el.classList.remove("active"));
  document.getElementById(tabId).classList.add("active");
  document.querySelector(`.tab-btn[data-tab="${tabId}"]`).classList.add("active");
}

function escHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function addStaffRow(name = "", days = "", hours = "", maxHours = "") {
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input type="text" class="f-name" value="${escHtml(name)}" placeholder="例: 田中"></td>
    <td><input type="text" class="f-days" value="${escHtml(days)}" placeholder="例: 月,火,木,金"></td>
    <td><input type="text" class="f-hours" value="${escHtml(hours)}" placeholder="例: 10:00-15:00"></td>
    <td><input type="number" class="f-maxhours" min="0" value="${maxHours}"></td>
    <td><button class="row-remove" onclick="this.closest('tr').remove()">削除</button></td>
  `;
  staffRows.appendChild(tr);
}

function buildReqRows() {
  reqRows.innerHTML = "";
  DAYS.forEach((day) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${day}</td>
      <td><input type="text" class="f-open" placeholder="例: 10:00-19:00"></td>
      <td><input type="number" class="f-required" min="0" value="0"></td>
    `;
    reqRows.appendChild(tr);
  });
}

function loadSampleData() {
  staffRows.innerHTML = "";
  const sample = [
    ["田中", "月,火,水,木,金", "09:00-17:00", 35],
    ["佐藤", "月,水,金,土,日", "10:00-19:00", 30],
    ["鈴木", "火,木,土,日", "13:00-21:00", 25],
    ["高橋", "土,日", "10:00-18:00", 16],
  ];
  sample.forEach((row) => addStaffRow(...row));

  const reqSample = {
    "月": ["10:00-19:00", 2], "火": ["10:00-19:00", 2], "水": ["10:00-19:00", 2],
    "木": ["10:00-19:00", 2], "金": ["10:00-19:00", 2], "土": ["10:00-20:00", 3], "日": ["10:00-20:00", 3],
  };
  for (const tr of reqRows.querySelectorAll("tr")) {
    const day = tr.children[0].textContent;
    const [open, required] = reqSample[day];
    tr.querySelector(".f-open").value = open;
    tr.querySelector(".f-required").value = required;
  }

  notesEl.value = "土日は来客が多いため、できればベテランの田中・佐藤を1名以上配置したい。";
  charCountEl.textContent = notesEl.value.length;
}

notesEl.addEventListener("input", () => {
  charCountEl.textContent = notesEl.value.length;
});

function collectStaff() {
  const staff = [];
  for (const tr of staffRows.querySelectorAll("tr")) {
    const name = tr.querySelector(".f-name").value.trim();
    const days = tr.querySelector(".f-days").value.trim();
    const hours = tr.querySelector(".f-hours").value.trim();
    const maxHours = tr.querySelector(".f-maxhours").value;
    if (!name || maxHours === "") continue;
    staff.push({ name, available_days: days, preferred_hours: hours, max_hours: parseInt(maxHours, 10) });
  }
  return staff;
}

function collectRequirements() {
  const requirements = [];
  for (const tr of reqRows.querySelectorAll("tr")) {
    const day = tr.children[0].textContent;
    const open = tr.querySelector(".f-open").value.trim();
    const required = tr.querySelector(".f-required").value;
    requirements.push({ day, open_hours: open, required_count: parseInt(required || "0", 10) });
  }
  return requirements;
}

async function doGenerate() {
  inputError.style.display = "none";
  const staff = collectStaff();
  const requirements = collectRequirements();
  if (staff.length === 0) {
    inputError.textContent = "⚠️ 1名以上、氏名と週の上限時間を入力してください";
    inputError.style.display = "block";
    return;
  }

  generateBtn.disabled = true;
  generateBtn.textContent = "作成中...";

  try {
    const res = await fetch("api/generate", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ staff, requirements, notes: notesEl.value }),
    });
    const data = await res.json();
    if (data.ok) {
      renderResult(data.result);
      switchTab("tab-result");
    } else {
      inputError.textContent = "⚠️ " + (data.error || "シフト作成に失敗しました");
      inputError.style.display = "block";
    }
  } catch (e) {
    inputError.textContent = "⚠️ 通信エラーが発生しました。しばらく待ってから再試行してください。";
    inputError.style.display = "block";
  } finally {
    generateBtn.disabled = false;
    generateBtn.textContent = "AIでシフトを作成する";
  }
}

function renderResult(result) {
  document.getElementById("result-empty").style.display = "none";
  document.getElementById("result-content").style.display = "block";

  const wrap = document.getElementById("shift-table-wrap");
  wrap.innerHTML = "";
  const plan = result.shift_plan || [];
  plan.forEach((d) => {
    const card = document.createElement("div");
    card.className = "card shift-day-card";
    const statusBadge = d.staffing_ok === false
      ? '<span class="badge-warn">⚠️ 人数不足の可能性</span>'
      : '<span class="badge-ok">✅ 配置OK</span>';
    const rows = (d.assignments || []).map((a) => `
      <tr>
        <td>${escHtml(a.name || "")}</td>
        <td>${escHtml(a.time || "")}</td>
        <td>${escHtml(a.break || "")}</td>
      </tr>
    `).join("");
    card.innerHTML = `
      <div class="card-header">
        <span class="shift-day-title">${escHtml(d.day || "")}曜日</span>
        ${statusBadge}
      </div>
      ${rows ? `
        <table class="data-table">
          <thead><tr><th>担当</th><th>勤務時間</th><th>休憩</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      ` : '<p class="insight-empty">この曜日の配置はありません</p>'}
      ${d.note ? `<p class="shift-note">${escHtml(d.note)}</p>` : ""}
    `;
    wrap.appendChild(card);
  });

  renderList("concern-list", result.concerns || []);
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
addStaffRow();
buildReqRows();
