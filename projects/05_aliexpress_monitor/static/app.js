/* 価格監視ツール JavaScript */
function flash(id, msg, color) {
  const el = document.getElementById(`flash-${id}`);
  el.textContent = msg; el.style.color = color || '#e85d04'; el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 4000);
}

async function addProduct() {
  const name = document.getElementById('add-name').value.trim();
  const url  = document.getElementById('add-url').value.trim();
  const tgt  = document.getElementById('add-target').value.trim();
  if (!name || !url) { alert('商品名とURLを入力してください'); return; }
  const btn = document.getElementById('add-btn');
  btn.disabled = true;
  const fd = new FormData();
  fd.append('name', name); fd.append('url', url);
  if (tgt) fd.append('target_price', tgt);
  const d = await (await fetch('/add', { method: 'POST', body: fd })).json();
  btn.disabled = false;
  const res = document.getElementById('add-result');
  if (d.ok) { res.textContent = '✅ 追加しました。「今すぐチェック」で価格を取得してください。'; res.style.color = '#15803d'; res.style.display = 'block'; setTimeout(() => location.reload(), 1500); }
  else      { res.textContent = '❌ ' + d.error; res.style.color = '#dc2626'; res.style.display = 'block'; }
}

async function checkNow(id, btn) {
  btn.disabled = true; btn.textContent = 'チェック中…';
  const d = await (await fetch(`/check/${id}`, { method: 'POST' })).json();
  btn.disabled = false; btn.textContent = '今すぐチェック';
  if (d.ok) { flash(id, `✅ ${d.price.toLocaleString()}円 / ${d.status}`, '#15803d'); setTimeout(() => location.reload(), 2000); }
  else { flash(id, `❌ ${d.error}`, '#dc2626'); }
}

function toggleManual(id) {
  const el = document.getElementById(`manual-${id}`);
  el.style.display = el.style.display === 'flex' ? 'none' : 'flex';
}

async function saveManual(id) {
  const price = document.getElementById(`manual-val-${id}`).value;
  if (!price) return;
  const fd = new FormData(); fd.append('price', price);
  const d = await (await fetch(`/manual/${id}`, { method: 'POST', body: fd })).json();
  if (d.ok) { flash(id, `✅ ${Number(price).toLocaleString()}円を記録しました / ${d.status}`, '#15803d'); setTimeout(() => location.reload(), 1500); }
  else { flash(id, '❌ ' + d.error, '#dc2626'); }
}

async function deleteProduct(id) {
  await fetch(`/delete/${id}`, { method: 'POST' });
  document.getElementById(`card-${id}`).style.display = 'none';
}

async function checkAll() {
  const btn = document.querySelector('.check-all-btn');
  btn.textContent = 'チェック中…'; btn.disabled = true;
  await fetch('/check_all', { method: 'POST' });
  btn.textContent = '✅ 完了'; setTimeout(() => location.reload(), 1500);
}
