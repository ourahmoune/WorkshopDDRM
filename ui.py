# ui.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML_PAGE = r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Chat LLM</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 24px; max-width: 820px; }
    #chat { border: 1px solid #ddd; border-radius: 10px; padding: 12px; height: 420px; overflow: auto; }
    .msg { margin: 10px 0; padding: 10px 12px; border-radius: 10px; white-space: pre-wrap; }
    .user { background: #f2f2f2; margin-left: 20%; }
    .assistant { background: #e9f3ff; margin-right: 20%; }
    form { display: flex; flex-direction: column; gap: 10px; margin-top: 12px; }
    textarea { flex: 1; resize: vertical; min-height: 44px; padding: 10px; border-radius: 10px; border: 1px solid #ddd; }
    .row { display: flex; gap: 10px; align-items: center; }
    button { padding: 10px 14px; border-radius: 10px; border: 1px solid #ddd; background: white; cursor: pointer; }
    button:disabled { opacity: .6; cursor: not-allowed; }
    #fileName { font-size: .9em; color: #555; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 420px; }
  </style>
</head>
<body>
  <h1>Chat via Otoroshi</h1>

  <div id="chat"></div>

  <form id="form">
    <textarea id="input" placeholder="Écris ton message…"></textarea>

    <div class="row">
      <input id="file" type="file" style="display:none" />
      <button type="button" id="fileBtn">📎 Fichier</button>
      <span id="fileName"></span>
      <button id="send" type="submit">Envoyer</button>
    </div>
  </form>

<script>
  const ENDPOINT = "/ask";

  const chatEl = document.getElementById("chat");
  const formEl = document.getElementById("form");
  const inputEl = document.getElementById("input");
  const sendBtn = document.getElementById("send");

  // Fichier
  const fileInput = document.getElementById("file");
  const fileBtn = document.getElementById("fileBtn");
  const fileNameEl = document.getElementById("fileName");

  fileBtn.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files.length > 0) {
      fileNameEl.textContent = fileInput.files[0].name;
    } else {
      fileNameEl.textContent = "";
    }
  });

  const messages = [];

  function addMsg(role, content) {
    const div = document.createElement("div");
    div.className = `msg ${role === "user" ? "user" : "assistant"}`;
    div.textContent = content;
    chatEl.appendChild(div);
    chatEl.scrollTop = chatEl.scrollHeight;
  }

  async function callLLM() {
    const res = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return res.json();
  }

  formEl.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text) return;

    // Optionnel: afficher le nom du fichier dans le chat côté user (sans l'envoyer)
    let displayed = text;
    if (fileInput.files && fileInput.files.length > 0) {
      displayed += `\n\n📎 Fichier sélectionné: ${fileInput.files[0].name}`;
    }

    messages.push({ role: "user", content: text });
    addMsg("user", displayed);

    inputEl.value = "";
    sendBtn.disabled = true;

    addMsg("assistant", "…");

    try {
      const data = await callLLM();
      const content = data?.choices?.[0]?.message?.content ?? "(pas de contenu)";
      chatEl.lastChild.textContent = content;
      messages.push({ role: "assistant", content });
    } catch (err) {
      chatEl.lastChild.textContent = `Erreur: ${err.message}`;
    } finally {
      sendBtn.disabled = false;
      inputEl.focus();
    }
  });
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(HTML_PAGE)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ui.py", response_class=PlainTextResponse)
def show_source():
    with open("ui.py", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/ask")
async def ask(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"error": f"Invalid JSON: {str(e)}"}, status_code=400)

    messages = body.get("messages", [])
    if not isinstance(messages, list):
        return JSONResponse({"error": "`messages` must be an array"}, status_code=400)

    last_user_message = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            last_user_message = (msg.get("content") or "")
            break

    answer = f"Tu as dit : {last_user_message}" if last_user_message else "Aucun message reçu."

    resp = {
        "choices": [
            {"message": {"role": "assistant", "content": answer}}
        ]
    }
    return JSONResponse(resp)
