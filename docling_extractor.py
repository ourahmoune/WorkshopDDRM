"""
Extracteur de documents vers Markdown avec Docling
Supporte: PDF, DOCX, PPTX, images, HTML
Optimisé pour la qualité et la structure du Markdown généré

Usage:
    python3 docling_extractor.py input.pdf output.md
    python3 docling_extractor.py rapport.pdf chunks/  # Avec chunking automatique
"""

import sys
from pathlib import Path
from typing import Optional, List
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from hierarchical.postprocessor import ResultPostprocessor


class DoclingMarkdownExtractor:
    """Extracteur de documents vers Markdown avec Docling."""

    def __init__(
        self,
        ocr_enabled: bool = True,
        table_structure: bool = True,
        extract_images: bool = True,
        image_export_mode: str = "placeholder",
    ):
        """
        Initialise l'extracteur Docling.

        Args:
            ocr_enabled: Activer l'OCR pour les PDF scannés
            table_structure: Préserver la structure des tableaux
            extract_images: Extraire les images du document
            image_export_mode: Mode d'export des images
        """
        self.ocr_enabled = ocr_enabled
        self.table_structure = table_structure
        self.extract_images = extract_images
        self.image_export_mode = image_export_mode

        # Configuration du pipeline PDF
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = ocr_enabled
        pipeline_options.do_table_structure = table_structure

        # Configuration de l'extracteur
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options, backend=PyPdfiumDocumentBackend
                )
            }
        )

    def convert_to_markdown(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        add_metadata: bool = True,
    ) -> str:
        """
        Convertit un document en Markdown.

        Args:
            input_path: Chemin vers le document source
            output_path: Chemin de sortie
            add_metadata: Ajouter des métadonnées en en-tête

        Returns:
            Contenu Markdown généré
        """
        input_file = Path(input_path)

        if not input_file.exists():
            raise FileNotFoundError(f"Le fichier {input_path} n'existe pas")

        print(f"Conversion de {input_file.name}...")

        # Conversion du document
        result = self.converter.convert(str(input_file))
        ResultPostprocessor(result).process()

        # Génération du Markdown
        markdown_content = result.document.export_to_markdown()

        # Ajouter les métadonnées si demandé
        if add_metadata:
            metadata = self._generate_metadata(result, input_file)
            markdown_content = metadata + "\n\n" + markdown_content

        # Post-traitement pour améliorer la qualité
        markdown_content = self._post_process_markdown(markdown_content)

        # Sauvegarder
        if output_path:
            output_file = Path(output_path)

            # Si c'est un dossier, créer le nom de fichier
            if output_file.suffix == "" or output_file.is_dir():
                output_file = output_file / f"{input_file.stem}.md"

            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            print(f"Markdown sauvegardé: {output_file}")
            print(f"Taille: {len(markdown_content)} caractères")

        return markdown_content

    def _generate_metadata(self, result, input_file: Path) -> str:
        """Génère un en-tête de métadonnées."""
        doc = result.document

        metadata = [
            "---",
            f"source: {input_file.name}",
            f"format: {input_file.suffix[1:].upper()}",
        ]

        # Ajouter le titre si disponible
        if hasattr(doc, "title") and doc.title:
            metadata.append(f"title: {doc.title}")

        # Nombre de pages pour les PDF
        if hasattr(doc, "pages"):
            metadata.append(f"pages: {len(doc.pages)}")

        metadata.append("---")

        return "\n".join(metadata)

    def _post_process_markdown(self, content: str) -> str:
        """Post-traite le Markdown pour améliorer sa qualité."""
        lines = content.split("\n")
        processed = []
        prev_empty = False

        for line in lines:
            # Éviter les lignes vides multiples
            if line.strip() == "":
                if not prev_empty:
                    processed.append(line)
                    prev_empty = True
            else:
                processed.append(line)
                prev_empty = False

        # Normaliser les espaces autour des headers
        result = []
        for i, line in enumerate(processed):
            if line.startswith("#"):
                # Ajouter une ligne vide avant le header
                if i > 0 and processed[i - 1].strip() != "":
                    result.append("")
                result.append(line)
            else:
                result.append(line)

        return "\n".join(result).strip() + "\n"


def print_usage():
    """Affiche l'aide d'utilisation."""
    print(
        """
╔══════════════════════════════════════════════════════════════╗
║           Extracteur Markdown avec Docling                   ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    python3 docling_extractor.py <input_file> <output_path>

Arguments:
    input_file   : Fichier source (PDF, DOCX, PPTX, HTML, image)
    output_path  : Fichier .md ou dossier de sortie

Exemples:
    python3 docling_extractor.py rapport.pdf rapport.md
    python3 docling_extractor.py document.pdf output/
    python3 docling_extractor.py presentation.pptx markdown/

Options disponibles (modifier dans le code):
    - OCR activé par défaut
    - Structure des tableaux préservée
    - Métadonnées ajoutées automatiquement
    """
    )


def main(input_file,output_path):
    """Point d'entrée principal."""


    # Vérifier que le fichier existe
    if not Path(input_file).exists():
        print(f"Erreur: Le fichier '{input_file}' n'existe pas")
        sys.exit(1)

    try:
        # Créer l'extracteur avec configuration optimale
        extractor = DoclingMarkdownExtractor(
            ocr_enabled=True,
            table_structure=True,
            extract_images=True,
            image_export_mode="placeholder",
        )

        print("\n" + "=" * 60)
        print("  EXTRACTION MARKDOWN AVEC DOCLING")
        print("=" * 60 + "\n")

        # Convertir
        markdown = extractor.convert_to_markdown(
            input_path=input_file, output_path=output_path, add_metadata=True
        )

        print("\n" + "=" * 60)
        print("Conversion réussie !")
        print("=" * 60 + "\n")

        # Afficher un aperçu
        lines = markdown.split("\n")
        preview_lines = min(20, len(lines))
        print(f"Aperçu ({preview_lines} premières lignes):\n")
        print("\n".join(lines[:preview_lines]))
        if len(lines) > preview_lines:
            print("\n[...]\n")

    except Exception as e:
        print(f"\nErreur lors de la conversion: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
