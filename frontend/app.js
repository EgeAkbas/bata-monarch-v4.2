const messages = document.getElementById("messages");
const input    = document.getElementById("input");
const sendBtn  = document.getElementById("send");
const micBtn   = document.getElementById("mic");

// ── Mesaj ekle ──────────────────────────────────────────────
function addMessage(text, who) {
  const div = document.createElement("div");
  div.className = "msg " + who;
  div.textContent = text;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

// Yükleniyor göstergesi
function addLoading() {
  const div = document.createElement("div");
  div.className = "msg bata loading";
  div.innerHTML = "<span></span><span></span><span></span>";
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

// ── Backend isteği ──────────────────────────────────────────
async function sendToBackend(command) {
  try {
    const response = await fetch("http://localhost:8847/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    return data.response;
  } catch (error) {
    return "❌ Sunucu hatası: " + error.message;
  }
}

// ── Mesaj gönder ────────────────────────────────────────────
async function send() {
  const text = input.value.trim();
  if (!text) return;

  addMessage(text, "user");
  input.value = "";
  sendBtn.disabled = true;

  const loader = addLoading();
  const response = await sendToBackend(text);
  loader.remove();

  addMessage(response, "bata");
  sendBtn.disabled = false;
  input.focus();
}

// ── Event listeners ─────────────────────────────────────────
sendBtn.addEventListener("click", send);
input.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) send();
});

micBtn.addEventListener("click", () => {
  micBtn.classList.toggle("listening");
  if (micBtn.classList.contains("listening")) {
    addMessage("🎤 Sesli komut dinleniyor...", "bata");
  }
});

// ── Karşılama ───────────────────────────────────────────────
window.addEventListener("load", () => {
  addMessage("Merhaba, ben Monarch. Bugün ne yapıyoruz?", "bata");
});
