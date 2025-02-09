import os
import subprocess
from glob import glob
from PyPDF2 import PdfMerger

def generate_pdf():
    """
    Generate a German cover page PDF and a main document PDF, then merge them, ensuring:
      1) The cover page has NO page numbering at all.
      2) A table of contents (TOC) is generated but also has NO page numbers.
      3) Actual page numbering begins AFTER the TOC on the true document start page.
      4) No words are split with a dash/hyphen across lines (hyphenation disabled).
      5) Titles are NOT justified, but paragraphs are fully justified.
      6) Use Pandoc via subprocess (not pypandoc), with proper UTF-8 handling on Windows.
    """

    input_dir = "md"  # Folder containing the Markdown files
    output_pdf = "da.pdf"
    cover_pdf = "temp_cover.pdf"
    document_pdf = "temp_document.pdf"
    disable_hyphenation_file = "disable_hyphenation.tex"

    # Create a small LaTeX header file to disable hyphenation and justify only paragraphs
    disable_hyphenation = r"""
\usepackage[none]{hyphenat}
\sloppy
\usepackage{titlesec}
\titleformat{\section}{\raggedright\Large\bfseries}{}{0em}{}
\titleformat{\subsection}{\raggedright\large\bfseries}{}{0em}{}
\titleformat{\subsubsection}{\raggedright\normalsize\bfseries}{}{0em}{}
"""
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

    ########################################################################
    # 1) Cover Page Generation (no page numbering at all)
    ########################################################################
    try:
        with open(md_files[0], "r", encoding="utf-8") as f:
            original_cover_md = f.read()

        # Prepend LaTeX commands to ensure no page numbering on cover
        cover_md = (
            r"\pagenumbering{gobble}" "\n"
            r"\thispagestyle{empty}" "\n"
            + original_cover_md
        )

        cmd_cover = [
            "pandoc",
            "-f", "markdown+footnotes",
            "-o", cover_pdf,
            "--pdf-engine=xelatex",
            "-V", "geometry=a4paper",
            "-V", "fontsize=14pt",
            "-V", "mainfont=Lora",
            "-V", "margin=1in",
            "-H", disable_hyphenation_file
        ]

        subprocess.run(cmd_cover, input=cover_md, text=True, check=True, encoding="utf-8")
        print(f"✅ Titelseite erstellt: {cover_pdf}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Fehler bei der Erstellung der Titelseite: {e}")
        return

    ########################################################################
    # 2) Main Document Generation
    ########################################################################
    main_doc_header = r"""
\pagenumbering{gobble}
\thispagestyle{empty}
\renewcommand*\contentsname{Inhaltsverzeichnis}
\tableofcontents
\clearpage
\pagenumbering{arabic}
\pagestyle{plain}
"""

    combined_md = main_doc_header

    for md_file in md_files[1:]:
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
        combined_md += f"\n\\newpage\n\n{content}\n"

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
            "-V", "lang=de",
            "--number-sections",
            "-H", disable_hyphenation_file
        ]

        subprocess.run(cmd_document, input=combined_md, text=True, check=True, encoding="utf-8")
        print(f"✅ Hauptdokument erstellt: {document_pdf}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Fehler bei der Erstellung des Hauptdokuments: {e}")
        return

    ########################################################################
    # 3) Merge Cover Page and Main Document
    ########################################################################
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
