const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const jsonHeaders = { "Content-Type": "application/json", "X-CSRFToken": csrfToken };

const taskNameEl = document.getElementById("task-name");
const targetAudienceEl = document.getElementById("target-audience");
const roughStepsEl = document.getElementById("rough-steps");
const roughCountEl = document.getElementById("rough-count");
const notesEl = document.getElementById("notes");
const notesCountEl = document.getElementById("notes-count");
const inputError = document.getElementById("input-error");
const generateBtn = document.getElementById("generate-btn");

let lastResult = null;

function switchTab(tabId) {
  document.querySelectorAll(".tab-pane").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach((el) => el.classList.remove("active"));
  document.getElementById(tabId).classList.add("active");
  document.querySelector(`.tab-btn[data-tab="${tabId}"]`).classList.add("active");
}

function escHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

roughStepsEl.addEventListener("input", () => {
  roughCountEl.textContent = roughStepsEl.value.length;
});
notesEl.addEventListener("input", () => {
  notesCountEl.textContent = notesEl.value.length;
});

function loadSampleData() {
  taskNameEl.value = "レジ締め作業";
  targetAudienceEl.value = "新人スタッフ・アルバイト";
  roughStepsEl.value = "閉店後にレジの現金を数える。レジ機の精算ボタンを押してレポートを印刷する。レポートの金額と実際に数えた現金が合っているか確認する。レポートを金庫に保管する。レジ内に次の日のお釣り用の現金を残しておく。";
  notesEl.value = "差額が1000円以上ある場合は必ず防犯カメラを確認し、店長に報告すること。";
  roughCountEl.textContent = roughStepsEl.value.length;
  notesCountEl.textContent = notesEl.value.length;
}

async function doGenerate() {
  inputError.style.display = "none";
  const taskName = taskNameEl.value.trim();
  const targetAudience = targetAudienceEl.value.trim();
  const roughSteps = roughStepsEl.value.trim();

  if (!taskName || !targetAudience || !roughSteps) {
    inputError.textContent = "⚠️ 業務名・対象者・ざっくりした手順をすべて入力してください";
    inputError.style.display = "block";
    return;
  }

  generateBtn.disabled = true;
  generateBtn.textContent = "作成中...";

  try {
    const res = await fetch("api/generate", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({
        task_name: taskName,
        target_audience: targetAudience,
        rough_steps: roughSteps,
        notes: notesEl.value,
      }),
    });
    const data = await res.json();
    if (data.ok) {
      lastResult = data.result;
      renderResult(data.result);
      switchTab("tab-result");
    } else {
      inputError.textContent = "⚠️ " + (data.error || "マニュアル作成に失敗しました");
      inputError.style.display = "block";
    }
  } catch (e) {
    inputError.textContent = "⚠️ 通信エラーが発生しました。しばらく待ってから再試行してください。";
    inputError.style.display = "block";
  } finally {
    generateBtn.disabled = false;
    generateBtn.textContent = "AIでマニュアルを作成する";
  }
}

function renderResult(result) {
  document.getElementById("result-empty").style.display = "none";
  document.getElementById("result-content").style.display = "block";

  document.getElementById("manual-title").textContent = result.title || "";
  document.getElementById("manual-purpose").textContent = result.purpose || "";

  renderList("preparation-list", result.preparation || []);
  renderList("mistakes-list", result.common_mistakes || []);

  const checklistEl = document.getElementById("checklist-list");
  checklistEl.innerHTML = "";
  const checklist = result.checklist || [];
  if (checklist.length === 0) {
    checklistEl.innerHTML = '<li class="insight-empty" style="padding-left:0;">該当する項目はありませんでした</li>';
  } else {
    checklist.forEach((item, i) => {
      const li = document.createElement("li");
      li.innerHTML = `<label><input type="checkbox" id="check-${i}"> ${escHtml(item)}</label>`;
      checklistEl.appendChild(li);
    });
  }

  const stepsEl = document.getElementById("steps-list");
  stepsEl.innerHTML = "";
  const steps = result.steps || [];
  steps.forEach((s) => {
    const div = document.createElement("div");
    div.className = "step-card";
    div.innerHTML = `
      <div class="step-head">
        <span class="step-no">STEP ${escHtml(s.step_no || "")}</span>
        <span class="step-title">${escHtml(s.title || "")}</span>
      </div>
      <div class="step-desc">${escHtml(s.description || "")}</div>
      ${s.tips ? `<div class="step-tips">💡 ${escHtml(s.tips)}</div>` : ""}
    `;
    stepsEl.appendChild(div);
  });
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

function buildManualText() {
  if (!lastResult) return "";
  const r = lastResult;
  const lines = [];
  lines.push(`■ ${r.title || ""}`);
  if (r.purpose) lines.push(`\n【目的】\n${r.purpose}`);
  if ((r.preparation || []).length) {
    lines.push(`\n【準備するもの】`);
    r.preparation.forEach((p) => lines.push(`- ${p}`));
  }
  if ((r.steps || []).length) {
    lines.push(`\n【作業手順】`);
    r.steps.forEach((s) => {
      lines.push(`STEP ${s.step_no}: ${s.title}`);
      lines.push(`  ${s.description}`);
      if (s.tips) lines.push(`  💡 ${s.tips}`);
    });
  }
  if ((r.common_mistakes || []).length) {
    lines.push(`\n【よくあるミスと対策】`);
    r.common_mistakes.forEach((m) => lines.push(`- ${m}`));
  }
  if ((r.checklist || []).length) {
    lines.push(`\n【完了チェックリスト】`);
    r.checklist.forEach((c) => lines.push(`[ ] ${c}`));
  }
  return lines.join("\n");
}

function copyManual() {
  const text = buildManualText();
  navigator.clipboard.writeText(text);
}

function downloadManual() {
  const text = buildManualText();
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${(lastResult && lastResult.title) || "manual"}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}
