import json
from pathlib import Path
from sentence_transformers import SentenceTransformer

# Configuration
INPUT_FILE = "resultats_questions.json"  # À modifier avec votre chemin
OUTPUT_FILE = "output.json"  # À modifier avec votre chemin
MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"  # Modèle Qwen3 depuis HuggingFace

# Charger le modèle une seule fois
print("Chargement du modèle Qwen3-Embedding-0.6B...")
model = SentenceTransformer(MODEL_NAME)
print("✓ Modèle chargé avec succès\n")

def load_json(filepath):
    """Charge le fichier JSON d'entrée"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_embedding(text):
    """Récupère l'embedding d'un texte"""
    try:
        embedding = model.encode(text, convert_to_tensor=False)
        return embedding.tolist()  # Convertir en liste pour JSON
    except Exception as e:
        print(f"Erreur lors de l'embedding: {e}")
        return None

def embed_questions(data):
    """Embedde toutes les questions du dataset"""
    
    # Si c'est une liste, traiter chaque élément
    if isinstance(data, list):
        items = data
    else:
        items = [data]
    
    total_questions = 0
    # Compter le nombre total de questions
    for item in items:
        if 'questions' in item:
            total_questions += len(item['questions'])
    
    current_idx = 1
    for item in items:
        if 'questions' in item:
            # Embedder chaque question
            for question in item['questions']:
                if 'question' in question:
                    text = question['question']
                    embedding = get_embedding(text)
                    
                    if embedding:
                        question['embedding'] = embedding
                        print(f"✓ [{current_idx}/{total_questions}] Embeddée: {text[:60]}...")
                    else:
                        print(f"✗ [{current_idx}/{total_questions}] Erreur pour: {text[:60]}...")
                    
                    current_idx += 1
    
    return data

def save_json(data, filepath):
    """Sauvegarde les données en JSON"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Fichier sauvegardé: {filepath}")

def main():
    """Fonction principale"""
    print("=" * 70)
    print("Embedding avec Qwen3-Embedding-0.6B (SentenceTransformers)")
    print("=" * 70)
    
    print("\n1. Chargement du fichier JSON...")
    try:
        data = load_json(INPUT_FILE)
        print(f"   ✓ Fichier chargé avec succès")
    except FileNotFoundError:
        print(f"   ✗ Erreur: Le fichier '{INPUT_FILE}' n'existe pas")
        return
    except json.JSONDecodeError:
        print(f"   ✗ Erreur: Le fichier JSON n'est pas valide")
        return
    
    print("\n2. Embedding des questions...")
    data_with_embeddings = embed_questions(data)
    
    print("\n3. Sauvegarde des résultats...")
    save_json(data_with_embeddings, OUTPUT_FILE)
    
    print("\n" + "=" * 70)
    print("✓ Processus terminé avec succès!")
    print("=" * 70)

if __name__ == "__main__":
    main()