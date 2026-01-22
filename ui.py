# ui.py
import json
import os
import re
import tempfile
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

# ✅ import direct de ta fonction main
from docling_extractor import main as docling_main  # docling_extractor.py

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
    .row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
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
      <input id="file" type="file" accept="application/pdf" style="display:none" />
      <button type="button" id="fileBtn">📎 PDF</button>
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

  const fileInput = document.getElementById("file");
  const fileBtn = document.getElementById("fileBtn");
  const fileNameEl = document.getElementById("fileName");

  fileBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    fileNameEl.textContent = (fileInput.files && fileInput.files.length > 0) ? fileInput.files[0].name : "";
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
    const formData = new FormData();
    formData.append("messages", JSON.stringify(messages));

    if (fileInput.files && fileInput.files.length > 0) {
      formData.append("file", fileInput.files[0]);
    }

    const res = await fetch(ENDPOINT, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return res.json();
  }

  formEl.addEventListener("submit", async (e) => {
    e.preventDefault();

    const text = inputEl.value.trim();
    const hasPdf = fileInput.files && fileInput.files.length > 0;
    if (!text && !hasPdf) return;

    let displayed = text || "(PDF envoyé)";
    if (hasPdf) displayed += `\n\n📎 PDF: ${fileInput.files[0].name}`;

    messages.push({ role: "user", content: text || "" });
    addMsg("user", displayed);

    inputEl.value = "";
    sendBtn.disabled = true;
    addMsg("assistant", "…");

    try {
      const data = await callLLM();
      const content = data?.choices?.[0]?.message?.content ?? "(pas de contenu)";
      chatEl.lastChild.textContent = content;
      messages.push({ role: "assistant", content });

      fileInput.value = "";
      fileNameEl.textContent = "";

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


def safe_stem(filename: str) -> str:
    """Crée un nom de fichier safe (sans caractères bizarres)"""
    stem = os.path.splitext(filename)[0]
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "_", stem).strip("_")
    return stem or "document"


def run_docling_main(input_pdf_path: str, original_filename: str) -> str:
    """
    Exécute docling_extractor.main(input_file, output_path)
    et renvoie le contenu du .md généré.
    """
    stem = safe_stem(original_filename)
    out_md_path = os.path.join(tempfile.gettempdir(), f"{stem}.md")

    # ⚠️ Appel direct à ta fonction main
    # signature: main(input_file, output_path)
    docling_main(input_pdf_path, out_md_path)

    if not os.path.exists(out_md_path):
        raise RuntimeError(f"docling_extractor.main() n'a pas créé le fichier: {out_md_path}")

    with open(out_md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    # optionnel: nettoyer le .md après lecture
    try:
        os.remove(out_md_path)
    except Exception:
        pass

    return md_content


@app.post("/ask")
async def ask(
    messages: str = Form(...),
    file: Optional[UploadFile] = File(None),
):
    # 1) Parser messages JSON
    try:
        msgs = json.loads(messages) if messages else []
        if not isinstance(msgs, list):
            return JSONResponse({"error": "`messages` must be a JSON array"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"Invalid messages JSON: {str(e)}"}, status_code=400)

    # 2) Dernier message user
    last_user_message = ""
    for msg in reversed(msgs):
        if isinstance(msg, dict) and msg.get("role") == "user":
            last_user_message = (msg.get("content") or "")
            break

    # 3) Si PDF présent -> sauver temporairement et appeler docling_main()
    md_content = ""
    pdf_name = ""

    if file is not None:
        pdf_name = file.filename or "document.pdf"

        if file.content_type not in (None, "application/pdf"):
            return JSONResponse({"error": f"Unsupported file type: {file.content_type}"}, status_code=400)

        tmp_pdf_path = None
        try:
            # Sauvegarde temporaire du PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp_pdf_path = tmp.name
                tmp.write(await file.read())

            # Appel main(input_file, output_path) -> lit le .md
            md_content = run_docling_main(tmp_pdf_path, pdf_name)

        except Exception as e:
            return JSONResponse({"error": f"PDF extraction error: {str(e)}"}, status_code=500)
        finally:
            if tmp_pdf_path and os.path.exists(tmp_pdf_path):
                try:
                    os.remove(tmp_pdf_path)
                except Exception:
                    pass

    # 4) Construire réponse pour UI
    if md_content:
        # pour éviter un message trop énorme
        preview = md_content[:4000]
        answer = (
            f"✅ PDF reçu: {pdf_name}\n"
            f"✅ Conversion terminée (.md)\n\n"
            f"--- Début du markdown ---\n"
            f"{preview}\n"
            f"--- Fin (preview) ---\n"
        )
        if last_user_message:
            answer += f"\n💬 Ton message: {last_user_message}"
    else:
        answer = f"Tu as dit : {last_user_message}" if last_user_message else "Aucun message reçu."

    resp = {"choices": [{"message": {"role": "assistant", "content": answer}}]}
    return JSONResponse(resp)
