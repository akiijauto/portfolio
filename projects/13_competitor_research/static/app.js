/* 競合調査ツール JavaScript */

const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const csrfHeaders = { 'X-CSRFToken': csrfToken };

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                  .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function showErr(id, msg) {
  const el = document.getElementById(id);
  el.textContent = msg; el.style.display = 'block';
}
function hideErr(id) { document.getElementById(id).style.display = 'none'; }

const TAB_ORDER = ['search', 'results'];
function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelectorAll('.tab')[TAB_ORDER.indexOf(name)].classList.add('active');
}

// ── ① 検索 ──────────────────────────────────────────────────
async function doSearch() {
  const kw  = document.getElementById('keyword').value.trim();
  const btn = document.getElementById('search-btn');
  if (!kw) { showErr('search-error', 'キーワードを入力してください'); return; }
  hideErr('search-error');
  btn.disabled = true; btn.textContent = '検索中…';
  document.getElementById('url-box').style.display = 'none';

  const fd = new FormData();
  fd.append('keyword', kw);
  const d = await (await fetch('search', { method: 'POST', headers: csrfHeaders, body: fd })).json();
  btn.disabled = false; btn.textContent = '🔍 競合を検索';

  if (!d.ok) { showErr('search-error', d.error); return; }
  renderUrlList(d.urls);
}

function renderUrlList(urls) {
  document.getElementById('url-list').innerHTML = urls.map((url, i) => `
    <div class="url-item">
      <input type="checkbox" id="chk-${i}" checked>
      <span class="url-rank">${i + 1}位</span>
      <span class="url-text" title="${escHtml(url)}">${escHtml(url)}</span>
    </div>
  `).join('');
  document.getElementById('url-box').style.display = 'block';
}

function getCheckedUrls() {
  const items = document.querySelectorAll('#url-list .url-item');
  return [...items]
    .filter((_, i) => document.getElementById(`chk-${i}`)?.checked)
    .map(el => el.querySelector('.url-text').title);
}

// ── ② 分析 ──────────────────────────────────────────────────
async function doAnalyze() {
  const kw   = document.getElementById('keyword').value.trim();
  const urls = getCheckedUrls();
  const btn  = document.getElementById('analyze-btn');
  if (!urls.length) { showErr('analyze-error', 'URLを1件以上選択してください'); return; }
  hideErr('analyze-error');

  btn.disabled = true;
  document.getElementById('progress-wrap').style.display = 'block';
  animateProgress();

  const fd = new FormData();
  fd.append('keyword', kw);
  fd.append('urls', urls.join('\n'));
  const d = await (await fetch('analyze', { method: 'POST', headers: csrfHeaders, body: fd })).json();

  btn.disabled = false;
  document.getElementById('progress-wrap').style.display = 'none';
  document.getElementById('progress-fill').style.width = '0%';

  if (!d.ok) { showErr('analyze-error', d.error); return; }
  renderResults(d);
  switchTab('results');
}

let _progressTimer = null;
function animateProgress() {
  let pct = 0;
  const msgs = ['URLを取得中…', 'ページをスクレイプ中…', 'AIが分析中…', 'レポートを生成中…'];
  let msgIdx = 0;
  document.getElementById('progress-text').textContent = msgs[0];
  _progressTimer = setInterval(() => {
    pct = Math.min(pct + 2, 90);
    document.getElementById('progress-fill').style.width = pct + '%';
    if (pct % 25 === 0 && msgIdx < msgs.length - 1) {
      msgIdx++;
      document.getElementById('progress-text').textContent = msgs[msgIdx];
    }
  }, 400);
}

// ── 結果描画 ──────────────────────────────────────────────────
let _lastAnalysis = '';

function renderResults(d) {
  _lastAnalysis = d.analysis;

  document.getElementById('results-empty').style.display = 'none';
  document.getElementById('results-wrap').style.display = 'block';
  document.getElementById('result-keyword-label').textContent = `「${d.keyword}」競合分析結果`;

  document.getElementById('pages-grid').innerHTML = d.pages.map((p, i) => {
    if (!p.ok) return `
      <div class="page-card page-failed">
        <div class="page-rank">${i+1}位</div>
        <div class="page-domain">取得失敗</div>
        <div class="page-title" style="font-size:10px;color:#dc2626;">${escHtml(p.error || '')}</div>
      </div>`;

    const charLabel = p.char_count > 5000 ? '多め' : p.char_count > 2000 ? '中程度' : '少なめ';
    const charWarn  = p.char_count < 1500;
    const h2Html = p.h2.length
      ? `<details class="page-h2s"><summary>見出し一覧 (${p.h2.length}件)</summary><ul>${p.h2.map(h=>`<li>${escHtml(h)}</li>`).join('')}</ul></details>`
      : '';
    return `
      <div class="page-card">
        <div class="page-rank">${i+1}位</div>
        <div class="page-domain">${escHtml(p.domain)}</div>
        <div class="page-title">${escHtml(p.title)}</div>
        <div class="page-meta">
          <span class="meta-tag ${charWarn ? 'meta-warn' : ''}">${(p.char_count/1000).toFixed(1)}k文字</span>
          <span class="meta-tag">${p.h2.length}個のH2</span>
          ${p.meta_desc ? '' : '<span class="meta-tag meta-warn">meta説明なし</span>'}
        </div>
        ${h2Html}
      </div>`;
  }).join('');

  // Markdown → HTML (簡易変換)
  const html = markdownToHtml(d.analysis);
  document.getElementById('ai-report').innerHTML = html;
}

function markdownToHtml(md) {
  return md
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^### (.+)$/gm, '<h3 style="font-size:14px;font-weight:700;margin:12px 0 4px;color:#047857">$3</h3>'.replace('$3','$1'))
    .replace(/^[\-\*] (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>(\n|$))+/g, m => `<ul>${m}</ul>`)
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}

function copyAnalysis() {
  navigator.clipboard.writeText(_lastAnalysis).then(() => {
    const btn = document.querySelector('[onclick="copyAnalysis()"]');
    btn.textContent = '✅ コピー完了';
    setTimeout(() => { btn.textContent = '📋 レポートをコピー'; }, 2000);
  });
}

function downloadText(text, filename) {
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
function dateStr() {
  const d = new Date();
  return `${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}${String(d.getDate()).padStart(2,'0')}`;
}
function downloadReport() {
  const kw = document.getElementById('keyword').value.trim() || 'report';
  downloadText(_lastAnalysis, `競合分析_${kw}_${dateStr()}.txt`);
}
