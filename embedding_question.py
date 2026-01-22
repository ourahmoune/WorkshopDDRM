from sentence_transformers import SentenceTransformer
import json

# Charger le modèle une seule fois
print("Chargement du modèle Qwen3-Embedding-0.6B...")
model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")
print("✓ Modèle chargé avec succès\n")

def get_embedding(question):
    """Récupère l'embedding d'une question"""
    try:
        embedding = model.encode(question, convert_to_tensor=False)
        return embedding.tolist()  # Convertir en liste pour JSON
    except Exception as e:
        print(f"Erreur lors de l'embedding: {e}")
        return None

def main():
    """Fonction principale"""
    print("=" * 70)
    print("Embedding d'une question avec Qwen3-Embedding-0.6B")
    print("=" * 70 + "\n")
    
    # Demander la question à l'utilisateur
    question = input("Entrez votre question: ").strip()
    
    if not question:
        print("❌ Erreur: Vous devez entrer une question")
        return
    
    print("\n⏳ Embedding en cours...")
    embedding = get_embedding(question)
    
    if embedding:
        print("\n" + "=" * 70)
        print(f"Question: {question}")
        print("-" * 70)
        print(f"Vecteur d'embedding (dimension: {len(embedding)}):")
        print(embedding)
        print("=" * 70)
        
        # Optionnel: Sauvegarder en JSON
        save_option = input("\nVoulez-vous sauvegarder le résultat? (o/n): ").strip().lower()
        if save_option == 'o':
            result = {
                "question": question,
                "embedding": embedding
            }
            filename = "embedding_result.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"✓ Résultat sauvegardé dans '{filename}'")
    else:
        print("❌ Erreur lors de l'embedding")

if __name__ == "__main__":
    main()