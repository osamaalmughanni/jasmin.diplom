import os
import subprocess
from glob import glob
from PyPDF2 import PdfMerger

def generate_pdf():
    """
    Generate a German cover page PDF and a main document PDF, then merge them,
    ensuring:
    1) No word is ever split with a dash (no hyphenation).
    2) Words do not break across lines or pages.
    3) We use Pandoc directly (via subprocess) instead of pypandoc.
    4) Proper handling of Unicode (UTF-8) on Windows.
    """

    input_dir = "md"  # Folder where markdown files are stored
    output_pdf = "da.pdf"
    cover_pdf = "temp_cover.pdf"
    document_pdf = "temp_document.pdf"
    disable_hyphenation_file = "disable_hyphenation.tex"

    # Create a small LaTeX header file to disable hyphenation completely
    disable_hyphenation = r"""
\usepackage[none]{hyphenat}
\sloppy
"""
    # Write this header to a temporary file
    with open(disable_hyphenation_file, "w", encoding="utf-8") as f:
        f.write(disable_hyphenation)

    # Ensure the input directory exists
    if not os.path.exists(input_dir):
        print(f"❌ Verzeichnis '{input_dir}' existiert nicht.")
        return

    # Get all Markdown files in sorted order
    md_files = sorted(glob(os.path.join(input_dir, "*.md")))

    if not md_files:
        print(f"❌ Keine Markdown-Dateien gefunden in '{input_dir}'.")
        return

    # 1) Cover Page Generation (first Markdown file)
    try:
        with open(md_files[0], "r", encoding="utf-8") as f:
            cover_md = f.read()

        cmd_cover = [
            "pandoc",
            "-f", "markdown+footnotes",         # Input format with footnotes
            "-o", cover_pdf,                    # Output PDF file
            "--pdf-engine=xelatex",             # Use XeLaTeX
            "-V", "geometry=a4paper",
            "-V", "fontsize=14pt",
            "-V", "mainfont=Lora",
            "-V", "margin=1in",
            "-H", disable_hyphenation_file      # Include header to disable hyphenation
        ]

        # Explicitly specify UTF-8 encoding to avoid charmap issues on Windows
        subprocess.run(cmd_cover, input=cover_md, text=True, check=True, encoding="utf-8")
        print(f"✅ Titelseite erstellt: {cover_pdf}")

    except subprocess.CalledProcessError as e:
        print(f"❌ Fehler bei der Erstellung der Titelseite: {e}")
        return

    # 2) Main Document Generation (remaining Markdown files)
    #    We insert a \newpage before each file's content
    combined_md = "\\newpage\n\n"
    for md_file in md_files[1:]:
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
        combined_md += f"\\newpage\n\n{content}"

    try:
        cmd_document = [
            "pandoc",
            "-f", "markdown+footnotes",
            "-o", document_pdf,
            "--pdf-engine=xelatex",
            "-V", "geometry=a4paper",
            "-V", "fontsize=12pt",
            "-V", "mainfont=Lora",
            "-V", "margin=1in",
            "-V", "lang=de",      # German language (but hyphenation disabled via header)
            "--toc",              # Table of contents
            "--number-sections",  # Numbered sections
            "-H", disable_hyphenation_file
        ]

        # Explicitly specify UTF-8 encoding to avoid charmap issues on Windows
        subprocess.run(cmd_document, input=combined_md, text=True, check=True, encoding="utf-8")
        print(f"✅ Hauptdokument erstellt: {document_pdf}")

    except subprocess.CalledProcessError as e:
        print(f"❌ Fehler bei der Erstellung des Hauptdokuments: {e}")
        return

    # 3) Merge Cover Page and Main Document
    try:
        merger = PdfMerger()
        merger.append(cover_pdf)
        merger.append(document_pdf)
        merger.write(output_pdf)
        merger.close()
        print(f"✅ Finale PDF erfolgreich erstellt: {output_pdf}")

        # 4) Delete Temporary Files
        os.remove(cover_pdf)
        os.remove(document_pdf)
        os.remove(disable_hyphenation_file)
        print(f"🗑️ Temporäre Dateien gelöscht: {cover_pdf}, {document_pdf}, {disable_hyphenation_file}")

    except Exception as e:
        print(f"❌ Fehler beim Zusammenfügen der PDFs: {e}")

if __name__ == "__main__":
    generate_pdf()
