import json
from pathlib import Path
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Configuration
JSON_FILE = "output.json"  # Fichier avec tous les vecteurs
TOP_K = 4  # Nombre de chunks à retourner

def load_json(filepath):
    """Charge le fichier JSON"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def cosine_similarity_score(vec1, vec2):
    """Calcule la similarité cosinus entre deux vecteurs"""
    vec1 = np.array(vec1).reshape(1, -1)
    vec2 = np.array(vec2).reshape(1, -1)
    return cosine_similarity(vec1, vec2)[0][0]

def search_similar_chunks(data, question_embedding, top_k=TOP_K):
    """Trouve les chunks les plus similaires"""
    
    # Si c'est une liste, traiter chaque élément
    if isinstance(data, list):
        items = data
    else:
        items = [data]
    
    similarities = []
    
    # Parcourir tous les chunks
    for item in items:
        chunk_id = item.get('chunk_id', 'Unknown')
        chunk_content = item.get('chunk_content', '')
        
        if 'questions' in item:
            # Pour chaque question du chunk
            for question_obj in item['questions']:
                if 'embedding' in question_obj:
                    question_text = question_obj.get('question', '')
                    embedding = question_obj['embedding']
                    
                    # Calculer la similarité cosinus
                    similarity = cosine_similarity_score(question_embedding, embedding)
                    
                    similarities.append({
                        'chunk_id': chunk_id,
                        'chunk_content': chunk_content,
                        'question': question_text,
                        'similarity': float(similarity)
                    })
    
    # Trier par similarité décroissante et retourner les top K
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    return similarities[:top_k]

def main():
    """Fonction principale"""
    print("=" * 80)
    print("Recherche de chunks similaires par similarité cosinus")
    print("=" * 80 + "\n")
    
    # Charger les données
    print(f"1. Chargement du fichier JSON: {JSON_FILE}")
    try:
        data = load_json(JSON_FILE)
        print("   ✓ Fichier chargé avec succès\n")
    except FileNotFoundError:
        print(f"   ✗ Erreur: Le fichier '{JSON_FILE}' n'existe pas")
        return
    except json.JSONDecodeError:
        print(f"   ✗ Erreur: Le fichier JSON n'est pas valide")
        return
    
    # Demander le vecteur d'embedding
    print("2. Entrez votre vecteur d'embedding (séparé par des virgules ou des espaces):")
    user_input = input("   > ").strip()
    
    try:
        # Nettoyer le vecteur (supprimer les crochets et espaces)
        user_input = user_input.strip().lstrip('[').rstrip(']').strip()
        
        # Essayer de parser le vecteur
        if ',' in user_input:
            question_embedding = [float(x.strip()) for x in user_input.split(',')]
        else:
            question_embedding = [float(x.strip()) for x in user_input.split()]
        
        print(f"\n   ✓ Vecteur chargé (dimension: {len(question_embedding)})\n")
    except ValueError as e:
        print(f"   ✗ Erreur: Format de vecteur invalide - {e}")
        return
    
    # Rechercher les chunks similaires
    print("3. Recherche des chunks les plus similaires...")
    results = search_similar_chunks(data, question_embedding, TOP_K)
    
    # Afficher les résultats
    print("\n" + "=" * 80)
    print(f"Top {TOP_K} chunks les plus proches")
    print("=" * 80 + "\n")
    
    for idx, result in enumerate(results, 1):
        print(f"Rang #{idx}")
        print(f"  Similarité: {result['similarity']:.6f}")
        print(f"  Chunk ID: {result['chunk_id']}")
        print(f"  Question: {result['question'][:70]}...")
        print(f"  Contenu: {result['chunk_content'][:70]}...")
        print()
    
    # Optionnel: Sauvegarder les résultats
    save_option = input("Voulez-vous sauvegarder les résultats? (o/n): ").strip().lower()
    if save_option == 'o':
        output_file = "search_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"✓ Résultats sauvegardés dans '{output_file}'")

if __name__ == "__main__":
    main()