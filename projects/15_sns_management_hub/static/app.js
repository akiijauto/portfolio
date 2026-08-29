/* SNS統合管理ツール JavaScript */

const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const csrfHeaders = { 'X-CSRFToken': csrfToken };
// nginx等でパスプレフィックス配下（例: /sns-management-hub）に置かれている場合、
// 末尾スラッシュなしのURLだと相対パス指定がプレフィックスを失って解決されるバグを
// 防ぐため、現在のpathnameを基準にAPIパスを組み立てる。
const API_BASE = window.location.pathname.endsWith('/')
  ? window.location.pathname
  : window.location.pathname + '/';
const _fetch = window.fetch.bind(window);
window.fetch = function(url, options) {
  if (typeof url === 'string' && !/^([a-z]+:)?\/\//i.test(url) && !url.startsWith('/')) {
    url = API_BASE + url;
  }
  return _fetch(url, options);
};

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                  .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function showErr(id, msg) { const el=document.getElementById(id); el.textContent=msg; el.style.display='block'; }
function hideErr(id) { document.getElementById(id).style.display='none'; }

const TAB_ORDER = ['theme', 'hashtag', 'variation', 'calendar', 'analytics'];
function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelectorAll('.tab')[TAB_ORDER.indexOf(name)].classList.add('active');
  if (name === 'calendar') loadPosts();
  if (name === 'analytics') { loadAnalytics(); loadHashtagRanking(); }
}

// ── ① テーマ提案 ──────────────────────────────────────────────
async function doSuggest() {
  const industry = document.getElementById('th-industry').value.trim();
  const target   = document.getElementById('th-target').value.trim();
  const count    = document.getElementById('th-count').value;
  const btn      = document.getElementById('th-btn');
  if (!industry || !target) { showErr('th-error', '業界とターゲットを入力してください'); return; }
  hideErr('th-error');
  btn.disabled = true; btn.textContent = '提案中…';

  const fd = new FormData();
  fd.append('industry', industry); fd.append('target', target); fd.append('count', count);
  const d = await (await fetch('suggest', { method:'POST', headers:csrfHeaders, body:fd })).json();
  btn.disabled = false; btn.textContent = '💡 テーマを提案する';
  if (!d.ok) { showErr('th-error', d.error); return; }

  const hot = new Set(d.hot || []);
  document.getElementById('th-grid').innerHTML = (d.topics || []).map(topic => `
    <span class="ht-chip" onclick="useTheme(${JSON.stringify(topic).replace(/"/g, '&quot;')})">
      ${hot.has(topic) ? '🔥 ' : ''}${escHtml(topic)}
    </span>
  `).join('');
  document.getElementById('th-result').style.display = 'block';
}

function useTheme(topic) {
  document.getElementById('var-topic').value = topic;
  switchTab('variation');
}

// ── ② ハッシュタグ ─────────────────────────────────────────────
let _allHashtags = [];

async function doHashtags() {
  const topic = document.getElementById('ht-topic').value.trim();
  const sns   = document.getElementById('ht-sns').value;
  const ind   = document.getElementById('ht-industry').value.trim();
  const btn   = document.getElementById('ht-btn');
  if (!topic) { showErr('ht-error', 'テーマを入力してください'); return; }
  hideErr('ht-error');
  btn.disabled = true; btn.textContent = '生成中…';

  const fd = new FormData();
  fd.append('topic', topic); fd.append('sns_type', sns); fd.append('industry', ind);
  const d = await (await fetch('hashtags', { method:'POST', headers:csrfHeaders, body:fd })).json();
  btn.disabled = false; btn.textContent = '🏷 ハッシュタグを生成する';
  if (!d.ok) { showErr('ht-error', d.error); return; }

  _allHashtags = d.hashtags || [];
  document.getElementById('ht-result-title').textContent =
    `${sns}向け ハッシュタグ (${_allHashtags.length}個)`;
  document.getElementById('ht-strategy').textContent = d.strategy || '';
  document.getElementById('ht-grid').innerHTML = _allHashtags.map(h =>
    `<span class="ht-chip" onclick="toggleTag(this)">${escHtml(h)}</span>`
  ).join('');
  document.getElementById('ht-plain').textContent = _allHashtags.join(' ');
  document.getElementById('ht-result').style.display = 'block';
}

function toggleTag(el) {
  el.style.background = el.dataset.sel === '1' ? '' : '#fce7f3';
  el.dataset.sel = el.dataset.sel === '1' ? '0' : '1';
}

function copyHashtags() {
  const selected = [...document.querySelectorAll('.ht-chip[data-sel="1"]')];
  const text = selected.length
    ? selected.map(el => el.textContent.trim()).join(' ')
    : _allHashtags.join(' ');
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector('[onclick="copyHashtags()"]');
    btn.textContent = '✅ コピー完了';
    setTimeout(() => { btn.textContent = '📋 コピー'; }, 2000);
  });
}

// ── ③ バリエーション・画像プロンプト ────────────────────────────
async function doVariations() {
  const topic = document.getElementById('var-topic').value.trim();
  const sns   = document.getElementById('var-sns').value;
  const tone  = document.getElementById('var-tone').value;
  const btn   = document.getElementById('var-btn');
  if (!topic) { showErr('var-error', 'テーマを入力してください'); return; }
  hideErr('var-error');
  btn.disabled = true; btn.textContent = '生成中…';

  const fd = new FormData();
  fd.append('topic', topic); fd.append('sns_type', sns); fd.append('tone', tone);
  const d = await (await fetch('variations', { method:'POST', headers:csrfHeaders, body:fd })).json();
  btn.disabled = false; btn.textContent = '✍️ 3つのバリエーションを生成';
  if (!d.ok) { showErr('var-error', d.error); return; }

  document.getElementById('var-grid').innerHTML = (d.variations || []).map((v, i) => `
    <div class="var-card" onclick="selectVar(${i})" data-idx="${i}">
      <div><span class="var-angle">${escHtml(v.angle)}</span></div>
      <div class="var-body">${escHtml(v.post)}</div>
      <div class="var-footer">
        <span class="var-select-label">クリックで選択</span>
        <span class="var-len">${v.post.length}文字</span>
        <button class="copy-chip" onclick="event.stopPropagation(); copyVar(this, ${i})">コピー</button>
      </div>
    </div>
  `).join('');
  document.getElementById('var-results').style.display = 'block';
  document.getElementById('save-cal-success').style.display = 'none';
  document.getElementById('img-result').style.display = 'none';
  hideErr('img-error');

  // store posts for copy / save
  window._varPosts = (d.variations || []).map(v => v.post);
  window._selectedVarIdx = null;
}

function copyVar(btn, idx) {
  navigator.clipboard.writeText(window._varPosts[idx] || '').then(() => {
    btn.textContent = '✅';
    setTimeout(() => { btn.textContent = 'コピー'; }, 1800);
  });
}

function selectVar(idx) {
  window._selectedVarIdx = idx;
  document.querySelectorAll('#var-grid .var-card').forEach(el => {
    el.classList.toggle('selected', Number(el.dataset.idx) === idx);
  });
}

async function doImagePrompt() {
  hideErr('img-error');
  const idx = window._selectedVarIdx;
  if (idx === null || idx === undefined) {
    showErr('img-error', 'バリエーションを1つ選択してください'); return;
  }
  const btn = document.getElementById('img-btn');
  btn.disabled = true; btn.textContent = '生成中…';

  const fd = new FormData();
  fd.append('post_text', window._varPosts[idx]);
  fd.append('sns_type', document.getElementById('var-sns').value);
  const d = await (await fetch('image_prompt', { method:'POST', headers:csrfHeaders, body:fd })).json();
  btn.disabled = false; btn.textContent = '🎨 画像プロンプトを生成';
  if (!d.ok) { showErr('img-error', d.error); return; }

  const el = document.getElementById('img-result');
  el.textContent = d.image_prompt;
  el.style.display = 'block';
}

// ── ③→④ 投稿カレンダーへ保存 ─────────────────────────────────
async function saveSelectedToCalendar() {
  hideErr('save-cal-error');
  document.getElementById('save-cal-success').style.display = 'none';

  const idx = window._selectedVarIdx;
  if (idx === null || idx === undefined) {
    showErr('save-cal-error', 'バリエーションを1つ選択してください'); return;
  }
  const postText = window._varPosts[idx];
  const topic    = document.getElementById('var-topic').value.trim();
  const sns      = document.getElementById('var-sns').value;
  const scheduledLocal = document.getElementById('cal-scheduled-at').value;
  const scheduledAt = scheduledLocal ? new Date(scheduledLocal).toISOString() : '';
  const linkUrl = document.getElementById('cal-url').value.trim();

  const selectedTags = [...document.querySelectorAll('.ht-chip[data-sel="1"]')].map(el => el.textContent.trim());
  const hashtags = selectedTags.join(' ');

  const btn = document.getElementById('save-cal-btn');
  btn.disabled = true; btn.textContent = '保存中…';

  const fd = new FormData();
  fd.append('topic', topic); fd.append('sns_type', sns); fd.append('post_text', postText);
  fd.append('hashtags', hashtags); fd.append('scheduled_at', scheduledAt); fd.append('url', linkUrl);
  const d = await (await fetch('save_to_calendar', { method:'POST', headers:csrfHeaders, body:fd })).json();
  btn.disabled = false; btn.textContent = '📅 投稿カレンダーに保存';
  if (!d.ok) { showErr('save-cal-error', d.error); return; }

  const el = document.getElementById('save-cal-success');
  el.textContent = '✅ 投稿カレンダーに保存しました（④タブで確認できます）';
  el.style.display = 'block';
}

// ── ④ 投稿カレンダー管理 ─────────────────────────────────────
const snsCls = s => s === 'Instagram' ? 'sns-instagram' : s === 'Twitter' ? 'sns-twitter' : 'sns-line';
const stsCls = s => s === '承認済み' ? 'status-approved' : s === '下書き' ? 'status-draft' : 'status-other';

function fmtDate(iso, now) {
  if (!iso) return '—';
  const dt = new Date(iso);
  const past = dt < now;
  const today = dt.toDateString() === now.toDateString();
  const str = dt.toLocaleDateString('ja-JP', {month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'});
  const cls = today ? 'date-today' : past ? 'date-past' : '';
  return cls ? `<span class="${cls}">${str}</span>` : str;
}

function toLocalInputValue(iso) {
  if (!iso) return '';
  const dt = new Date(iso);
  const pad = n => String(n).padStart(2, '0');
  return `${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
}

async function loadPosts() {
  const d = await (await fetch('posts')).json();
  if (!d.ok) return;

  if (d.warning) {
    document.getElementById('posts-warning').innerHTML =
      `⚠️ ${escHtml(d.warning)}<br>` +
      `設定方法: Notion Integrationを作成してカレンダー用データベースに招待し、` +
      `.env に <code>NOTION_TOKEN</code> と <code>NOTION_DATABASE_ID</code> を設定してサーバーを再起動してください。<br>` +
      `※ ①〜③の生成機能は設定不要でそのままお使いいただけます。`;
    document.getElementById('posts-warning').style.display = 'block';
  }

  if (!d.posts || !d.posts.length) {
    document.getElementById('posts-empty').style.display = 'block';
    document.getElementById('posts-wrap').style.display = 'none';
    return;
  }

  const now = new Date();
  const upcoming = d.posts.filter(p => p.scheduled && new Date(p.sched_raw) >= now).length;
  const draft    = d.posts.filter(p => p.status === '下書き').length;
  document.getElementById('posts-stats').innerHTML = `
    <span>📅 合計 <strong>${d.posts.length}</strong> 件</span>
    <span>🔜 今後 <strong>${upcoming}</strong> 件</span>
    <span>📝 下書き <strong>${draft}</strong> 件</span>
  `;

  document.getElementById('posts-tbody').innerHTML = d.posts.map((p, i) => {
    const actions = [];
    if (p.status === '下書き') {
      actions.push(`<input type="datetime-local" id="sched-${i}" value="${toLocalInputValue(p.sched_raw)}" style="width:150px;">`);
      actions.push(`<button class="copy-chip" onclick="schedulePost('${p.id}', ${i})">承認して予約</button>`);
    } else if (p.status === '承認済み') {
      actions.push(`<input type="datetime-local" id="sched-${i}" value="${toLocalInputValue(p.sched_raw)}" style="width:150px;">`);
      actions.push(`<button class="copy-chip" onclick="editSchedule('${p.id}', ${i})">予約更新</button>`);
      actions.push(`<button class="copy-chip" onclick="cancelSchedule('${p.id}')">予約取消</button>`);
      actions.push(`<button class="copy-chip" onclick="postDiscord('${p.id}')">Discordへ投稿</button>`);
      if (p.sns === 'Twitter') {
        actions.push(`<button class="copy-chip" onclick="postTwitter('${p.id}')">Twitterへ投稿</button>`);
      }
    }
    actions.push(`<button class="copy-chip" onclick="deletePost('${p.id}')">削除</button>`);

    return `
    <tr>
      <td>${fmtDate(p.sched_raw, now)}</td>
      <td><span class="sns-pill ${snsCls(p.sns)}">${escHtml(p.sns)}</span></td>
      <td>${escHtml(p.title)}</td>
      <td style="max-width:240px; white-space:pre-wrap;">${escHtml(p.content.slice(0, 100))}${p.content.length > 100 ? '…' : ''}</td>
      <td><span class="status-pill ${stsCls(p.status)}">${escHtml(p.status)}</span></td>
      <td><div class="btn-row" style="margin-top:0; gap:6px;">${actions.join('')}</div></td>
    </tr>`;
  }).join('');
  document.getElementById('posts-wrap').style.display = 'block';
  document.getElementById('posts-empty').style.display = 'none';
}

async function _postAction(url, fd, successMsg) {
  const d = await (await fetch(url, { method:'POST', headers:csrfHeaders, body: fd || new FormData() })).json();
  if (!d.ok) { alert(d.error || '操作に失敗しました'); return; }
  loadPosts();
}

function schedulePost(id, i) {
  const local = document.getElementById(`sched-${i}`).value;
  const fd = new FormData();
  if (local) fd.append('scheduled_at', new Date(local).toISOString());
  _postAction(`schedule_post/${id}`, fd);
}

function editSchedule(id, i) {
  const local = document.getElementById(`sched-${i}`).value;
  const fd = new FormData();
  if (local) fd.append('scheduled_at', new Date(local).toISOString());
  _postAction(`edit_schedule/${id}`, fd);
}

function cancelSchedule(id) { _postAction(`cancel_schedule/${id}`); }
function postDiscord(id)    { _postAction(`post_discord/${id}`); }
function postTwitter(id)    { _postAction(`post_twitter/${id}`); }
function deletePost(id)     { if (confirm('削除しますか？')) _postAction(`delete/${id}`); }

// ── ⑤ 効果分析 ──────────────────────────────────────────────
async function doEngage() {
  hideErr('eg-error');
  document.getElementById('eg-success').style.display = 'none';

  const topic = document.getElementById('eg-topic').value.trim();
  if (!topic) { showErr('eg-error', 'トピックを入力してください'); return; }

  const fd = new FormData();
  fd.append('topic', topic);
  fd.append('sns_type', document.getElementById('eg-sns').value);
  fd.append('likes', document.getElementById('eg-likes').value);
  fd.append('comments', document.getElementById('eg-comments').value);
  fd.append('reach', document.getElementById('eg-reach').value);

  const btn = document.getElementById('eg-btn');
  btn.disabled = true; btn.textContent = '記録中…';
  const d = await (await fetch('engage', { method:'POST', headers:csrfHeaders, body:fd })).json();
  btn.disabled = false; btn.textContent = '📊 記録する';
  if (!d.ok) { showErr('eg-error', d.error); return; }

  document.getElementById('eg-success').style.display = 'block';
  loadAnalytics();
}

async function loadAnalytics() {
  const d = await (await fetch('analytics')).json();
  if (!d.ok) return;
  const data = d.data || [];
  if (!data.length) {
    document.getElementById('an-empty').style.display = 'block';
    document.getElementById('an-table').style.display = 'none';
    return;
  }
  document.getElementById('an-tbody').innerHTML = data.map(r => `
    <tr>
      <td>${escHtml(r.topic)}</td>
      <td><span class="sns-pill ${snsCls(r.sns_type)}">${escHtml(r.sns_type)}</span></td>
      <td>${r.posts}</td>
      <td>${r.avg_likes}</td>
      <td>${r.avg_comments}</td>
      <td>${r.avg_reach}</td>
      <td>${r.score}</td>
    </tr>
  `).join('');
  document.getElementById('an-table').style.display = '';
  document.getElementById('an-empty').style.display = 'none';
}

async function loadHashtagRanking() {
  const d = await (await fetch('hashtag_ranking')).json();
  if (!d.ok) return;
  const ranking = d.ranking || [];
  if (!ranking.length) {
    document.getElementById('hr-empty').style.display = 'block';
    document.getElementById('hr-grid').innerHTML = '';
    return;
  }
  document.getElementById('hr-empty').style.display = 'none';
  document.getElementById('hr-grid').innerHTML = ranking.map(([tag, count]) =>
    `<span class="ht-chip">${escHtml(tag)} <strong>${count}</strong></span>`
  ).join('');
}
