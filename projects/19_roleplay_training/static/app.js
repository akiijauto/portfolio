/* 接客・クレーム対応ロールプレイAI JavaScript */

const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const jsonHeaders = { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken };

const MAX_TURNS = 8;
let _scenario = null;
let _difficulty = 'normal';
let _history = []; // [{speaker:'customer'|'staff', text:'...'}]

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                  .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function showErr(id, msg) { const el=document.getElementById(id); el.textContent=msg; el.style.display='block'; }
function hideErr(id) { document.getElementById(id).style.display='none'; }

const TAB_ORDER = ['setup', 'chat', 'score'];
function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.getElementById('nav-' + name).classList.add('active');
}

// ── ① シナリオ選択 ──────────────────────────────────────────
async function startRoleplay() {
  _scenario = document.querySelector('input[name="scenario"]:checked')?.value;
  _difficulty = document.querySelector('input[name="difficulty"]:checked')?.value || 'normal';
  hideErr('start-error');

  const btn = document.getElementById('start-btn');
  btn.disabled = true;
  document.getElementById('start-progress').style.display = 'block';

  try {
    const res = await fetch('api/start', {
      method: 'POST', headers: jsonHeaders,
      body: JSON.stringify({ scenario: _scenario, difficulty: _difficulty })
    });
    const d = await res.json();
    if (!d.ok) { showErr('start-error', d.error); return; }

    _history = [{ speaker: 'customer', text: d.message }];
    renderChat();
    document.getElementById('chat-title').textContent =
      document.querySelector(`input[name="scenario"]:checked`).closest('.scenario-card').querySelector('.scenario-label').textContent;
    switchTab('chat');
  } finally {
    btn.disabled = false;
    document.getElementById('start-progress').style.display = 'none';
  }
}

// ── ② ロールプレイ ────────────────────────────────────────────
function renderChat() {
  const win = document.getElementById('chat-window');
  win.innerHTML = _history.map(t => `
    <div class="chat-msg chat-${t.speaker}">
      <div class="chat-bubble">${escHtml(t.text)}</div>
      <div class="chat-role">${t.speaker === 'customer' ? '🧑 客' : '🧑‍💼 あなた（スタッフ）'}</div>
    </div>`).join('');
  win.scrollTop = win.scrollHeight;

  const staffTurns = _history.filter(t => t.speaker === 'staff').length;
  document.getElementById('turn-counter').textContent = `${staffTurns} / ${MAX_TURNS} ターン`;

  const ended = staffTurns >= MAX_TURNS;
  document.getElementById('staff-input').disabled = ended;
  document.getElementById('send-btn').disabled = ended;
}

async function sendReply() {
  const input = document.getElementById('staff-input');
  const text = input.value.trim();
  if (!text) return;
  hideErr('chat-error');

  _history.push({ speaker: 'staff', text });
  renderChat();
  input.value = '';

  const sendBtn = document.getElementById('send-btn');
  sendBtn.disabled = true;
  input.disabled = true;
  document.getElementById('chat-progress').style.display = 'block';

  try {
    const res = await fetch('api/reply', {
      method: 'POST', headers: jsonHeaders,
      body: JSON.stringify({ scenario: _scenario, difficulty: _difficulty, staff_message: text, history: _history.slice(0, -1) })
    });
    const d = await res.json();
    if (!d.ok) { showErr('chat-error', d.error); _history.pop(); renderChat(); return; }

    _history.push({ speaker: 'customer', text: d.message });
    renderChat();
  } finally {
    document.getElementById('chat-progress').style.display = 'none';
    const staffTurns = _history.filter(t => t.speaker === 'staff').length;
    const ended = staffTurns >= MAX_TURNS;
    sendBtn.disabled = ended;
    input.disabled = ended;
    if (!ended) input.focus();
  }
}

document.addEventListener('keydown', (e) => {
  if (e.target.id === 'staff-input' && e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendReply();
  }
});

// ── ③ 採点 ────────────────────────────────────────────────────
async function doScore() {
  hideErr('score-error');
  document.getElementById('score-result').innerHTML = '';
  document.getElementById('score-restart-row').style.display = 'none';
  document.getElementById('score-progress-box').style.display = 'block';
  switchTab('score');

  try {
    const res = await fetch('api/score', {
      method: 'POST', headers: jsonHeaders,
      body: JSON.stringify({ scenario: _scenario, difficulty: _difficulty, history: _history })
    });
    const d = await res.json();
    if (!d.ok) { showErr('score-error', d.error); return; }
    renderScore(d.result);
    document.getElementById('score-restart-row').style.display = 'block';
  } finally {
    document.getElementById('score-progress-box').style.display = 'none';
  }
}

function renderScore(r) {
  const scores = r.scores || {};
  const total = Object.values(scores).reduce((a, b) => a + (Number(b) || 0), 0);
  const max = Object.keys(scores).length * 5;

  const scoreRows = Object.entries(scores).map(([k, v]) => `
    <div class="score-row">
      <div class="score-label">${escHtml(k)}</div>
      <div class="score-bar"><div class="score-bar-fill" style="width:${(Number(v) || 0) / 5 * 100}%"></div></div>
      <div class="score-value">${escHtml(String(v))} / 5</div>
    </div>`).join('');

  const goodList = (r.good_points || []).map(x => `<li>${escHtml(x)}</li>`).join('');
  const improveList = (r.improvement_points || []).map(x => `<li>${escHtml(x)}</li>`).join('');

  document.getElementById('score-result').innerHTML = `
    <div class="box">
      <div class="total-score">${total} <span class="total-score-unit">/ ${max}点</span></div>
      <p class="total-comment">${escHtml(r.total_comment || '')}</p>
      <div class="score-rows">${scoreRows}</div>
    </div>
    <div class="box">
      <h3>👍 良かった点</h3>
      <ul>${goodList}</ul>
    </div>
    <div class="box">
      <h3>📝 改善点</h3>
      <ul>${improveList}</ul>
    </div>
    <div class="box">
      <h3>💡 より良い対応の例</h3>
      <p>${escHtml(r.model_answer || '')}</p>
    </div>`;
}

function restart() {
  _scenario = null;
  _history = [];
  document.getElementById('chat-window').innerHTML = '';
  document.getElementById('staff-input').disabled = false;
  document.getElementById('send-btn').disabled = false;
  document.getElementById('score-result').innerHTML = '';
  switchTab('setup');
}
