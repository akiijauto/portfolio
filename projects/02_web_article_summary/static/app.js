/* Web記事要約ツール JavaScript */
document.getElementById('url-input').addEventListener('keydown', e => { if (e.key === 'Enter') doSummarize(); });

async function doSummarize() {
  const url = document.getElementById('url-input').value.trim();
  if (!url) { showError('URLを入力してください'); return; }
  const btn = document.getElementById('summarize-btn');
  btn.disabled = true;
  document.getElementById('progress').style.display  = 'block';
  document.getElementById('results').style.display   = 'none';
  document.getElementById('error-box').style.display = 'none';

  const fd = new FormData(); fd.append('url', url);
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  const res  = await fetch('summarize', { method: 'POST', headers: { 'X-CSRFToken': csrfToken }, body: fd });
  const data = await res.json();
  document.getElementById('progress').style.display = 'none';
  btn.disabled = false;
  if (!data.ok) { showError(data.error); return; }

  const d = data.data;
  const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  document.getElementById('article-title').textContent = d.title || '（タイトル不明）';
  document.getElementById('article-url').textContent   = d.url;
  document.getElementById('list-3').innerHTML = d.summary_3.map(s => `<li>${esc(s)}</li>`).join('');
  document.getElementById('list-5').innerHTML = d.summary_5.map(s => `<li>${esc(s)}</li>`).join('');
  document.getElementById('sns-text').textContent = d.sns;
  document.getElementById('results').style.display = 'block';
  document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
}

document.getElementById('search-input').addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

async function doSearch() {
  const keyword = document.getElementById('search-input').value.trim();
  if (!keyword) { showSearchError('検索キーワードを入力してください'); return; }
  const btn = document.getElementById('search-btn');
  btn.disabled = true;
  document.getElementById('search-progress').style.display  = 'block';
  document.getElementById('search-error-box').style.display = 'none';
  document.getElementById('search-results').innerHTML = '';

  const fd = new FormData(); fd.append('keyword', keyword);
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  const res  = await fetch('search', { method: 'POST', headers: { 'X-CSRFToken': csrfToken }, body: fd });
  const data = await res.json();
  document.getElementById('search-progress').style.display = 'none';
  btn.disabled = false;
  if (!data.ok) { showSearchError(data.error); return; }

  const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const list = document.getElementById('search-results');
  list.innerHTML = data.results.map((r, i) => `
    <li class="search-result-item">
      <div class="search-result-title">${esc(r.title)}</div>
      <div class="search-result-url">${esc(r.url)}</div>
      <div class="search-result-snippet">${esc(r.snippet)}</div>
      <button class="btn-secondary" onclick="selectSearchResult(${i})">このURLを要約する</button>
    </li>`).join('');
  window._searchResults = data.results;
}

function selectSearchResult(i) {
  const r = window._searchResults[i];
  document.getElementById('url-input').value = r.url;
  doSummarize();
  document.getElementById('url-input').scrollIntoView({ behavior: 'smooth' });
}

function showSearchError(msg) {
  const el = document.getElementById('search-error-box');
  el.textContent = '❌ ' + msg; el.style.display = 'block';
}

function showError(msg) {
  const el = document.getElementById('error-box');
  el.textContent = '❌ ' + msg; el.style.display = 'block';
}

async function copyText(id) {
  const el   = document.getElementById(id);
  const text = el.tagName === 'UL'
    ? [...el.querySelectorAll('li')].map(li => li.textContent).join('\n')
    : el.textContent;
  await navigator.clipboard.writeText(text);
  const btn = el.closest('.card').querySelector('.copy-btn');
  btn.textContent = '✅ コピー済み'; setTimeout(() => btn.textContent = 'コピー', 2000);
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
function downloadSummary() {
  const title = document.getElementById('article-title').textContent;
  const url   = document.getElementById('article-url').textContent;
  const list3 = [...document.querySelectorAll('#list-3 li')].map(li => '・' + li.textContent);
  const list5 = [...document.querySelectorAll('#list-5 li')].map(li => '・' + li.textContent);
  const sns   = document.getElementById('sns-text').textContent;
  const text = [
    title, url, '',
    '【3行要約】', ...list3, '',
    '【5行要約】', ...list5, '',
    '【SNS投稿用】', sns
  ].join('\n');
  downloadText(text, `記事要約_${dateStr()}.txt`);
}
