/* 広告文生成ツール JavaScript */

const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const csrfHeaders = { 'X-CSRFToken': csrfToken };

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                  .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function showErr(id, msg) { const el=document.getElementById(id); el.textContent=msg; el.style.display='block'; }
function hideErr(id) { document.getElementById(id).style.display='none'; }

function updateUspCounter() {
  const len = document.getElementById('usp').value.length;
  document.getElementById('usp-counter').textContent = `${len} / 300文字`;
}

const TAB_ORDER = ['input', 'result'];
function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelectorAll('.tab')[TAB_ORDER.indexOf(name)].classList.add('active');
}

// ── 生成 ──────────────────────────────────────────────────────
let _data = null;

async function doGenerate() {
  const btn = document.getElementById('gen-btn');
  const product  = document.getElementById('product').value.trim();
  const target   = document.getElementById('target').value.trim();
  const usp      = document.getElementById('usp').value.trim();
  if (!product || !target || !usp) {
    showErr('gen-error', '商品名・ターゲット・強みはすべて必須です'); return;
  }
  hideErr('gen-error');
  btn.disabled = true;
  document.getElementById('progress-wrap').style.display = 'block';
  animateProgress();

  const fd = new FormData();
  fd.append('product',  product);
  fd.append('target',   target);
  fd.append('usp',      usp);
  fd.append('industry', document.getElementById('industry').value.trim());
  fd.append('goal',     document.querySelector('input[name="goal"]:checked')?.value || 'リード獲得');

  const d = await (await fetch('generate', { method:'POST', headers:csrfHeaders, body:fd })).json();
  btn.disabled = false;
  document.getElementById('progress-wrap').style.display = 'none';
  document.getElementById('progress-fill').style.width = '0%';

  if (!d.ok) { showErr('gen-error', d.error); return; }
  _data = d;
  renderResults(d);
  switchTab('result');
}

let _timer;
function animateProgress() {
  let pct = 0;
  const msgs = ['Google広告を生成中…', 'Meta広告を生成中…', 'LINE広告を生成中…', 'A/Bバリエーションを追加中…'];
  let mi = 0;
  document.getElementById('progress-text').textContent = msgs[0];
  clearInterval(_timer);
  _timer = setInterval(() => {
    pct = Math.min(pct + 2, 90);
    document.getElementById('progress-fill').style.width = pct + '%';
    if (pct % 22 === 0 && mi < msgs.length - 1) { mi++; document.getElementById('progress-text').textContent = msgs[mi]; }
  }, 300);
}

// ── 描画 ──────────────────────────────────────────────────────
function renderResults(d) {
  document.getElementById('result-empty').style.display = 'none';
  document.getElementById('result-wrap').style.display = 'block';

  // Google
  const g = d.google || {};
  const headlines = g.headlines || [];
  document.getElementById('g-headlines').innerHTML = headlines.map((h, i) => {
    const len = h.length;
    return `<div class="headline-chip">
      <span class="hl-text">${escHtml(h)}</span>
      <span class="hl-len ${len > 30 ? 'over' : ''}">${len}字</span>
      <button class="copy-mini" onclick="copyText(this,'${escHtml(h).replace(/'/g,'\\'+'\'').replace(/"/g,'\\"')}')">コピー</button>
    </div>`;
  }).join('');
  document.getElementById('g-descriptions').innerHTML = (g.descriptions || []).map(d2 =>
    descRow(d2, 90)
  ).join('');
  if (d.ab_variants?.google_alt_headline) {
    document.getElementById('g-ab').innerHTML = `
      <div class="ab-label">🔀 A/Bバリエーション見出し</div>
      <div class="ab-text">${escHtml(d.ab_variants.google_alt_headline)}</div>`;
  }

  // Meta
  const m = d.meta || {};
  document.getElementById('m-primary').textContent  = m.primary_text || '';
  document.getElementById('m-headline').textContent = m.headline || '';
  document.getElementById('m-desc').textContent     = m.description || '';
  document.getElementById('m-cta').innerHTML = (m.cta_options || []).map(c =>
    `<span class="cta-tag">${escHtml(c)}</span>`
  ).join(' ');
  // wrap cta in div
  const ctaEl = document.getElementById('m-cta');
  ctaEl.className = 'cta-tags';
  if (d.ab_variants?.meta_alt_primary) {
    document.getElementById('m-ab').innerHTML = `
      <div class="ab-label">🔀 A/Bバリエーション本文</div>
      <div class="ab-text">${escHtml(d.ab_variants.meta_alt_primary)}</div>`;
  }

  // LINE
  const l = d.line || {};
  document.getElementById('l-title').textContent = l.title || '';
  document.getElementById('l-text').textContent  = l.text  || '';

  // Points
  document.getElementById('copy-points').textContent = d.copy_points || '';
}

function descRow(text, limit) {
  const len = text.length;
  return `<div class="copy-line">
    <div class="copy-line-text">${escHtml(text)}</div>
    <span class="copy-line-len ${len > limit ? 'over' : ''}">${len}字</span>
    <button class="copy-mini" onclick="copyText(this,${JSON.stringify(text)})">コピー</button>
  </div>`;
}

function copyText(btn, text) {
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.textContent; btn.textContent = '✅';
    setTimeout(() => { btn.textContent = orig; }, 1600);
  });
}

// ── ダウンロード ──────────────────────────────────────────────
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
function downloadAll() {
  if (!_data) return;
  const product = document.getElementById('product').value.trim() || 'ad';
  const g = _data.google || {}, m = _data.meta || {}, l = _data.line || {};
  const text = [
    '【Google検索広告】',
    '見出し:', ...(g.headlines || []), '',
    '説明文:', ...(g.descriptions || []), '',
    '【Meta広告】',
    `プライマリテキスト:\n${m.primary_text || ''}`,
    `見出し: ${m.headline || ''}`,
    `説明文: ${m.description || ''}`,
    `CTA案: ${(m.cta_options || []).join(' / ')}`, '',
    '【LINE広告】',
    `タイトル: ${l.title || ''}`,
    `テキスト:\n${l.text || ''}`, '',
    '【このコピーが効果的な理由】',
    _data.copy_points || ''
  ].join('\n');
  downloadText(text, `広告文_${product}_${dateStr()}.txt`);
}

// ── 全コピー ──────────────────────────────────────────────────
function copyAll(platform) {
  if (!_data) return;
  let text = '';
  if (platform === 'google') {
    const g = _data.google || {};
    text = '【見出し】\n' + (g.headlines || []).join('\n') +
           '\n\n【説明文】\n' + (g.descriptions || []).join('\n');
  } else if (platform === 'meta') {
    const m = _data.meta || {};
    text = `【プライマリテキスト】\n${m.primary_text || ''}\n\n【見出し】\n${m.headline || ''}\n\n【説明文】\n${m.description || ''}\n\n【CTA】\n${(m.cta_options || []).join(' / ')}`;
  } else if (platform === 'line') {
    const l = _data.line || {};
    text = `【タイトル】\n${l.title || ''}\n\n【テキスト】\n${l.text || ''}`;
  }
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector(`[onclick="copyAll('${platform}')"]`);
    const orig = btn.textContent; btn.textContent = '✅ コピー済み';
    setTimeout(() => { btn.textContent = orig; }, 2000);
  });
}
