/* 音声入力式 日報・引継ぎ自動整形 JavaScript */

const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const jsonHeaders = { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken };

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                  .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function showErr(id, msg) { const el=document.getElementById(id); el.textContent=msg; el.style.display='block'; }
function hideErr(id) { document.getElementById(id).style.display='none'; }

function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.getElementById('nav-' + name).classList.add('active');
}

// 日付の初期値を今日にする
document.getElementById('report-date').value = new Date().toISOString().slice(0, 10);

// 文字数カウンタ
const rawText = document.getElementById('raw-text');
rawText.addEventListener('input', () => {
  document.getElementById('char-count').textContent = rawText.value.length;
});

// ── 音声入力（Web Speech API） ─────────────────────────────
// continuous=trueでAndroid Chrome等の内部リセット（event.resultsが巻き戻る）を
// 差分管理で吸収しようとしたが、リセットの発生パターンが不規則で、断片化した
// 認識結果が誤った順序・重複で混入する不具合が解消しなかった。
// そのため「1フレーズ確定→onendで自動的に次の認識を開始」という、確定済み
// セッションをまたいだ状態管理が不要なシンプルな構成に変更する。
let _recognition = null;
let _listening = false;
let _manualStop = false;
let _accumulatedFinal = '';

function toggleMic() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const status = document.getElementById('mic-status');
  const btn = document.getElementById('mic-btn');

  if (!SpeechRecognition) {
    status.textContent = 'お使いのブラウザは音声入力に対応していません（テキスト入力をご利用ください）';
    return;
  }

  // Web Speech APIはHTTPS（またはlocalhost）でのみ動作するブラウザが多い。
  // HTTP配信時はマイク起動前に分かりやすいメッセージを出す（テキスト入力は引き続き使える）。
  if (!window.isSecureContext) {
    status.textContent = '音声入力はHTTPS接続でのみ利用できます（現在はHTTP）。テキスト入力をご利用ください';
    return;
  }

  if (_listening) {
    _manualStop = true;
    _recognition.stop();
    return;
  }

  _manualStop = false;
  _accumulatedFinal = rawText.value;
  _startRecognitionSession(SpeechRecognition, status, btn);
}

function _startRecognitionSession(SpeechRecognition, status, btn) {
  _recognition = new SpeechRecognition();
  _recognition.lang = 'ja-JP';
  // 1セッション1フレーズのみ確定させる。continuous=trueにすると内部リセットで
  // 結果配列が壊れるため、確定後はonendで新しいセッションを開始して継続感を出す。
  _recognition.continuous = false;
  _recognition.interimResults = true;

  _recognition.onstart = () => {
    _listening = true;
    btn.textContent = '⏹ 音声入力を停止';
    btn.classList.add('mic-active');
    status.textContent = '聞き取り中…';
  };

  _recognition.onresult = (event) => {
    let interim = '';
    for (let i = 0; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        _accumulatedFinal += transcript;
      } else {
        interim += transcript;
      }
    }
    rawText.value = (_accumulatedFinal + interim).slice(0, 3000);
    document.getElementById('char-count').textContent = rawText.value.length;
  };

  _recognition.onerror = (event) => {
    const messages = {
      'not-allowed': 'マイクの使用が許可されませんでした（ブラウザの権限設定をご確認ください）',
      'service-not-allowed': 'この接続では音声認識サービスを利用できません（HTTPS接続が必要な場合があります）',
      'no-speech': '音声が検出されませんでした。もう一度お試しください',
    };
    status.textContent = messages[event.error] || ('音声認識エラー: ' + event.error);
    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
      _manualStop = true;
    }
  };

  _recognition.onend = () => {
    if (_manualStop) {
      _listening = false;
      btn.textContent = '🎤 音声入力を開始';
      btn.classList.remove('mic-active');
      status.textContent = '';
      return;
    }
    // 1フレーズ確定後、ユーザーが停止していない限り次のフレーズの認識を継続する。
    _startRecognitionSession(SpeechRecognition, status, btn);
  };

  _recognition.start();
}

// ── 整形 ─────────────────────────────────────────────────
async function doFormat() {
  hideErr('format-error');
  const raw_text = rawText.value.trim();
  if (!raw_text) {
    showErr('format-error', '日報の内容を入力してください');
    return;
  }

  const btn = document.getElementById('format-btn');
  btn.disabled = true;
  document.getElementById('format-progress').style.display = 'block';

  try {
    const res = await fetch('api/format', {
      method: 'POST', headers: jsonHeaders,
      body: JSON.stringify({
        raw_text,
        staff_name: document.getElementById('staff-name').value.trim(),
        report_date: document.getElementById('report-date').value
      })
    });
    const d = await res.json();
    if (!d.ok) { showErr('format-error', d.error); return; }

    renderResult(d.result);
    switchTab('result');
  } finally {
    btn.disabled = false;
    document.getElementById('format-progress').style.display = 'none';
  }
}

function renderResult(r) {
  hideErr('result-error');
  const date = document.getElementById('report-date').value;
  const staff = document.getElementById('staff-name').value.trim();

  const sectionEntries = Object.entries(r.sections || {}).filter(([, v]) => (v || '').trim());
  const sectionsHtml = sectionEntries.map(([k, v]) => `
    <div class="report-section">
      <h3>${escHtml(k)}</h3>
      <p>${escHtml(v)}</p>
    </div>`).join('');

  const handoverItems = r.handover_items || [];
  const handoverHtml = handoverItems.length
    ? `<ul>${handoverItems.map(x => `<li>${escHtml(x)}</li>`).join('')}</ul>`
    : '<p class="empty-note">引継ぎ事項はありません</p>';

  document.getElementById('result-area').innerHTML = `
    <div class="box">
      <div class="report-meta">
        ${date ? `<span>📅 ${escHtml(date)}</span>` : ''}
        ${staff ? `<span>👤 ${escHtml(staff)}</span>` : ''}
      </div>
      <h2>本日のまとめ</h2>
      <p class="report-summary">${escHtml(r.summary || '')}</p>
    </div>
    <div class="box">
      ${sectionsHtml || '<p class="empty-note">記載なし</p>'}
    </div>
    <div class="box handover-box">
      <h2>📋 引継ぎ事項（翌日スタッフへ）</h2>
      ${handoverHtml}
    </div>
    <div class="btn-row">
      <button class="btn btn-secondary" onclick="copyResult()">📋 コピー</button>
      <button class="btn btn-secondary" onclick="downloadResult()">⬇ テキストでダウンロード</button>
      <button class="btn btn-primary" onclick="switchTab('input')">← 入力に戻る</button>
    </div>`;

  window._lastResult = r;
}

function resultToText() {
  const r = window._lastResult || {};
  const date = document.getElementById('report-date').value;
  const staff = document.getElementById('staff-name').value.trim();
  let lines = [];
  lines.push('■ 日報・引継ぎメモ');
  if (date) lines.push(`日付: ${date}`);
  if (staff) lines.push(`記入者: ${staff}`);
  lines.push('');
  lines.push('【本日のまとめ】');
  lines.push(r.summary || '');
  lines.push('');
  for (const [k, v] of Object.entries(r.sections || {})) {
    if ((v || '').trim()) {
      lines.push(`【${k}】`);
      lines.push(v);
      lines.push('');
    }
  }
  lines.push('【引継ぎ事項（翌日スタッフへ）】');
  const items = r.handover_items || [];
  if (items.length) {
    items.forEach(x => lines.push('・' + x));
  } else {
    lines.push('（なし）');
  }
  return lines.join('\n');
}

function copyResult() {
  navigator.clipboard.writeText(resultToText());
}

function downloadResult() {
  const date = document.getElementById('report-date').value || 'report';
  const blob = new Blob([resultToText()], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `日報_${date}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}
