/* 問い合わせ管理CRM JavaScript */

const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const csrfHeaders = { 'X-CSRFToken': csrfToken };

const STATUSES = ['新規', '連絡済み', '商談中', '成約', '失注'];

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                  .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function showErr(id, msg) { const el=document.getElementById(id); el.textContent=msg; el.style.display='block'; }
function hideErr(id) { document.getElementById(id).style.display='none'; }
function showOk(id, msg) {
  const el=document.getElementById(id); el.textContent=msg; el.style.display='block';
  setTimeout(() => { el.style.display='none'; }, 2500);
}

const TAB_ORDER = ['new', 'list', 'reply'];
function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelectorAll('.tab')[TAB_ORDER.indexOf(name)].classList.add('active');
  if (name === 'list') loadList();
  if (name === 'reply') loadReplyOptions();
}

// ── 統計 ──────────────────────────────────────────────────────
async function loadStats() {
  const d = await (await fetch('api/stats')).json();
  if (!d.ok) return;
  document.getElementById('stat-total').innerHTML = d.total + '<span class="hero-unit">件</span>';
  document.getElementById('stat-new').innerHTML = (d.counts['新規'] || 0) + '<span class="hero-unit">件</span>';
  document.getElementById('stat-progress').innerHTML =
    ((d.counts['連絡済み'] || 0) + (d.counts['商談中'] || 0)) + '<span class="hero-unit">件</span>';
  document.getElementById('stat-won').innerHTML = (d.counts['成約'] || 0) + '<span class="hero-unit">件</span>';
}

// ── 新規登録 ──────────────────────────────────────────────────
async function doCreate() {
  const btn = document.getElementById('create-btn');
  const company = document.getElementById('in-company').value.trim();
  if (!company) { showErr('create-error', '会社名・お名前は必須です'); return; }
  hideErr('create-error');
  btn.disabled = true;

  const fd = new FormData();
  fd.append('company', company);
  fd.append('contact_name', document.getElementById('in-contact').value.trim());
  fd.append('email', document.getElementById('in-email').value.trim());
  fd.append('phone', document.getElementById('in-phone').value.trim());
  fd.append('source', document.querySelector('input[name="source"]:checked')?.value || '');
  fd.append('content', document.getElementById('in-content').value.trim());

  const d = await (await fetch('api/inquiries', { method:'POST', headers:csrfHeaders, body:fd })).json();
  btn.disabled = false;

  if (!d.ok) { showErr('create-error', d.error); return; }

  // フォームをリセット
  document.getElementById('in-company').value = '';
  document.getElementById('in-contact').value = '';
  document.getElementById('in-email').value = '';
  document.getElementById('in-phone').value = '';
  document.getElementById('in-content').value = '';

  showOk('create-success', `「${d.inquiry.company}」を登録しました`);
  loadStats();
}

// ── 一覧・進捗管理 ────────────────────────────────────────────
let _currentFilter = '';

function setFilter(status) {
  _currentFilter = status;
  document.querySelectorAll('.filter-chip').forEach(el => {
    el.classList.toggle('active', el.dataset.status === status);
  });
  loadList();
}

async function loadList() {
  const url = _currentFilter ? `api/inquiries?status=${encodeURIComponent(_currentFilter)}` : 'api/inquiries';
  const d = await (await fetch(url)).json();
  if (!d.ok) return;

  document.getElementById('list-empty').style.display = d.inquiries.length ? 'none' : 'block';
  document.getElementById('inquiry-list').innerHTML = d.inquiries.map(renderCard).join('');
  loadStats();
}

function renderCard(inq) {
  const statusOptions = STATUSES.map(s =>
    `<option value="${s}" ${s === inq.status ? 'selected' : ''}>${s}</option>`
  ).join('');
  const metaParts = [];
  if (inq.contact_name) metaParts.push(escHtml(inq.contact_name));
  if (inq.email) metaParts.push(escHtml(inq.email));
  if (inq.phone) metaParts.push(escHtml(inq.phone));
  if (inq.source) metaParts.push(escHtml(inq.source));
  metaParts.push('登録: ' + inq.created_at);

  return `
  <div class="inquiry-card" data-id="${inq.id}">
    <div class="inquiry-top">
      <div>
        <div class="inquiry-company">${escHtml(inq.company)}</div>
        <div class="inquiry-meta">${metaParts.join(' ・ ')}</div>
      </div>
      <span class="status-badge status-${inq.status}">${inq.status}</span>
    </div>
    ${inq.content ? `<div class="inquiry-content">${escHtml(inq.content)}</div>` : ''}
    <div class="inquiry-actions">
      <select class="status-select" onchange="updateStatus(${inq.id}, this.value)">${statusOptions}</select>
      <button class="btn btn-sm btn-delete" onclick="deleteInquiry(${inq.id})">削除</button>
    </div>
    <div class="inquiry-memo">
      <label>対応メモ</label>
      <div class="inquiry-memo-row">
        <textarea rows="2" id="memo-${inq.id}" placeholder="対応履歴・次のアクションなど">${escHtml(inq.memo || '')}</textarea>
        <button class="btn btn-sm btn-save-memo" onclick="saveMemo(${inq.id})">保存</button>
      </div>
    </div>
  </div>`;
}

async function updateStatus(id, status) {
  const fd = new FormData();
  fd.append('status', status);
  await fetch(`api/inquiries/${id}/status`, { method:'POST', headers:csrfHeaders, body:fd });
  loadList();
}

async function saveMemo(id) {
  const memo = document.getElementById('memo-' + id).value;
  const fd = new FormData();
  fd.append('memo', memo);
  await fetch(`api/inquiries/${id}/memo`, { method:'POST', headers:csrfHeaders, body:fd });
}

async function deleteInquiry(id) {
  if (!confirm('この案件を削除しますか？')) return;
  await fetch(`api/inquiries/${id}/delete`, { method:'POST', headers:csrfHeaders });
  loadList();
}

// ── AI返信文生成 ──────────────────────────────────────────────
async function loadReplyOptions() {
  const d = await (await fetch('api/inquiries')).json();
  if (!d.ok) return;
  const sel = document.getElementById('reply-inquiry');
  const current = sel.value;
  sel.innerHTML = '<option value="">-- 案件を選択 --</option>' + d.inquiries.map(inq =>
    `<option value="${inq.id}">${escHtml(inq.company)}${inq.contact_name ? ' / ' + escHtml(inq.contact_name) : ''}（${inq.status}）</option>`
  ).join('');
  if (current) sel.value = current;
}

async function doReplyDraft() {
  const btn = document.getElementById('reply-btn');
  const inquiryId = document.getElementById('reply-inquiry').value;
  if (!inquiryId) { showErr('reply-error', '案件を選択してください'); return; }
  hideErr('reply-error');
  btn.disabled = true;
  document.getElementById('reply-progress').style.display = 'block';
  document.getElementById('reply-progress-fill').style.width = '0%';
  let pct = 0;
  const timer = setInterval(() => {
    pct = Math.min(pct + 4, 90);
    document.getElementById('reply-progress-fill').style.width = pct + '%';
  }, 200);

  const fd = new FormData();
  fd.append('inquiry_id', inquiryId);
  fd.append('tone', document.querySelector('input[name="tone"]:checked')?.value || '丁寧（標準）');
  fd.append('purpose', document.getElementById('reply-purpose').value.trim());

  const d = await (await fetch('reply_draft', { method:'POST', headers:csrfHeaders, body:fd })).json();
  clearInterval(timer);
  btn.disabled = false;
  document.getElementById('reply-progress').style.display = 'none';

  if (!d.ok) { showErr('reply-error', d.error); return; }

  document.getElementById('reply-result-box').style.display = 'block';
  document.getElementById('reply-draft').textContent = d.draft;
}

function copyDraft() {
  const text = document.getElementById('reply-draft').textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector('[onclick="copyDraft()"]');
    const orig = btn.textContent; btn.textContent = '✅ コピー済み';
    setTimeout(() => { btn.textContent = orig; }, 2000);
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
function downloadDraft() {
  const text = document.getElementById('reply-draft').textContent;
  const sel = document.getElementById('reply-inquiry');
  const company = (sel.options[sel.selectedIndex]?.text || '返信文').split('（')[0].trim();
  downloadText(text, `返信文_${company}_${dateStr()}.txt`);
}

// ── 初期化 ────────────────────────────────────────────────────
loadStats();
