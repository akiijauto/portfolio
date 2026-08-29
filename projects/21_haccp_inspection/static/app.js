/* 写真ベース 衛生点検・HACCP記録サポート JavaScript */

const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                  .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function showErr(id, msg) { const el=document.getElementById(id); el.textContent=msg; el.style.display='block'; }
function hideErr(id) { document.getElementById(id).style.display='none'; }

function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.getElementById('nav-' + name).classList.add('active');
}

const JUDGEMENT_CLASS = { 'OK': 'judge-ok', '要注意': 'judge-warn', 'NG': 'judge-ng', '確認不可': 'judge-unknown' };

let _log = [];

function previewImage() {
  const input = document.getElementById('image-input');
  const preview = document.getElementById('image-preview');
  const file = input.files[0];
  if (!file) { preview.style.display = 'none'; return; }
  const reader = new FileReader();
  reader.onload = (e) => {
    preview.src = e.target.result;
    preview.style.display = 'block';
  };
  reader.readAsDataURL(file);
}

async function doInspect() {
  hideErr('inspect-error');
  const input = document.getElementById('image-input');
  const file = input.files[0];
  if (!file) {
    showErr('inspect-error', '点検対象の写真をアップロードしてください');
    return;
  }
  const category = document.querySelector('input[name="category"]:checked').value;
  const categoryLabel = document.querySelector('input[name="category"]:checked').nextElementSibling.textContent;
  const notes = document.getElementById('notes').value.trim();

  const btn = document.getElementById('inspect-btn');
  btn.disabled = true;
  document.getElementById('inspect-progress').style.display = 'block';

  try {
    const fd = new FormData();
    fd.append('image', file);
    fd.append('category', category);
    fd.append('notes', notes);

    const res = await fetch('api/inspect', {
      method: 'POST',
      headers: { 'X-CSRFToken': csrfToken },
      body: fd
    });
    const d = await res.json();
    if (!d.ok) { showErr('inspect-error', d.error); return; }

    const previewSrc = document.getElementById('image-preview').src;
    renderLatestResult(d.result, categoryLabel, previewSrc);
    addToLog(d.result, categoryLabel, previewSrc, notes);
  } finally {
    btn.disabled = false;
    document.getElementById('inspect-progress').style.display = 'none';
  }
}

function renderLatestResult(r, categoryLabel, imgSrc) {
  const judgeClass = JUDGEMENT_CLASS[r.overall_judgement] || 'judge-unknown';

  const checksHtml = (r.checks || []).map(c => `
    <div class="check-row">
      <span class="check-judge ${JUDGEMENT_CLASS[c.result] || 'judge-unknown'}">${escHtml(c.result || '-')}</span>
      <div class="check-body">
        <div class="check-item">${escHtml(c.item || '')}</div>
        <div class="check-comment">${escHtml(c.comment || '')}</div>
      </div>
    </div>`).join('');

  const issuesHtml = (r.issues || []).length
    ? `<ul>${r.issues.map(x => `<li>${escHtml(x)}</li>`).join('')}</ul>`
    : '<p class="empty-note">問題点は確認されませんでした</p>';

  const actionsHtml = (r.corrective_actions || []).length
    ? `<ul>${r.corrective_actions.map(x => `<li>${escHtml(x)}</li>`).join('')}</ul>`
    : '<p class="empty-note">改善アクションはありません</p>';

  document.getElementById('latest-result').innerHTML = `
    <div class="box">
      <div class="result-header">
        <img src="${imgSrc}" class="result-thumb">
        <div>
          <div class="result-category">${escHtml(categoryLabel)}</div>
          <div class="judge-badge ${judgeClass}">総合判定: ${escHtml(r.overall_judgement || '-')}</div>
        </div>
      </div>
      <h3>観察結果</h3>
      <p>${escHtml(r.observation || '')}</p>
      <h3>チェック項目</h3>
      <div class="check-list">${checksHtml}</div>
      <h3>問題点</h3>
      ${issuesHtml}
      <h3>改善アクション</h3>
      ${actionsHtml}
      <h3>記録用コメント</h3>
      <p class="record-comment">${escHtml(r.record_comment || '')}</p>
    </div>`;
}

function addToLog(r, categoryLabel, imgSrc, notes) {
  const now = new Date();
  const time = now.toTimeString().slice(0, 5);
  _log.push({ time, categoryLabel, judgement: r.overall_judgement, comment: r.record_comment, notes, imgSrc });
  renderLog();
}

function renderLog() {
  const empty = document.getElementById('log-empty');
  const list = document.getElementById('log-list');
  if (_log.length === 0) {
    empty.style.display = 'block';
    list.innerHTML = '';
    return;
  }
  empty.style.display = 'none';
  list.innerHTML = _log.map(entry => `
    <div class="log-row">
      <img src="${entry.imgSrc}" class="log-thumb">
      <div class="log-body">
        <div class="log-meta">
          <span class="log-time">${escHtml(entry.time)}</span>
          <span class="log-category">${escHtml(entry.categoryLabel)}</span>
          <span class="judge-badge ${JUDGEMENT_CLASS[entry.judgement] || 'judge-unknown'}">${escHtml(entry.judgement || '-')}</span>
        </div>
        <div class="log-comment">${escHtml(entry.comment || '')}</div>
      </div>
    </div>`).join('');
}

function downloadLog() {
  if (_log.length === 0) return;
  const lines = ['■ 衛生点検記録（HACCP）', `日付: ${new Date().toISOString().slice(0, 10)}`, ''];
  _log.forEach((entry, i) => {
    lines.push(`${i + 1}. [${entry.time}] ${entry.categoryLabel} — 判定: ${entry.judgement}`);
    if (entry.notes) lines.push(`   補足: ${entry.notes}`);
    lines.push(`   コメント: ${entry.comment}`);
    lines.push('');
  });
  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `衛生点検記録_${new Date().toISOString().slice(0, 10)}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}
