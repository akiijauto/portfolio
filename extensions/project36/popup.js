// ローカル開発時はlocalhost、本番公開時はRenderのURLに差し替える
const API_BASE = "http://localhost:5036";

const textInput = document.getElementById("text-input");
const pasteButton = document.getElementById("paste-button");
const modeSelect = document.getElementById("mode-select");
const formatButton = document.getElementById("format-button");
const errorMessage = document.getElementById("error-message");
const resultBlock = document.getElementById("result-block");
const resultText = document.getElementById("result-text");
const copyButton = document.getElementById("copy-button");

pasteButton.addEventListener("click", async () => {
  try {
    textInput.value = await navigator.clipboard.readText();
  } catch (e) {
    errorMessage.textContent = "クリップボードの読み取りに失敗しました。";
  }
});

formatButton.addEventListener("click", async () => {
  const text = textInput.value.trim();
  errorMessage.textContent = "";
  resultBlock.classList.add("hidden");

  if (!text) {
    errorMessage.textContent = "テキストを入力してください。";
    return;
  }

  formatButton.disabled = true;
  formatButton.textContent = "整形中...";

  try {
    const response = await fetch(`${API_BASE}/api/format`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, mode: modeSelect.value }),
    });
    const data = await response.json();

    if (!data.ok) {
      errorMessage.textContent = data.error || "整形に失敗しました。";
      return;
    }

    resultText.value = data.result;
    resultBlock.classList.remove("hidden");
  } catch (e) {
    errorMessage.textContent = "サーバーに接続できませんでした。";
  } finally {
    formatButton.disabled = false;
    formatButton.textContent = "整形する";
  }
});

copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(resultText.value);
  copyButton.textContent = "コピーしました";
  setTimeout(() => (copyButton.textContent = "クリップボードにコピー"), 1500);
});
