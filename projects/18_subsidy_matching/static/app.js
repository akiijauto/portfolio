/* 補助金マッチング＆事業計画ドラフト生成 JavaScript */

const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const csrfHeaders = { 'X-CSRFToken': csrfToken };

let _selectedSubsidy = null; // 選択中の補助金（一覧取得時の簡易情報）
let _matchResult = null;
let _planResult = null;

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                  .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function showErr(id, msg) { const el=document.getElementById(id); el.textContent=msg; el.style.display='block'; }
function hideErr(id) { document.getElementById(id).style.display='none'; }
function yen(n) { return (n === null || n === undefined) ? '不明' : '¥' + Number(n).toLocaleString(); }

const TAB_ORDER = ['search', 'match', 'plan'];
function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelectorAll('.tab')[TAB_ORDER.indexOf(name)].classList.add('active');
}

// ── ① 検索 ────────────────────────────────────────────────────
function subsidyCardHtml(s, idx) {
  const period = (s.acceptance_start || '?') + ' 〜 ' + (s.acceptance_end || '?');
  return `
    <div class="subsidy-card">
      <div class="subsidy-title">${escHtml(s.title)}</div>
      <div class="subsidy-meta">
        <span class="badge-area">${escHtml(s.area || '全国')}</span>
        <span class="subsidy-limit">上限額: ${yen(s.max_limit)}</span>
        <span class="subsidy-period">受付期間: ${escHtml(period)}</span>
      </div>
      <div class="subsidy-meta">${escHtml(s.target_employees || '')}</div>
      <div class="btn-row">
        <button class="btn btn-sm btn-primary" onclick="selectSubsidy(${idx})">この補助金で診断する</button>
      </div>
    </div>`;
}

let _searchResults = [];

async function doSearch() {
  const keyword = document.getElementById('in-keyword').value.trim();
  if (keyword.length < 2) { showErr('search-error', 'キーワードは2文字以上で入力してください'); return; }
  hideErr('search-error');

  const btn = document.getElementById('search-btn');
  btn.disabled = true;
  document.getElementById('search-progress').style.display = 'block';
  document.getElementById('search-empty').style.display = 'none';
  document.getElementById('search-results').innerHTML = '';

  const fd = new FormData();
  fd.append('keyword', keyword);
  fd.append('prefecture', document.getElementById('in-prefecture').value);
  fd.append('only_open', document.getElementById('in-only-open').checked ? '1' : '0');

  try {
    const d = await (await fetch('api/search', { method: 'POST', headers: csrfHeaders, body: fd })).json();
    if (!d.ok) { showErr('search-error', d.error); return; }
    _searchResults = d.results;
    if (d.results.length === 0) {
      document.getElementById('search-empty').style.display = 'block';
      document.getElementById('search-empty').querySelector('.empty').textContent =
        '該当する補助金・助成金が見つかりませんでした。キーワードや地域を変えて再検索してください。';
    } else {
      document.getElementById('search-results').innerHTML = d.results.map((s, i) => subsidyCardHtml(s, i)).join('');
    }
  } catch (e) {
    showErr('search-error', '通信エラーが発生しました。しばらく待ってから再試行してください。');
  } finally {
    btn.disabled = false;
    document.getElementById('search-progress').style.display = 'none';
  }
}

function selectedSubsidyInfoHtml(s) {
  const period = (s.acceptance_start || '?') + ' 〜 ' + (s.acceptance_end || '?');
  return `
    <div class="subsidy-title">${escHtml(s.title)}</div>
    <div class="subsidy-meta">
      <span class="badge-area">${escHtml(s.area || '全国')}</span>
      <span class="subsidy-limit">上限額: ${yen(s.max_limit)}</span>
      <span class="subsidy-period">受付期間: ${escHtml(period)}</span>
    </div>`;
}

function selectSubsidy(idx) {
  _selectedSubsidy = _searchResults[idx];
  _matchResult = null;
  _planResult = null;

  // ②タブの表示を更新
  document.getElementById('match-none-box').style.display = 'none';
  document.getElementById('match-selected-box').style.display = 'block';
  document.getElementById('match-form-box').style.display = 'block';
  document.getElementById('match-result-box').style.display = 'none';
  document.getElementById('match-selected-info').innerHTML = selectedSubsidyInfoHtml(_selectedSubsidy);
  hideErr('match-error');

  // ③タブの表示を更新
  document.getElementById('plan-none-box').style.display = 'none';
  document.getElementById('plan-selected-box').style.display = 'block';
  document.getElementById('plan-form-box').style.display = 'block';
  document.getElementById('plan-result-box').style.display = 'none';
  document.getElementById('plan-selected-info').innerHTML = selectedSubsidyInfoHtml(_selectedSubsidy);
  hideErr('plan-error');

  switchTab('match');
}

// ── ② 適合判定 ────────────────────────────────────────────────
async function doMatch() {
  if (!_selectedSubsidy) return;
  const desc = document.getElementById('match-business-desc').value.trim();
  if (!desc) { showErr('match-error', '事業内容を入力してください'); return; }
  hideErr('match-error');

  const btn = document.getElementById('match-btn');
  btn.disabled = true;
  document.getElementById('match-progress').style.display = 'block';
  document.getElementById('match-result-box').style.display = 'none';

  const fd = new FormData();
  fd.append('subsidy_id', _selectedSubsidy.id);
  fd.append('business_desc', desc);

  try {
    const d = await (await fetch('api/match', { method: 'POST', headers: csrfHeaders, body: fd })).json();
    if (!d.ok) { showErr('match-error', d.error); return; }
    _matchResult = d.match;
    renderMatchResult(d.match);
    document.getElementById('match-result-box').style.display = 'block';

    // ③タブ用に事業内容を引き継ぐ
    document.getElementById('plan-business-desc').value = desc;
  } catch (e) {
    showErr('match-error', '通信エラーが発生しました。しばらく待ってから再試行してください。');
  } finally {
    btn.disabled = false;
    document.getElementById('match-progress').style.display = 'none';
  }
}

function renderMatchResult(m) {
  const score = Math.max(0, Math.min(100, Number(m.score) || 0));
  let scoreClass = 'score-low';
  if (score >= 70) scoreClass = 'score-high';
  else if (score >= 40) scoreClass = 'score-mid';

  const list = (items) => (items || []).map(x => `<li>${escHtml(x)}</li>`).join('');

  document.getElementById('match-result').innerHTML = `
    <div class="match-score-wrap">
      <div class="match-score ${scoreClass}">${score}<span class="match-score-unit">/100</span></div>
      <div class="match-score-label">${escHtml(m.score_label || '')}</div>
    </div>
    <div class="match-section">
      <h3>✅ 適合していると考えられる理由</h3>
      <ul>${list(m.reasons)}</ul>
    </div>
    <div class="match-section">
      <h3>⚠️ 申請前に確認すべき注意点</h3>
      <ul>${list(m.concerns)}</ul>
    </div>
    <div class="match-section">
      <h3>📄 必要になりそうな書類</h3>
      <ul>${list(m.required_documents)}</ul>
    </div>
    <div class="match-section">
      <h3>👉 次のアクション</h3>
      <p>${escHtml(m.next_action || '')}</p>
    </div>`;
}

function goToPlan() {
  switchTab('plan');
}

// ── ③ 事業計画ドラフト生成 ───────────────────────────────────
async function doPlan() {
  if (!_selectedSubsidy) return;
  const desc = document.getElementById('plan-business-desc').value.trim();
  if (!desc) { showErr('plan-error', '事業内容を入力してください'); return; }
  hideErr('plan-error');

  const btn = document.getElementById('plan-btn');
  btn.disabled = true;
  document.getElementById('plan-progress').style.display = 'block';
  document.getElementById('plan-result-box').style.display = 'none';

  const fd = new FormData();
  fd.append('subsidy_id', _selectedSubsidy.id);
  fd.append('business_desc', desc);
  fd.append('focus_points', document.getElementById('plan-focus').value.trim());

  try {
    const d = await (await fetch('api/plan', { method: 'POST', headers: csrfHeaders, body: fd })).json();
    if (!d.ok) { showErr('plan-error', d.error); return; }
    _planResult = d.plan;
    renderPlanResult(d.plan);
    document.getElementById('plan-result-box').style.display = 'block';
  } catch (e) {
    showErr('plan-error', '通信エラーが発生しました。しばらく待ってから再試行してください。');
  } finally {
    btn.disabled = false;
    document.getElementById('plan-progress').style.display = 'none';
  }
}

function renderPlanResult(p) {
  const scheduleRows = (p.schedule || []).map(s => `
    <tr><td>${escHtml(s.phase || '')}</td><td>${escHtml(s.period || '')}</td><td>${escHtml(s.content || '')}</td></tr>`).join('');
  const costRows = (p.expected_costs || []).map(c => `
    <tr><td>${escHtml(c.item || '')}</td><td>${escHtml(c.estimate || '')}</td><td>${escHtml(c.note || '')}</td></tr>`).join('');
  const tips = (p.application_tips || []).map(x => `<li>${escHtml(x)}</li>`).join('');

  document.getElementById('plan-result').innerHTML = `
    <h3 class="plan-title">${escHtml(p.title || '')}</h3>
    <div class="plan-section"><h4>事業概要</h4><p>${escHtml(p.overview || '')}</p></div>
    <div class="plan-section"><h4>現状の課題・背景</h4><p>${escHtml(p.current_issues || '')}</p></div>
    <div class="plan-section"><h4>解決策・実施内容</h4><p>${escHtml(p.solution || '')}</p></div>
    <div class="plan-section">
      <h4>実施スケジュール</h4>
      <table class="plan-table"><thead><tr><th>フェーズ</th><th>期間</th><th>内容</th></tr></thead><tbody>${scheduleRows}</tbody></table>
    </div>
    <div class="plan-section">
      <h4>必要経費（概算）</h4>
      <table class="plan-table"><thead><tr><th>項目</th><th>概算金額</th><th>補足</th></tr></thead><tbody>${costRows}</tbody></table>
    </div>
    <div class="plan-section"><h4>期待される効果</h4><p>${escHtml(p.expected_effects || '')}</p></div>
    <div class="plan-section"><h4>申請のポイント</h4><ul>${tips}</ul></div>`;
}

function planToText(p) {
  const lines = [];
  lines.push(`■ ${p.title || ''}`, '');
  lines.push('【事業概要】', p.overview || '', '');
  lines.push('【現状の課題・背景】', p.current_issues || '', '');
  lines.push('【解決策・実施内容】', p.solution || '', '');
  lines.push('【実施スケジュール】');
  (p.schedule || []).forEach(s => lines.push(`・${s.phase || ''}（${s.period || ''}）: ${s.content || ''}`));
  lines.push('');
  lines.push('【必要経費（概算）】');
  (p.expected_costs || []).forEach(c => lines.push(`・${c.item || ''}: ${c.estimate || ''}（${c.note || ''}）`));
  lines.push('');
  lines.push('【期待される効果】', p.expected_effects || '', '');
  lines.push('【申請のポイント】');
  (p.application_tips || []).forEach(t => lines.push(`・${t}`));
  return lines.join('\n');
}

function copyPlan() {
  if (!_planResult) return;
  navigator.clipboard.writeText(planToText(_planResult));
}

function downloadPlan() {
  if (!_planResult) return;
  const blob = new Blob([planToText(_planResult)], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = '事業計画ドラフト.txt';
  a.click();
  URL.revokeObjectURL(url);
}
