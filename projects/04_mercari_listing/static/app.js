/* メルカリ出品文生成ツール JavaScript */
async function doGenerate() {
  const name      = document.getElementById('name').value.trim();
  const condition = document.getElementById('condition').value;
  const category  = document.getElementById('category').value.trim();
  const features  = document.getElementById('features').value.trim();
  if (!name)      { showError('商品名を入力してください'); return; }
  if (!condition) { showError('商品の状態を選択してください'); return; }

  const btn = document.getElementById('gen-btn');
  btn.disabled = true;
  document.getElementById('progress').style.display  = 'block';
  document.getElementById('results').style.display   = 'none';
  document.getElementById('error-box').style.display = 'none';

  const fd = new FormData();
  fd.append('name', name); fd.append('condition', condition);
  fd.append('category', category); fd.append('features', features);
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  const res  = await fetch('generate', { method: 'POST', headers: { 'X-CSRFToken': csrfToken }, body: fd });
  const data = await res.json();

  document.getElementById('progress').style.display = 'none';
  btn.disabled = false;
  if (!data.ok) { showError(data.error); return; }

  const d = data.data;
  const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const titleEl = document.getElementById('title-text');
  titleEl.textContent = d.title;
  const len = d.title.length;
  const lenEl = document.getElementById('title-len');
  lenEl.textContent = `${len}文字 / 40文字`;
  lenEl.className   = 'title-len' + (len > 40 ? ' over' : '');

  document.getElementById('desc-text').textContent  = d.description;
  document.getElementById('price-min').textContent  = d.price_min.toLocaleString();
  document.getElementById('price-max').textContent  = d.price_max.toLocaleString();
  document.getElementById('category-tag').textContent = '📂 ' + d.category;
  document.getElementById('tips-list').innerHTML = d.tips.map(t => `<li>${esc(t)}</li>`).join('');
  document.getElementById('results').style.display = 'block';
  document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
}

function showError(msg) {
  const el = document.getElementById('error-box');
  el.textContent = '❌ ' + msg; el.style.display = 'block';
}

async function copyEl(id) {
  const text = document.getElementById(id).textContent;
  await navigator.clipboard.writeText(text);
  const card = document.getElementById(id).closest('.card');
  const btn  = card.querySelector('.copy-btn');
  if (btn) { btn.textContent = '✅ コピー済み'; setTimeout(() => btn.textContent = 'コピー', 2000); }
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
function downloadListing() {
  const name = document.getElementById('name').value.trim() || 'listing';
  const title = document.getElementById('title-text').textContent;
  const desc  = document.getElementById('desc-text').textContent;
  const priceMin = document.getElementById('price-min').textContent;
  const priceMax = document.getElementById('price-max').textContent;
  const category = document.getElementById('category-tag').textContent;
  const tips = Array.from(document.querySelectorAll('#tips-list li')).map(li => '・' + li.textContent);
  const text = [
    '【タイトル】', title, '',
    '【商品説明文】', desc, '',
    '【推奨価格】', `${priceMin}円 〜 ${priceMax}円`, '',
    '【カテゴリ】', category, '',
    '【売るためのコツ】', ...tips
  ].join('\n');
  downloadText(text, `出品文_${name}_${dateStr()}.txt`);
}
