/* SEO記事生成ツール JavaScript */

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

const TAB_ORDER = ['settings', 'outline', 'article'];
function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelectorAll('.tab')[TAB_ORDER.indexOf(name)].classList.add('active');
}

// ── アウトライン生成 ────────────────────────────────────────────
let _currentOutline = null;

async function doOutline() {
  const kw   = document.getElementById('keyword').value.trim();
  const btn  = document.getElementById('outline-btn');
  if (!kw) { showErr('settings-error', 'キーワードを入力してください'); return; }
  hideErr('settings-error');
  btn.disabled = true; btn.textContent = '生成中…';

  const fd = new FormData();
  fd.append('keyword',           kw);
  fd.append('article_type',     document.getElementById('article_type').value);
  fd.append('tone',             document.getElementById('tone').value);
  fd.append('target_chars',     document.getElementById('target_chars').value);
  fd.append('competitor_context', document.getElementById('competitor_context').value);

  const d = await (await fetch('outline', { method: 'POST', headers: csrfHeaders, body: fd })).json();
  btn.disabled = false; btn.textContent = '📋 アウトラインを生成する';

  if (!d.ok) { showErr('settings-error', d.error); return; }
  _currentOutline = d.outline;
  renderOutline(d.outline, kw);
  switchTab('outline');
}

function renderOutline(ol, kw) {
  document.getElementById('outline-empty').style.display = 'none';
  document.getElementById('outline-wrap').style.display = 'block';
  document.getElementById('outline-title-label').textContent = ol.title || kw + 'の記事';
  document.getElementById('outline-meta-pill').textContent =
    document.getElementById('article_type').value + ' / ' + document.getElementById('target_chars').value + '文字';
  document.getElementById('outline-meta-desc').textContent = ol.meta_desc || '';

  document.getElementById('outline-sections').innerHTML = (ol.sections || []).map((s, i) => `
    <div class="section-card">
      <div class="section-h2">
        <span class="section-num">${i + 1}</span>
        ${escHtml(s.h2)}
      </div>
      <div class="section-purpose">${escHtml(s.purpose || '')}</div>
      ${s.h3s && s.h3s.length
        ? `<div class="section-h3s">${s.h3s.map(h => `<span class="h3-tag">└ ${escHtml(h)}</span>`).join('')}</div>`
        : ''}
    </div>
  `).join('');

  if (ol.faq && ol.faq.length) {
    document.getElementById('outline-faq').innerHTML = `
      <h3>よくある質問（FAQ）セクション</h3>
      ${ol.faq.map(q => `<div class="faq-item">Q. ${escHtml(q)}</div>`).join('')}
    `;
  }
}

// ── 記事本文生成 ────────────────────────────────────────────────
let _rawMarkdown = '';
let _previewMode = false;

async function doGenerate() {
  if (!_currentOutline) { showErr('outline-error', 'アウトラインがありません'); return; }
  const kw  = document.getElementById('keyword').value.trim();
  const btn = document.getElementById('generate-btn');

  btn.disabled = true;
  document.getElementById('progress-wrap').style.display = 'block';
  animateProgress();

  const fd = new FormData();
  fd.append('keyword',     kw);
  fd.append('outline',     JSON.stringify(_currentOutline));
  fd.append('tone',        document.getElementById('tone').value);
  fd.append('target_chars', document.getElementById('target_chars').value);

  const d = await (await fetch('generate', { method: 'POST', headers: csrfHeaders, body: fd })).json();
  btn.disabled = false;
  document.getElementById('progress-wrap').style.display = 'none';
  document.getElementById('progress-fill').style.width = '0%';

  if (!d.ok) { showErr('outline-error', d.error); return; }
  _rawMarkdown = d.article;
  renderArticle(d);
  switchTab('article');
}

let _timer = null;
function animateProgress() {
  let pct = 0;
  const msgs = ['アウトラインを処理中…', 'AIが執筆中…', 'セクションを構成中…', 'SEO最適化を適用中…'];
  let mi = 0;
  document.getElementById('progress-text').textContent = msgs[0];
  _timer = setInterval(() => {
    pct = Math.min(pct + 1.5, 88);
    document.getElementById('progress-fill').style.width = pct + '%';
    if (pct % 25 === 0 && mi < msgs.length - 1) { mi++; document.getElementById('progress-text').textContent = msgs[mi]; }
  }, 400);
}

function renderArticle(d) {
  document.getElementById('article-empty').style.display = 'none';
  document.getElementById('article-wrap').style.display = 'block';
  document.getElementById('article-title-label').textContent =
    (_currentOutline && _currentOutline.title) || document.getElementById('keyword').value;

  const chars = d.char_count || d.article.length;
  const readMin = Math.ceil(chars / 400);
  document.getElementById('char-count-badge').textContent = `${chars.toLocaleString()}文字 / 約${readMin}分`;

  document.getElementById('article-markdown').textContent = d.article;
  document.getElementById('article-preview').innerHTML = markdownToHtml(d.article);

  const kw = document.getElementById('keyword').value;
  const kwCount = (d.article.match(new RegExp(kw.split(/\s+/)[0], 'g')) || []).length;
  document.getElementById('reading-meta').innerHTML = `
    <span>📝 <strong>${chars.toLocaleString()}</strong> 文字</span>
    <span>⏱ 約 <strong>${readMin}</strong> 分で読める</span>
    <span>🔑 キーワード出現: <strong>${kwCount}</strong> 回</span>
    <span>📌 見出し数: <strong>${(d.article.match(/^#{1,3} /gm) || []).length}</strong> 個</span>
  `;
}

function markdownToHtml(md) {
  return md
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^# (.+)$/gm,  '<h1>$1</h1>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^### (.+)$/gm,'<h3>$1</h3>')
    .replace(/^[\-\*] (.+)$/gm, '<li>$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>')
    .replace(/(<li>.*?<\/li>\n?)+/g, s => `<ul>${s}</ul>`)
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(?!<[hup])/gm, '<p>')
    .replace(/(?<![>])$/gm, '</p>')
    .replace(/<p><\/p>/g, '')
    .replace(/<p>(<[hu])/g, '$1')
    .replace(/(<\/[hu][1-3]>)<\/p>/g, '$1');
}

function togglePreview() {
  _previewMode = !_previewMode;
  document.getElementById('article-markdown').style.display = _previewMode ? 'none' : 'block';
  document.getElementById('article-preview').style.display  = _previewMode ? 'block' : 'none';
  document.querySelector('[onclick="togglePreview()"]').textContent =
    _previewMode ? '📝 Markdownを表示' : '👁 プレビュー切替';
}

function copyMarkdown() {
  navigator.clipboard.writeText(_rawMarkdown).then(() => {
    const btn = document.querySelector('[onclick="copyMarkdown()"]');
    btn.textContent = '✅ コピー完了'; setTimeout(() => { btn.textContent = '📋 Markdownをコピー'; }, 2000);
  });
}
function copyPlain() {
  const plain = _rawMarkdown.replace(/^#+\s/gm,'').replace(/\*\*/g,'').replace(/\*/g,'');
  navigator.clipboard.writeText(plain).then(() => {
    const btn = document.querySelector('[onclick="copyPlain()"]');
    btn.textContent = '✅ コピー完了'; setTimeout(() => { btn.textContent = '📄 テキストをコピー'; }, 2000);
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
function downloadMarkdown() {
  const kw = document.getElementById('keyword').value.trim() || 'article';
  downloadText(_rawMarkdown, `記事_${kw}_${dateStr()}.md`);
}
