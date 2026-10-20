const messagesEl = document.getElementById("messages");
const input      = document.getElementById("input");
const sendBtn    = document.getElementById("send");
const micBtn     = document.getElementById("mic");
const historyEl  = document.querySelector(".history");

let currentSessionId = null; // aktif sohbet

// ── Mesaj ekle ───────────────────────────────────────────────
function addMessage(text, who) {
  const div = document.createElement("div");
  div.className = "msg " + who;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function addLoading() {
  const div = document.createElement("div");
  div.className = "msg bata loading";
  div.innerHTML = "<span></span><span></span><span></span>";
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

// ── Backend istekleri ────────────────────────────────────────
async function sendToBackend(command) {
  const response = await fetch("http://localhost:8847/api/command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, session_id: currentSessionId })
  });

  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function fetchSessions() {
  const res = await fetch("http://localhost:8847/api/sessions");
  if (!res.ok) return [];
  const data = await res.json();
  return data.sessions || [];
}

async function loadSession(session_id) {
  const res = await fetch(`http://localhost:8847/api/sessions/${session_id}`);
  if (!res.ok) return null;
  return res.json();
}

// ── Sohbet listesini güncelle ────────────────────────────────
async function refreshHistory() {
  const sessions = await fetchSessions().catch(() => []);
  historyEl.innerHTML = "";

  if (sessions.length === 0) {
    const li = document.createElement("li");
    li.textContent = "-Henüz sohbet yok-";
    li.style.pointerEvents = "none";
    historyEl.appendChild(li);
    return;
  }

  sessions.forEach(s => {
    const li = document.createElement("li");
    li.tabIndex = 0;
    li.textContent = s.baslik;
    li.title = s.baslik;
    li.dataset.id = s.session_id;

    if (s.session_id === currentSessionId) {
      li.style.color = "var(--glow)";
    }

    li.addEventListener("click", () => openSession(s.session_id));
    li.addEventListener("keydown", e => { if (e.key === "Enter") openSession(s.session_id); });
    historyEl.appendChild(li);
  });
}

// ── Mevcut sohbeti aç ───────────────────────────────────────
async function openSession(session_id) {
  const data = await loadSession(session_id).catch(() => null);
  if (!data) return;

  currentSessionId = session_id;
  messagesEl.innerHTML = "";

  data.messages.forEach(m => {
    addMessage(m.content, m.role === "user" ? "user" : "bata");
  });

  await refreshHistory();
}

// ── Yeni sohbet ──────────────────────────────────────────────
function yeniSohbet() {
  currentSessionId = null;
  messagesEl.innerHTML = "";
  addMessage("Merhaba, ben Bata Monarch. Ne yapmamı istersin?", "bata");
  refreshHistory();
}

// ── Mesaj gönder ─────────────────────────────────────────────
async function send() {
  const text = input.value.trim();
  if (!text) return;

  addMessage(text, "user");
  input.value = "";
  sendBtn.disabled = true;

  const loader = addLoading();

  try {
    const data = await sendToBackend(text);
    loader.remove();
    addMessage(data.response, "bata");

    // Backend'den gelen session_id'yi sakla (yeni sohbet ise ilk mesajda atanır)
    if (!currentSessionId) {
      currentSessionId = data.session_id;
    }

    await refreshHistory();
  } catch (err) {
    loader.remove();
    addMessage("❌ Sunucu hatası: " + err.message, "bata");
  }

  sendBtn.disabled = false;
  input.focus();
}

// ── Event listeners ──────────────────────────────────────────
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

// Sidebar'daki "Sohbet" linkine tıklayınca yeni sohbet
document.querySelector(".menu a.active")?.addEventListener("click", e => {
  e.preventDefault();
  yeniSohbet();
});

// ── Başlangıç ────────────────────────────────────────────────
window.addEventListener("load", () => {
  addMessage("Merhaba, ben Bata Monarch. Ne yapmamı istersin?", "bata");
  refreshHistory();
});

