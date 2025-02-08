import os
import pypandoc
from glob import glob
from PyPDF2 import PdfMerger

def generate_pdf():
    """ Generate a German cover page PDF and a main document PDF, then merge them. """
    
    input_dir = "md"  # Folder where markdown files are stored
    output_pdf = "Diplomarbeit.pdf"
    cover_pdf = "temp_cover.pdf"
    document_pdf = "temp_document.pdf"

    # Ensure the input directory exists
    if not os.path.exists(input_dir):
        print(f"❌ Verzeichnis '{input_dir}' existiert nicht.")
        return

    # Get all Markdown files in sorted order
    md_files = sorted(glob(os.path.join(input_dir, "*.md")))

    if not md_files:
        print(f"❌ Keine Markdown-Dateien gefunden in '{input_dir}'.")
        return

    # 1️⃣ Cover Page Generation (First Markdown File)
    cover_md = open(md_files[0], "r", encoding="utf-8").read()
    try:
        pypandoc.convert_text(cover_md, "pdf", format="md", outputfile=cover_pdf, extra_args=[
            "--pdf-engine=xelatex",
            "-V", "geometry:a4paper",
            "-V", "fontsize=14pt",
            "-V", "mainfont=Lora",
            "-V", "margin=1in"
        ])
        print(f"✅ Titelseite erstellt: {cover_pdf}")
    except OSError as e:
        print(f"❌ Fehler bei der Erstellung der Titelseite: {e}")
        return

    # 2️⃣ Main Document Generation (Remaining Markdown Files)
    combined_md = "\\newpage\n\n"  # Ensures TOC starts on a new page
    for md_file in md_files[1:]:
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
            combined_md += f"\\newpage\n\n{content}"  # New page before each markdown file

    try:
        pypandoc.convert_text(combined_md, "pdf", format="md", outputfile=document_pdf, extra_args=[
            "--pdf-engine=xelatex",
            "-V", "geometry:a4paper",
            "-V", "fontsize=12pt",
            "-V", "mainfont=Lora",
            "-V", "margin=1in",
            "-V", "lang=de",  # Set document language to German
            "--toc",  # Generates TOC dynamically (will now be "Inhaltsverzeichnis")
            "--number-sections"
        ])
        print(f"✅ Hauptdokument erstellt: {document_pdf}")
    except OSError as e:
        print(f"❌ Fehler bei der Erstellung des Hauptdokuments: {e}")
        return

    # 3️⃣ Merge Cover Page and Main Document
    try:
        merger = PdfMerger()
        merger.append(cover_pdf)  # First the cover page
        merger.append(document_pdf)  # Then the full document
        merger.write(output_pdf)
        merger.close()

        print(f"✅ Finale PDF erfolgreich erstellt: {output_pdf}")

        # 4️⃣ Delete Temporary Files
        os.remove(cover_pdf)
        os.remove(document_pdf)
        print(f"🗑️ Temporäre Dateien gelöscht: {cover_pdf}, {document_pdf}")

    except Exception as e:
        print(f"❌ Fehler beim Zusammenfügen der PDFs: {e}")

if __name__ == "__main__":
    generate_pdf()
