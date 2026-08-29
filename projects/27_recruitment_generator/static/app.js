const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const jsonHeaders = { "Content-Type": "application/json", "X-CSRFToken": csrfToken };

const positionEl = document.getElementById("position");
const employmentTypeEl = document.getElementById("employment-type");
const workScheduleEl = document.getElementById("work-schedule");
const salaryEl = document.getElementById("salary");
const jobDescriptionEl = document.getElementById("job-description");
const jobCountEl = document.getElementById("job-count");
const idealCandidateEl = document.getElementById("ideal-candidate");
const appealPointsEl = document.getElementById("appeal-points");
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

jobDescriptionEl.addEventListener("input", () => {
  jobCountEl.textContent = jobDescriptionEl.value.length;
});

function loadSampleData() {
  positionEl.value = "カフェのホールスタッフ";
  employmentTypeEl.value = "アルバイト・パート";
  workScheduleEl.value = "平日10:00-18:00の間で週3日〜、1日4時間以上、土日勤務できる方歓迎";
  salaryEl.value = "時給1100円〜（経験により昇給あり）";
  jobDescriptionEl.value = "接客・レジ対応、ドリンク・フードの提供、簡単な清掃業務。お客様への丁寧な接客を心がけていただきます。";
  idealCandidateEl.value = "未経験歓迎。笑顔で接客できる方、丁寧な対応ができる方を歓迎します。";
  appealPointsEl.value = "駅徒歩3分、シフト相談OK、まかない付き、社員割引あり。";
  jobCountEl.textContent = jobDescriptionEl.value.length;
}

async function doGenerate() {
  inputError.style.display = "none";
  const position = positionEl.value.trim();
  const employmentType = employmentTypeEl.value.trim();
  const workSchedule = workScheduleEl.value.trim();
  const salary = salaryEl.value.trim();
  const jobDescription = jobDescriptionEl.value.trim();

  if (!position || !employmentType || !workSchedule || !salary || !jobDescription) {
    inputError.textContent = "⚠️ 募集職種・雇用形態・勤務時間・給与・仕事内容をすべて入力してください";
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
        position,
        employment_type: employmentType,
        work_schedule: workSchedule,
        salary,
        job_description: jobDescription,
        ideal_candidate: idealCandidateEl.value,
        appeal_points: appealPointsEl.value,
      }),
    });
    const data = await res.json();
    if (data.ok) {
      lastResult = data.result;
      renderResult(data.result);
      switchTab("tab-result");
    } else {
      inputError.textContent = "⚠️ " + (data.error || "作成に失敗しました");
      inputError.style.display = "block";
    }
  } catch (e) {
    inputError.textContent = "⚠️ 通信エラーが発生しました。しばらく待ってから再試行してください。";
    inputError.style.display = "block";
  } finally {
    generateBtn.disabled = false;
    generateBtn.textContent = "AIで求人原稿を作成する";
  }
}

function renderResult(result) {
  document.getElementById("result-empty").style.display = "none";
  document.getElementById("result-content").style.display = "block";

  const posting = result.job_posting || {};
  document.getElementById("posting-title").textContent = posting.title || "";
  document.getElementById("posting-catch").textContent = posting.catch_copy || "";
  document.getElementById("posting-desc").textContent = posting.job_description || "";
  renderList("posting-requirements", posting.requirements || []);
  renderList("posting-conditions", posting.conditions || []);
  renderList("posting-appeal", posting.appeal_points || []);

  const interview = result.interview_questions || {};
  renderList("interview-basic", interview.basic || []);
  renderList("interview-role", interview.role_specific || []);
  renderList("interview-notes", interview.notes || []);
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

function buildPostingText() {
  if (!lastResult) return "";
  const p = lastResult.job_posting || {};
  const lines = [];
  if (p.title) lines.push(`■ ${p.title}`);
  if (p.catch_copy) lines.push(`\n${p.catch_copy}`);
  if (p.job_description) lines.push(`\n【仕事内容】\n${p.job_description}`);
  if ((p.requirements || []).length) {
    lines.push(`\n【応募資格・歓迎条件】`);
    p.requirements.forEach((r) => lines.push(`- ${r}`));
  }
  if ((p.conditions || []).length) {
    lines.push(`\n【勤務条件】`);
    p.conditions.forEach((c) => lines.push(`- ${c}`));
  }
  if ((p.appeal_points || []).length) {
    lines.push(`\n【アピールポイント】`);
    p.appeal_points.forEach((a) => lines.push(`- ${a}`));
  }
  return lines.join("\n");
}

function buildInterviewText() {
  if (!lastResult) return "";
  const i = lastResult.interview_questions || {};
  const lines = [];
  lines.push("■ 面接質問リスト");
  if ((i.basic || []).length) {
    lines.push(`\n【基本的な質問】`);
    i.basic.forEach((q) => lines.push(`- ${q}`));
  }
  if ((i.role_specific || []).length) {
    lines.push(`\n【職種に関する質問】`);
    i.role_specific.forEach((q) => lines.push(`- ${q}`));
  }
  if ((i.notes || []).length) {
    lines.push(`\n【面接で避けるべき質問・注意事項】`);
    i.notes.forEach((n) => lines.push(`- ${n}`));
  }
  return lines.join("\n");
}

function copyText(kind) {
  const text = kind === "posting" ? buildPostingText() : buildInterviewText();
  navigator.clipboard.writeText(text);
}

function downloadText(kind) {
  const text = kind === "posting" ? buildPostingText() : buildInterviewText();
  const filename = kind === "posting" ? "求人原稿.txt" : "面接質問リスト.txt";
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
