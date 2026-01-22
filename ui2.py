# ui.py
import base64
import json
import logging
import os
import tempfile
import time

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

# ✅ Import direct de ta fonction main(input_file, output_path)
from docling_extractor import main as docling_main  # docling_extractor.py

# -------------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("ui")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# HTML UI
# -------------------------------------------------------------------
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
  const CHAT_ENDPOINT = "/ask";
  const EXTRACT_ENDPOINT = "/extract";

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

  async function callChat() {
    const res = await fetch(CHAT_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    return res.json();
  }

  async function fileToBase64(file) {
    const ab = await file.arrayBuffer();
    const bytes = new Uint8Array(ab);

    let binary = "";
    const chunkSize = 0x8000;
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
    }
    return btoa(binary);
  }

  async function extractPdf(file) {
    const content_b64 = await fileToBase64(file);
    const res = await fetch(EXTRACT_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: file.name,
        content_b64: content_b64,
      }),
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
      if (hasPdf) {
        const f = fileInput.files[0];
        const data = await extractPdf(f);

        const md = data?.markdown ?? "";
        const preview = md.slice(0, 4000);

        chatEl.lastChild.textContent =
          `✅ PDF reçu: ${data?.filename ?? f.name}\n` +
          `✅ Conversion terminée (.md)\n\n` +
          `--- Début du markdown ---\n` +
          `${preview}\n` +
          `--- Fin (preview) ---\n`;

        messages.push({
          role: "system",
          content: `Document converti en Markdown (source: ${data?.filename ?? f.name}).\n\n${md}`
        });

        fileInput.value = "";
        fileNameEl.textContent = "";
        return;
      }

      const data = await callChat();
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

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
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

@app.get("/debug/headers")
async def debug_headers(request: Request):
    """Pour voir ce que le proxy envoie comme headers."""
    return JSONResponse({
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers),
    })


# -------------------------------------------------------------------
# Docling runner (logs + timings)
# -------------------------------------------------------------------
def run_docling_main(input_pdf_path: str, original_filename: str) -> str:
    """
    Exécute docling_extractor.main(input_file, output_path)
    et renvoie le contenu du .md généré.
    """
    stem = os.path.splitext(original_filename)[0] or "document"
    out_md_path = os.path.join(tempfile.gettempdir(), f"{stem}-{os.getpid()}-{int(time.time())}.md")

    log.info("[docling] start convert | input=%s | out=%s", input_pdf_path, out_md_path)

    t0 = time.time()
    docling_main(input_pdf_path, out_md_path)
    dt = time.time() - t0

    log.info("[docling] finished convert in %.2fs | exists_out=%s", dt, os.path.exists(out_md_path))

    if not os.path.exists(out_md_path):
        raise RuntimeError(f"docling_extractor.main() n'a pas créé le fichier: {out_md_path}")

    with open(out_md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    log.info("[docling] out size=%d chars", len(md_content))

    try:
        os.remove(out_md_path)
        log.debug("[docling] cleaned out file: %s", out_md_path)
    except Exception as e:
        log.warning("[docling] failed to remove out file %s: %s", out_md_path, str(e))

    return md_content


# -------------------------------------------------------------------
# Extract endpoint with detailed logs
# -------------------------------------------------------------------
@app.post("/extract")
async def extract(request: Request):
    """
    Extraction PDF -> Markdown via JSON base64
    Body attendu:
      { "filename": "xxx.pdf", "content_b64": "..." }
    """
    req_id = f"{int(time.time()*1000)}-{os.getpid()}"
    ct = request.headers.get("content-type", "")
    cl = request.headers.get("content-length", "")

    log.info("[extract:%s] incoming | ct=%s | cl=%s", req_id, ct, cl)

    # Log headers utiles (sans tout spammer)
    log.debug("[extract:%s] headers=%s", req_id, dict(request.headers))

    # 1) Parse JSON
    try:
        payload = await request.json()
    except Exception as e:
        log.exception("[extract:%s] JSON parse error: %s", req_id, str(e))
        return JSONResponse({"error": f"Invalid JSON: {str(e)}"}, status_code=400)

    filename = (payload.get("filename") or "document.pdf").strip() or "document.pdf"
    content_b64 = payload.get("content_b64")

    log.info(
        "[extract:%s] payload ok | filename=%s | has_b64=%s | b64_len=%s",
        req_id,
        filename,
        bool(content_b64),
        (len(content_b64) if isinstance(content_b64, str) else None),
    )

    if not content_b64:
        return JSONResponse({"error": "Missing field: content_b64"}, status_code=400)

    # tolère data URL: "data:application/pdf;base64,..."
    if isinstance(content_b64, str) and content_b64.strip().startswith("data:") and "," in content_b64:
        log.info("[extract:%s] detected data-url, stripping prefix", req_id)
        content_b64 = content_b64.split(",", 1)[1]

    # 2) Decode base64
    try:
        t0 = time.time()
        pdf_bytes = base64.b64decode(content_b64, validate=True)
        log.info("[extract:%s] base64 decoded | bytes=%d | %.3fs", req_id, len(pdf_bytes), time.time() - t0)
    except Exception as e:
        log.exception("[extract:%s] base64 decode error: %s", req_id, str(e))
        return JSONResponse({"error": f"Invalid base64: {str(e)}"}, status_code=400)

    # 3) Quick sanity check: PDF header
    if len(pdf_bytes) < 5 or pdf_bytes[:5] != b"%PDF-":
        head = pdf_bytes[:32]
        log.warning("[extract:%s] bytes do not look like a PDF | head=%s", req_id, head)
        # On continue quand même (au cas où), mais tu verras le warning.

    # 4) Save temp file
    tmp_pdf_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_pdf_path = tmp.name
            tmp.write(pdf_bytes)

        log.info("[extract:%s] temp pdf saved: %s", req_id, tmp_pdf_path)

        # 5) Run docling
        md_content = run_docling_main(tmp_pdf_path, filename)

        log.info("[extract:%s] success | md_chars=%d", req_id, len(md_content))
        return JSONResponse({"filename": filename, "markdown": md_content})

    except Exception as e:
        log.exception("[extract:%s] extraction error: %s", req_id, str(e))
        return JSONResponse({"error": f"PDF extraction error: {str(e)}"}, status_code=500)

    finally:
        if tmp_pdf_path and os.path.exists(tmp_pdf_path):
            try:
                os.remove(tmp_pdf_path)
                log.debug("[extract:%s] cleaned tmp pdf: %s", req_id, tmp_pdf_path)
            except Exception as e:
                log.warning("[extract:%s] failed to remove tmp pdf %s: %s", req_id, tmp_pdf_path, str(e))


# -------------------------------------------------------------------
# Chat endpoint (JSON) + logs
# -------------------------------------------------------------------
@app.post("/ask")
async def ask(request: Request):
    """
    Chat texte uniquement en JSON
    Body attendu:
      { "messages": [ {role, content}, ... ] }
    """
    req_id = f"{int(time.time()*1000)}-{os.getpid()}"
    ct = request.headers.get("content-type", "")
    cl = request.headers.get("content-length", "")
    log.info("[ask:%s] incoming | ct=%s | cl=%s", req_id, ct, cl)

    try:
        payload = await request.json()
    except Exception as e:
        log.exception("[ask:%s] JSON parse error: %s", req_id, str(e))
        return JSONResponse({"error": f"Invalid JSON: {str(e)}"}, status_code=400)

    msgs = payload.get("messages") or []
    if not isinstance(msgs, list):
        log.warning("[ask:%s] messages not list", req_id)
        return JSONResponse({"error": "`messages` must be a JSON array"}, status_code=400)

    last_user_message = ""
    for msg in reversed(msgs):
        if isinstance(msg, dict) and msg.get("role") == "user":
            last_user_message = (msg.get("content") or "")
            break

    log.info("[ask:%s] last_user_len=%d", req_id, len(last_user_message))

    answer = f"Tu as dit : {last_user_message}" if last_user_message else "Aucun message reçu."
    resp = {"choices": [{"message": {"role": "assistant", "content": answer}}]}
    return JSONResponse(resp)
