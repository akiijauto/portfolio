/* YouTube要約ツール JavaScript */
document.getElementById('url-input').addEventListener('keydown', e => { if (e.key === 'Enter') doSummarize(); });
document.getElementById('search-input').addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function showSearchError(msg) {
  const el = document.getElementById('search-error-box');
  el.textContent = '❌ ' + msg; el.style.display = 'block';
}

async function doSearch() {
  const keyword = document.getElementById('search-input').value.trim();
  if (!keyword) { showSearchError('キーワードを入力してください'); return; }

  const btn        = document.getElementById('search-btn');
  const progressEl = document.getElementById('search-progress');
  btn.disabled = true;
  document.getElementById('search-error-box').style.display = 'none';
  document.getElementById('search-results').innerHTML = '';
  progressEl.style.display = 'block';

  try {
    const fd = new FormData(); fd.append('keyword', keyword);
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const res = await fetch('search', { method: 'POST', headers: { 'X-CSRFToken': csrfToken }, body: fd });

    let data;
    try {
      data = await res.json();
    } catch {
      throw new Error(`サーバーから予期しない応答がありました（HTTP ${res.status}）。時間をおいて再度お試しください`);
    }
    if (!data.ok) { showSearchError(data.error); return; }

    if (data.videos.length === 0) {
      document.getElementById('search-results').innerHTML =
        '<p class="empty-note">字幕付きの動画が見つかりませんでした。別のキーワードでお試しください。</p>';
      return;
    }
    document.getElementById('search-results').innerHTML = data.videos.map(v => `
      <div class="search-result-card" onclick="selectSearchResult('${v.url}')">
        <img src="${v.thumbnail}" alt="">
        <div class="search-result-title">${escHtml(v.title)}</div>
      </div>`).join('');
  } catch (e) {
    showSearchError(e.message || '通信エラーが発生しました。時間をおいて再度お試しください');
  } finally {
    btn.disabled = false;
    progressEl.style.display = 'none';
  }
}

function selectSearchResult(url) {
  document.getElementById('url-input').value = url;
  doSummarize();
  document.getElementById('url-input').scrollIntoView({ behavior: 'smooth' });
}

async function doSummarize() {
  const url = document.getElementById('url-input').value.trim();
  if (!url) { showError('URLを入力してください'); return; }
  const btn        = document.getElementById('summarize-btn');
  const progressEl = document.getElementById('progress');
  btn.disabled = true;
  document.getElementById('results').style.display   = 'none';
  document.getElementById('error-box').style.display = 'none';

  const baseMsg  = '字幕を取得してAIが要約中です… しばらくお待ちください';
  const startsAt = Date.now();
  const tick = () => {
    const sec = Math.floor((Date.now() - startsAt) / 1000);
    progressEl.textContent = `${baseMsg}（経過: ${sec}秒）`;
  };
  tick();
  progressEl.style.display = 'block';
  const timer = setInterval(tick, 1000);

  try {
    const fd = new FormData(); fd.append('url', url);
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const res = await fetch('summarize', { method: 'POST', headers: { 'X-CSRFToken': csrfToken }, body: fd });

    let data;
    try {
      data = await res.json();
    } catch {
      throw new Error(`サーバーから予期しない応答がありました（HTTP ${res.status}）。時間をおいて再度お試しください`);
    }
    if (!data.ok) { showError(data.error); return; }

    const d   = data.data;
    const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    document.getElementById('thumbnail').src           = `https://img.youtube.com/vi/${d.video_id}/mqdefault.jpg`;
    document.getElementById('video-title').textContent = d.title || '（タイトル不明）';
    document.getElementById('transcript-len').textContent = `字幕文字数: ${d.transcript_len.toLocaleString()}文字`;
    document.getElementById('category').textContent    = d.category || '';
    document.getElementById('summary-text').textContent = d.summary;
    document.getElementById('points-list').innerHTML   = d.points.map(p => `<li>${esc(p)}</li>`).join('');
    document.getElementById('sns-text').textContent    = d.sns;
    document.getElementById('results').style.display   = 'block';
    document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
  } catch (e) {
    showError(e.message || '通信エラーが発生しました。時間をおいて再度お試しください');
  } finally {
    clearInterval(timer);
    progressEl.style.display = 'none';
    progressEl.textContent   = baseMsg;
    btn.disabled = false;
  }
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
  const title   = document.getElementById('video-title').textContent;
  const url     = document.getElementById('url-input').value.trim();
  const summary = document.getElementById('summary-text').textContent;
  const points  = [...document.querySelectorAll('#points-list li')].map(li => '・' + li.textContent);
  const sns     = document.getElementById('sns-text').textContent;
  const text = [
    title, url, '',
    '【動画要約】', summary, '',
    '【主要ポイント】', ...points, '',
    '【SNS投稿用】', sns
  ].join('\n');
  downloadText(text, `動画要約_${dateStr()}.txt`);
}
