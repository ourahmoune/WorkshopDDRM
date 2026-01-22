import sys
import re
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class MarkdownChunk:
    """Représente un chunk de texte avec ses métadonnées."""

    content: str
    header_path: List[str]  # Chemin hiérarchique des headers
    level: int  # Niveau du header (1-6) --> probleme docling : inconsistance de la hierarchisation, lock à 2
    start_line: int
    end_line: int

    def to_dict(self) -> Dict:
        """Convertit le chunk en dictionnaire."""
        return {
            "content": self.content,
            "header_path": " > ".join(self.header_path),
            "level": self.level,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "metadata": {"hierarchy": self.header_path, "section_level": self.level},
        }


class MarkdownChunker:
    """Découpe un fichier Markdown par headers pour un système RAG."""

    def __init__(self, max_chunk_size: Optional[int] = None):
        """
        Initialise le chunker.

        Args:
            max_chunk_size: Taille maximale d'un chunk en caractères (None = pas de limite)
        """
        self.max_chunk_size = max_chunk_size
        self.header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def chunk_by_headers(self, md_content: str) -> List[MarkdownChunk]:
        """
        Découpe le contenu Markdown par headers.

        Args:
            md_content: Contenu du fichier Markdown

        Returns:
            Liste de MarkdownChunk
        """
        lines = md_content.split("\n")
        chunks = []
        header_stack = []  # Pile pour suivre la hiérarchie
        current_content = []
        current_start = 0
        current_level = 0
        threshold_title = 150

        for i, line in enumerate(lines):
            header_match = self.header_pattern.match(line)

            if header_match:
                # Sauvegarder le chunk précédent si existe
                if current_content:
                    chunk = self._create_chunk(
                        current_content,
                        header_stack.copy(),
                        current_level,
                        current_start,
                        i - 1,
                        threshold_title,
                    )
                    chunks.append(chunk)
                    current_content = []

                # Traiter le nouveau header
                level = len(header_match.group(1))
                title = header_match.group(2).strip()

                # Ajuster la pile de headers selon le niveau
                while header_stack and header_stack[-1]["level"] >= level:
                    header_stack.pop()

                header_stack.append({"level": level, "title": title})
                current_level = level
                current_start = i
                current_content.append(line)
            else:
                current_content.append(line)

        # Ajouter le dernier chunk
        if current_content:
            chunk = self._create_chunk(
                current_content,
                header_stack.copy(),
                current_level,
                current_start,
                len(lines) - 1,
                threshold_title,
            )
            chunks.append(chunk)

        # Subdiviser les chunks trop grands si nécessaire
        if self.max_chunk_size:
            chunks = self._subdivide_large_chunks(chunks)

        return chunks

    def _create_chunk(
        self,
        content_lines: List[str],
        header_stack: List[Dict],
        level: int,
        start: int,
        end: int,
        threshold_title: int,
    ) -> MarkdownChunk:
        """Crée un MarkdownChunk à partir des données."""
        content = "\n".join(content_lines).strip()
        header_path = [h["title"] for h in header_stack]

        return MarkdownChunk(
            content=content,
            header_path=header_path if header_path else ["Document Root"],
            level=level,
            start_line=start,
            end_line=end,
        )

    def _subdivide_large_chunks(
        self, chunks: List[MarkdownChunk]
    ) -> List[MarkdownChunk]:
        """Subdivise les chunks dépassant la taille maximale."""
        result = []

        for chunk in chunks:
            if len(chunk.content) <= self.max_chunk_size:
                result.append(chunk)
            else:
                # Diviser par paragraphes
                paragraphs = chunk.content.split("\n\n")
                sub_content = []
                sub_start = chunk.start_line

                for para in paragraphs:
                    if (
                        sum(len(p) for p in sub_content) + len(para)
                        > self.max_chunk_size
                        and sub_content
                    ):
                        # Créer un sous-chunk
                        sub_chunk = MarkdownChunk(
                            content="\n\n".join(sub_content),
                            header_path=chunk.header_path,
                            level=chunk.level,
                            start_line=sub_start,
                            end_line=sub_start + len(sub_content) - 1,
                        )
                        result.append(sub_chunk)
                        sub_content = [para]
                        sub_start += len(sub_content)
                    else:
                        sub_content.append(para)

                # Ajouter le dernier sous-chunk
                if sub_content:
                    sub_chunk = MarkdownChunk(
                        content="\n\n".join(sub_content),
                        header_path=chunk.header_path,
                        level=chunk.level,
                        start_line=sub_start,
                        end_line=chunk.end_line,
                    )
                    result.append(sub_chunk)

        return result

    def load_and_chunk(self, filepath: str) -> List[MarkdownChunk]:
        """
        Charge un fichier Markdown et le découpe en chunks.

        Args:
            filepath: Chemin vers le fichier .md

        Returns:
            Liste de MarkdownChunk
        """
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        return self.chunk_by_headers(content)


def print_usage():
    """Affiche l'aide d'utilisation."""
    print(
        """
╔══════════════════════════════════════════════════════════════╗
║                   Chunkerer Markdown                         ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    python3 chunkerer.py <input_file>

Arguments:
    input_file   : Fichier source (MARKDOWN)
    

Exemples:
    python3 docling_extractor.py rapport.md
    """
    )


# Exemple d'utilisation
if __name__ == "__main__":

    """Point d'entrée principal."""
    # Vérifier les arguments
    if len(sys.argv) != 2:
        print("Erreur: Nombre d'arguments incorrect \n")
        print_usage()
        sys.exit(1)

    input_file = sys.argv[1]

    chunker = MarkdownChunker(max_chunk_size=1024)
    # Exemple de contenu Markdown
    chunks = chunker.load_and_chunk(input_file)

    print(f"Nombre de chunks: {len(chunks)}\n")

    for i, chunk in enumerate(chunks, 1):
        print(f"--- Chunk {i} ---")
        print(f"Hiérarchie: {chunk.to_dict()['header_path']}")
        print(f"Niveau: {chunk.level}")
        print(f"Lignes: {chunk.start_line}-{chunk.end_line}")
        print(f"Contenu ({len(chunk.content)} chars):")
        print(
            chunk.content[:150] + "..." if len(chunk.content) > 150 else chunk.content
        )
        print()
