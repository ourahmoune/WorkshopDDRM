## Usage

To convert pdf into md file
`docling_extractor.py`

To divid into chunk md file
`chunkerer.py`

## Etape de traitement

- Fichier DDRM source : PDF
  - Traitement docling (docling_extractor.py)
- Fichier MarkDown hierarchisé
  - Chunkerisation (chunkerer.py)
  - Generation des questions (questions_generator.py)
- Json des chunks & questions
  - Embedding (qwen3-embedding) , (embedding.py)
- Interface de chat-bot 
  - ui.py 
- Matrice

## Utilisation

- Question de l'utilisateur
  - Embedding de la question
  - Comparaison avec la matrice via similarité cosinus
  - Recuperation des chunks associé
  - Reformulation des chunks
  - Envoie de la réponce
