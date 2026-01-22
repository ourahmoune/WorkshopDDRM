import json
import re
import sys
import argparse
from chunkerer import MarkdownChunker
from dotenv import load_dotenv
import os
from groq import Groq

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

def generate_questions(chunk_id, chunk_content):
    """Génère des questions pour un chunk donné."""
    prompt = f"""Tu es un expert en création de questions.
    Analyse le chunk de texte suivant et génère exactement 3-4 questions 
    que ce chunk peut répondre.

    Les questions doivent être :
    - Spécifiques et ancrées dans le contenu du chunk
    - Formulées clairement, sans ambiguïté

    Format ta réponse en JSON :
    {{
    "chunk_id": "{chunk_id}",
    "chunk_content" : "{chunk_content}",
    "questions": [
        {{
        "question": "..."
        }}
    ]
    }} 
    
    CHUNK :
    {chunk_content}"""
    
    message = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.choices[0].message.content.strip()
    
    # Essayer de parser le JSON directement
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        # Supprimer les backticks et texte avant/après
        cleaned = re.sub(r'```json\n?', '', response_text)
        cleaned = re.sub(r'```\n?', '', cleaned)
        cleaned = re.sub(r'^[^{]*', '', cleaned)  # Supprimer tout avant la première accolade
        cleaned = re.sub(r'[^}]*$', '', cleaned)  # Supprimer tout après la dernière accolade
        
        try:
            return json.loads(cleaned.strip())
        except json.JSONDecodeError:
            # Dernière tentative : chercher juste le JSON entre accolades
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    return {"chunk_id": chunk_id, "questions": [], "error": "Parsing failed"}
            return {"chunk_id": chunk_id, "questions": [], "error": "No JSON found"}

def main():
    # Configuration du parser d'arguments
    parser = argparse.ArgumentParser(
        description="Génère des questions à partir d'un fichier Markdown"
    )
    parser.add_argument(
        "markdown_file",
        help="Chemin du fichier Markdown à traiter"
    )
    parser.add_argument(
        "-o", "--output",
        default="resultats_questions.json",
        help="Nom du fichier JSON de sortie (défaut: resultats_questions.json)"
    )
    
    args = parser.parse_args()
    
    # Vérifier que le fichier Markdown existe
    if not os.path.exists(args.markdown_file):
        print(f"Erreur : Le fichier '{args.markdown_file}' n'existe pas.")
        sys.exit(1)
    
    # Charger et découper le fichier Markdown
    print(f"Chargement du fichier : {args.markdown_file}")
    chunker = MarkdownChunker(max_chunk_size=1024)
    chunks = chunker.load_and_chunk(args.markdown_file)
    
    print(f"Nombre de chunks: {len(chunks)}\n")
    
    # Appliquer à tous les chunks
    results = []
    for i, chunk in enumerate(chunks):
        print(f"Traitement chunk {i}...")
        result = generate_questions(i, chunk.content)
        results.append(result)
    
    print(f"\nTraitement terminé: {len(results)} résultats")
    
    # Sauvegarder les résultats
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"Résultats sauvegardés dans '{args.output}'")

if __name__ == "__main__":
    main()