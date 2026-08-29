const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
const jsonHeaders = { "Content-Type": "application/json", "X-CSRFToken": csrfToken };

const messageEl = document.getElementById("message");
const charCountEl = document.getElementById("char-count");
messageEl.addEventListener("input", () => {
  charCountEl.textContent = messageEl.value.length;
});

const form = document.getElementById("contact-form");
const submitBtn = document.getElementById("submit-btn");
const resultOk = document.getElementById("result-ok");
const resultErr = document.getElementById("result-err");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  resultOk.style.display = "none";
  resultErr.style.display = "none";

  const tools = Array.from(document.querySelectorAll('input[name="tools"]:checked')).map((el) => el.value);

  const payload = {
    name: document.getElementById("name").value,
    company: document.getElementById("company").value,
    email: document.getElementById("email").value,
    tools: tools,
    message: messageEl.value,
  };

  submitBtn.disabled = true;
  submitBtn.textContent = "送信中...";

  try {
    const res = await fetch("api/submit", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.ok) {
      resultOk.style.display = "block";
      form.reset();
      charCountEl.textContent = "0";
    } else {
      resultErr.textContent = "⚠️ " + (data.error || "送信に失敗しました");
      resultErr.style.display = "block";
    }
  } catch (err) {
    resultErr.textContent = "⚠️ 通信エラーが発生しました。しばらく待ってから再試行してください。";
    resultErr.style.display = "block";
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "送信する";
  }
});
