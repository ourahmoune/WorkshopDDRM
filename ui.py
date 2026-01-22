import os
import re
import uuid
import asyncio
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Tuple

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from docling_extractor import main as docling_main

# ==============================================================================
# CONFIGURATION
# ==============================================================================

APP_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = APP_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf"}
PDF_MAGIC_BYTES = b"%PDF-"
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
CHUNK_SIZE = 1024 * 1024  # 1 MB chunks
DOCLING_TIMEOUT_SECONDS = 300  # 5 minutes
FILE_RETENTION_HOURS = 24


# ==============================================================================
# UTILITAIRES
# ==============================================================================

def generate_safe_filename(original_name: str) -> str:
    """
    Génère un nom de fichier sécurisé avec UUID pour éviter les collisions.
    Format: {uuid}_{sanitized_name}.pdf
    """
    basename = os.path.basename(original_name or "document.pdf")
    basename = basename.replace("\x00", "")
    basename = re.sub(r"[^a-zA-Z0-9._-]", "_", basename).strip("._")
    
    if not basename or len(basename) > 200:
        basename = "document.pdf"
    
    unique_id = uuid.uuid4().hex[:12]
    name_part = Path(basename).stem[:50]
    ext = Path(basename).suffix.lower()
    
    return f"{unique_id}_{name_part}{ext}"


def validate_pdf_signature(file_path: Path) -> bool:
    """
    Vérifie que le fichier commence par la signature magique PDF.
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(len(PDF_MAGIC_BYTES))
            return header == PDF_MAGIC_BYTES
    except Exception:
        return False


async def save_upload_chunked(upload_file: UploadFile, destination: Path) -> int:
    """
    Sauvegarde un fichier uploadé par chunks pour économiser la mémoire.
    Retourne la taille totale en octets.
    """
    total_size = 0
    
    try:
        with open(destination, "wb") as f:
            while True:
                chunk = await upload_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE_BYTES:
                    raise ValueError(f"Fichier trop volumineux (max {MAX_FILE_SIZE_MB} MB)")
                
                f.write(chunk)
    except Exception as e:
        # Nettoie le fichier partiel en cas d'erreur
        if destination.exists():
            destination.unlink()
        raise e
    
    return total_size


async def run_docling_with_timeout(pdf_path: Path, md_path: Path) -> Tuple[bool, str]:
    """
    Exécute docling_main avec timeout et gestion d'erreurs robuste.
    Retourne (success: bool, message: str)
    """
    def _run_conversion():
        """Wrapper synchrone pour l'exécution de docling."""
        try:
            # Appelle la fonction main() de docling_extractor avec les bons paramètres
            docling_main(str(pdf_path), str(md_path))
            return True, "Conversion terminée avec succès."
        except SystemExit as se:
            return False, f"docling_main a appelé sys.exit({se.code})."
        except Exception as e:
            tb = traceback.format_exc()
            return False, f"Erreur durant la conversion:\n{type(e).__name__}: {e}\n\nTraceback:\n{tb}"
    
    try:
        # Exécute la conversion dans un thread avec timeout
        success, message = await asyncio.wait_for(
            asyncio.to_thread(_run_conversion),
            timeout=DOCLING_TIMEOUT_SECONDS
        )
        
        if not success:
            return False, message
        
        # Vérifie que le fichier MD a bien été créé
        if not md_path.exists():
            return False, "La conversion s'est terminée mais aucun fichier Markdown n'a été généré."
        
        return True, message
        
    
    
    except Exception as e:
        tb = traceback.format_exc()
        return False, f"Erreur inattendue:\n{type(e).__name__}: {e}\n\nTraceback:\n{tb}"


def cleanup_old_files():
    """
    Supprime les fichiers plus anciens que FILE_RETENTION_HOURS.
    Exécuté en arrière-plan.
    """
    try:
        cutoff_time = datetime.now() - timedelta(hours=FILE_RETENTION_HOURS)
        
        for file_path in UPLOAD_DIR.iterdir():
            if file_path.is_file():
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff_time:
                    file_path.unlink()
    except Exception as e:
        print(f"Erreur lors du nettoyage: {e}")


# ==============================================================================
# APPLICATION FASTAPI
# ==============================================================================

app = FastAPI(
    title="Docling PDF to Markdown Converter",
    description="Service de conversion PDF vers Markdown utilisant Docling",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def index():
    """Page unique avec upload et affichage du résultat."""
    html = f"""
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Docling - Convertisseur PDF → Markdown</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ 
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .container {{ 
      background: white;
      max-width: 900px;
      width: 100%;
      padding: 40px;
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    }}
    h1 {{ 
      color: #333;
      margin-bottom: 12px;
      font-size: 28px;
    }}
    .subtitle {{ 
      color: #666;
      margin-bottom: 32px;
      font-size: 14px;
      line-height: 1.6;
    }}
    .info-box {{
      background: #f0f4ff;
      border-left: 4px solid #667eea;
      padding: 16px;
      margin-bottom: 24px;
      border-radius: 4px;
      font-size: 13px;
      color: #444;
    }}
    .file-input-wrapper {{
      position: relative;
      margin-bottom: 20px;
    }}
    input[type="file"] {{
      width: 100%;
      padding: 12px;
      border: 2px dashed #ddd;
      border-radius: 8px;
      cursor: pointer;
      transition: border-color 0.3s;
    }}
    input[type="file"]:hover {{
      border-color: #667eea;
    }}
    button {{
      width: 100%;
      padding: 14px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      border: none;
      border-radius: 8px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      transition: transform 0.2s, box-shadow 0.2s;
    }}
    button:hover:not(:disabled) {{
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }}
    button:active:not(:disabled) {{
      transform: translateY(0);
    }}
    button:disabled {{
      opacity: 0.6;
      cursor: not-allowed;
    }}
    .limits {{
      margin-top: 16px;
      font-size: 12px;
      color: #888;
      text-align: center;
    }}
    
    /* Résultats */
    #results {{
      margin-top: 32px;
      padding-top: 32px;
      border-top: 2px solid #f0f0f0;
      display: none;
    }}
    #results.show {{
      display: block;
    }}
    .status {{
      display: inline-block;
      padding: 8px 16px;
      border-radius: 20px;
      font-weight: 600;
      margin-bottom: 20px;
      font-size: 14px;
    }}
    .status.success {{
      background: #d4edda;
      color: #155724;
      border: 1px solid #c3e6cb;
    }}
    .status.error {{
      background: #f8d7da;
      color: #721c24;
      border: 1px solid #f5c6cb;
    }}
    .file-info {{
      background: #f8f9fa;
      padding: 16px;
      border-radius: 8px;
      margin-bottom: 20px;
      font-size: 14px;
      color: #555;
    }}
    .download-btn {{
      display: inline-block;
      padding: 12px 24px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      text-decoration: none;
      border-radius: 8px;
      font-weight: 600;
      margin: 16px 0;
      transition: transform 0.2s, box-shadow 0.2s;
    }}
    .download-btn:hover {{
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }}
    pre {{
      background: #f8f9fa;
      padding: 16px;
      border-radius: 8px;
      overflow-x: auto;
      font-size: 13px;
      line-height: 1.6;
      border: 1px solid #e9ecef;
      margin-top: 12px;
    }}
    pre.preview {{
      max-height: 400px;
      overflow-y: auto;
    }}
    h3 {{
      color: #555;
      margin: 20px 0 12px 0;
      font-size: 18px;
    }}
    .muted {{ 
      color: #888; 
      font-size: 13px; 
      margin-top: 8px; 
    }}
    .loader {{
      display: none;
      text-align: center;
      padding: 20px;
      color: #667eea;
      font-weight: 600;
    }}
    .loader.show {{
      display: block;
    }}
    .spinner {{
      border: 3px solid #f3f3f3;
      border-top: 3px solid #667eea;
      border-radius: 50%;
      width: 40px;
      height: 40px;
      animation: spin 1s linear infinite;
      margin: 0 auto 12px;
    }}
    @keyframes spin {{
      0% {{ transform: rotate(0deg); }}
      100% {{ transform: rotate(360deg); }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <h1>📄 Convertisseur PDF → Markdown</h1>
    <p class="subtitle">
      Transformez vos documents PDF en Markdown structuré grâce à Docling
    </p>
    
    <div class="info-box">
      <strong>ℹ️ Informations :</strong><br>
      • Taille max : {MAX_FILE_SIZE_MB} MB<br>
      • Formats acceptés : PDF uniquement<br>
      • Timeout : {DOCLING_TIMEOUT_SECONDS//60} minutes<br>
      • Conservation : {FILE_RETENTION_HOURS}h
    </div>

    <form id="uploadForm">
      <div class="file-input-wrapper">
        <input 
          type="file" 
          name="file" 
          accept="application/pdf,.pdf" 
          required 
          id="fileInput"
        />
      </div>
      <button type="submit" id="submitBtn">🚀 Convertir en Markdown</button>
    </form>
    
    <p class="limits">
      Les fichiers sont automatiquement supprimés après {FILE_RETENTION_HOURS}h
    </p>
    
    <div class="loader" id="loader">
      <div class="spinner"></div>
      <div>Conversion en cours...</div>
    </div>
    
    <div id="results">
      <div class="status" id="status"></div>
      <div class="file-info" id="fileInfo"></div>
      <div id="downloadSection"></div>
      <div id="logSection"></div>
      <div id="previewSection"></div>
    </div>
  </div>

  <script>
    const form = document.getElementById('uploadForm');
    const loader = document.getElementById('loader');
    const results = document.getElementById('results');
    const submitBtn = document.getElementById('submitBtn');
    const fileInput = document.getElementById('fileInput');
    
    form.addEventListener('submit', async (e) => {{
      e.preventDefault();
      
      const file = fileInput.files[0];
      if (!file) {{
        alert('Veuillez sélectionner un fichier');
        return;
      }}
      
      console.log('Fichier sélectionné:', file.name, file.size, 'bytes');
      
      // Affiche le loader
      loader.classList.add('show');
      results.classList.remove('show');
      submitBtn.disabled = true;
      
      // Prépare le FormData
      const formData = new FormData();
      formData.append('file', file);
      
      }};
    
    function escapeHtml(text) {{
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }}
    
    function showError(message) {{
      results.classList.add('show');
      document.getElementById('status').className = 'status error';
      document.getElementById('status').textContent = '❌ Erreur';
      document.getElementById('fileInfo').innerHTML = `<strong>Message :</strong> ${{escapeHtml(message)}}`;
      document.getElementById('downloadSection').innerHTML = '';
      document.getElementById('logSection').innerHTML = '';
      document.getElementById('previewSection').innerHTML = '';
    }}
    
    function showResults(data) {{
      results.classList.add('show');
      
      // Status
      const statusEl = document.getElementById('status');
      statusEl.className = 'status ' + (data.success ? 'success' : 'error');
      statusEl.textContent = data.success ? '✅ Conversion réussie' : '❌ Échec de la conversion';
      
      // File info
      document.getElementById('fileInfo').innerHTML = `
        <strong>📄 Fichier original :</strong> ${{escapeHtml(data.original_filename)}}<br>
        <strong>💾 Taille :</strong> ${{(data.file_size / 1024).toFixed(1)}} KB<br>
        <strong>🔒 Fichier sauvegardé :</strong> <code>${{escapeHtml(data.safe_filename)}}</code>
      `;
      
      // Download button
      let downloadHtml = '';
      if (data.success && data.md_filename) {{
        downloadHtml = `
          <a href="/api/download/${{encodeURIComponent(data.md_filename)}}" class="download-btn">
            📥 Télécharger le Markdown (${{(data.md_size / 1024).toFixed(1)}} KB)
          </a>
        `;
      }}
      document.getElementById('downloadSection').innerHTML = downloadHtml;
      
      // Log
      document.getElementById('logSection').innerHTML = `
        <h3>📋 Journal de conversion</h3>
        <pre>${{escapeHtml(data.log_message)}}</pre>
      `;
      
      // Preview
      let previewHtml = '';
      if (data.success && data.preview) {{
        const moreLines = data.total_lines > 50 ? `<p class="muted">... et ${{data.total_lines - 50}} lignes supplémentaires</p>` : '';
        previewHtml = `
          <h3>📋 Aperçu (50 premières lignes)</h3>
          <pre class="preview">${{escapeHtml(data.preview)}}</pre>
          ${{moreLines}}
        `;
      }}
      document.getElementById('previewSection').innerHTML = previewHtml;
    }}
  </script>
</body>
</html>
    """
    return HTMLResponse(content=html)


@app.post("/api/convert")
async def api_convert(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    API de conversion PDF → Markdown (retourne JSON).
    """
    # Planifie le nettoyage des vieux fichiers
    background_tasks.add_task(cleanup_old_files)
    
    # Validation de l'extension
    original_filename = file.filename or "document.pdf"
    ext = Path(original_filename).suffix.lower()
    
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Extension non autorisée. Formats acceptés : {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Génération d'un nom de fichier sécurisé et unique
    safe_filename = generate_safe_filename(original_filename)
    pdf_path = UPLOAD_DIR / safe_filename
    md_path = pdf_path.with_suffix(".md")
    
    try:
        # Sauvegarde par chunks avec limite de taille
        file_size = await save_upload_chunked(file, pdf_path)
        
        # Validation de la signature PDF
        if not validate_pdf_signature(pdf_path):
            pdf_path.unlink()
            raise HTTPException(
                status_code=400,
                detail="Le fichier n'est pas un PDF valide (signature magique incorrecte)."
            )
        
        # Conversion avec timeout
        success, log_message = await run_docling_with_timeout(pdf_path, md_path)
        
        # Prépare la réponse JSON
        response_data = {
            "success": success,
            "original_filename": original_filename,
            "safe_filename": safe_filename,
            "file_size": file_size,
            "log_message": log_message,
            "md_filename": None,
            "md_size": None,
            "preview": None,
            "total_lines": 0
        }
        
        if success and md_path.exists():
            md_content = md_path.read_text(encoding="utf-8", errors="replace")
            preview_lines = md_content.splitlines()[:50]
            
            response_data.update({
                "md_filename": md_path.name,
                "md_size": md_path.stat().st_size,
                "preview": "\n".join(preview_lines),
                "total_lines": len(md_content.splitlines())
            })
        
        return JSONResponse(content=response_data)
    
    except ValueError as e:
        # Erreur de validation (taille, etc.)
        if pdf_path.exists():
            pdf_path.unlink()
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        # Erreur inattendue - nettoyage
        if pdf_path.exists():
            pdf_path.unlink()
        if md_path.exists():
            md_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur inattendue : {type(e).__name__}: {e}"
        )


@app.get("/api/download/{filename}")
async def download_markdown(filename: str):
    """
    Télécharge un fichier Markdown converti.
    """
    # Validation stricte du nom de fichier
    safe_name = os.path.basename(filename)
    if not safe_name or ".." in safe_name or "/" in safe_name or "\\" in safe_name:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide.")
    
    file_path = UPLOAD_DIR / safe_name
    
    # Vérifications de sécurité
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable.")
    
    if not file_path.is_relative_to(UPLOAD_DIR):
        raise HTTPException(status_code=403, detail="Accès refusé.")
    
    if file_path.suffix.lower() != ".md":
        raise HTTPException(status_code=400, detail="Seuls les fichiers Markdown peuvent être téléchargés.")
    
    return FileResponse(
        path=file_path,
        media_type="text/markdown; charset=utf-8",
        filename=file_path.name,
        headers={"Content-Disposition": f'attachment; filename="{file_path.name}"'}
    )


@app.get("/health")
async def health_check():
    """Endpoint de santé pour monitoring."""
    return {
        "status": "healthy",
        "upload_dir": str(UPLOAD_DIR),
        "upload_dir_exists": UPLOAD_DIR.exists(),
        "max_file_size_mb": MAX_FILE_SIZE_MB,
        "timeout_seconds": DOCLING_TIMEOUT_SECONDS
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)