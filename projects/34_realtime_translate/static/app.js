const form = document.getElementById("translate-form");
const textInput = document.getElementById("text-input");
const errorMessage = document.getElementById("error-message");
const originalDisplay = document.getElementById("original-display");
const submitBtn = document.getElementById("translate-submit-btn");
const loadingHint = document.getElementById("translate-loading");
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = textInput.value.trim();
  if (!text) return;

  errorMessage.textContent = "";
  originalDisplay.textContent = text;
  document.querySelectorAll(".lang-text").forEach((el) => (el.textContent = ""));
  submitBtn.disabled = true;
  loadingHint.hidden = false;

  try {
    const basePath = window.location.pathname.replace(/\/$/, "");
    const response = await fetch(`${basePath}/translate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({ text }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop();

      for (const block of events) {
        const lines = block.split("\n");
        let eventName = "message";
        let data = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) eventName = line.slice(7);
          if (line.startsWith("data: ")) data = line.slice(6);
        }
        if (!data) continue;
        handleEvent(eventName, JSON.parse(data));
      }
    }
  } finally {
    submitBtn.disabled = false;
    loadingHint.hidden = true;
  }
});

function handleEvent(eventName, data) {
  if (eventName === "error") {
    errorMessage.textContent = data.message || "エラーが発生しました。";
    return;
  }
  if (eventName === "chunk") {
    const el = document.getElementById(`lang-text-${data.lang}`);
    if (el) el.textContent += data.delta;
    return;
  }
  if (eventName === "complete") {
    // ページを再読み込みすると、表示中の翻訳結果が即座に消えてコピーできなくなるため、
    // リロードせず履歴リストの先頭にこの結果を追加するだけにする。
    addHistoryItem(originalDisplay.textContent);
  }
}

function addHistoryItem(originalText) {
  const historyList = document.getElementById("history-list");
  const item = document.createElement("div");
  item.className = "history-item";

  const original = document.createElement("p");
  original.className = "history-original";
  original.textContent = originalText;
  item.appendChild(original);

  const ul = document.createElement("ul");
  for (const [code, label] of LANGS) {
    const el = document.getElementById(`lang-text-${code}`);
    const li = document.createElement("li");
    const strong = document.createElement("strong");
    strong.textContent = label;
    li.appendChild(strong);
    li.append(`: ${el ? el.textContent : ""}`);
    ul.appendChild(li);
  }
  item.appendChild(ul);

  historyList.insertBefore(item, historyList.firstChild);
}

function copyToClipboard(text) {
  if (!text) return;
  // navigator.clipboard はHTTPS（またはlocalhost）等の安全なコンテキストでのみ使える。
  // 本番がHTTP配信の場合は使えないため、テキストエリア経由のコピーにフォールバックする。
  if (window.isSecureContext && navigator.clipboard) {
    navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
  } else {
    fallbackCopy(text);
  }
}

function fallbackCopy(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  try {
    document.execCommand("copy");
  } catch (e) {
    errorMessage.textContent = "コピーに失敗しました。テキストを選択して手動でコピーしてください。";
  }
  document.body.removeChild(textarea);
}

function copyLang(code) {
  const el = document.getElementById(`lang-text-${code}`);
  if (el) copyToClipboard(el.textContent);
}

function copyOriginal() {
  copyToClipboard(originalDisplay.textContent);
}
