
import os
import re
import subprocess
from glob import glob
from PyPDF2 import PdfMerger

def generate_dynamic_font_header(header_filename="dynamic_font.tex", fonts_dir="fonts"):
    """
    Scans the fonts directory for .ttf and .otf files, groups them by font family,
    and generates a LaTeX header file that dynamically sets the main font (using its regular
    file) and registers available styles (bold, italic, bolditalic, and any extras).

    Naming convention: Font files should be named as FamilyName-Style.ttf (or .otf),
    e.g. Lora-Regular.ttf, Lora-Bold.ttf, Lora-Italic.otf, etc.
    """
    if not os.path.exists(fonts_dir):
        print(f"❌ Fonts directory '{fonts_dir}' does not exist.")
        return False

    # Gather all .ttf and .otf files.
    font_files = glob(os.path.join(fonts_dir, "*.ttf")) + glob(os.path.join(fonts_dir, "*.otf"))
    if not font_files:
        print(f"❌ No font files found in '{fonts_dir}'.")
        return False

    families = {}
    # Process each font file.
    for font_path in font_files:
        base = os.path.basename(font_path)  # e.g. Lora-Bold.ttf
        name, ext = os.path.splitext(base)
        # Expect a filename like Family-Style. If no dash found, assume "regular".
        if '-' in name:
            family, style = name.rsplit('-', 1)
        else:
            family = name
            style = "regular"
        family = family.strip()
        style = style.lower().strip()
        # Normalize common style names.
        if style in ("regular", "normal", "book"):
            style = "regular"
        elif style in ("bold", "black", "heavy"):
            style = "bold"
        elif style in ("italic", "oblique"):
            style = "italic"
        elif style in ("bolditalic", "bold-italic"):
            style = "bolditalic"
        # Group by family.
        if family not in families:
            families[family] = {}
        if style in families[family]:
            print(f"⚠️ Duplicate style '{style}' for font family '{family}'. Overriding previous entry.")
        families[family][style] = base

    # Select the best family (here, the one with the most variants)
    best_family = None
    best_count = 0
    for fam, variants in families.items():
        if len(variants) > best_count:
            best_count = len(variants)
            best_family = fam

    if best_family is None:
        print("❌ No valid font families found.")
        return False

    variants = families[best_family]
    # Ensure a "regular" variant exists.
    if "regular" not in variants:
        fallback_variant = list(variants.values())[0]
        variants["regular"] = fallback_variant
        print(f"⚠️ No regular variant found for font family '{best_family}'. Using '{fallback_variant}' as regular.")

    # Begin building the LaTeX header.
    header_lines = []
    header_lines.append("% Dynamisch generierter Font-Header")
    header_lines.append("\\usepackage{fontspec}")
    # Add Ligatures=TeX to better handle special characters.
    options = [f"Path={fonts_dir}/", "Ligatures=TeX"]
    if "bold" in variants:
        options.append("BoldFont={" + variants["bold"] + "}")
    if "italic" in variants:
        options.append("ItalicFont={" + variants["italic"] + "}")
    if "bolditalic" in variants:
        options.append("BoldItalicFont={" + variants["bolditalic"] + "}")
    options_str = ", ".join(options)
    # Use the regular file (with extension) as the main font.
    header_lines.append(f"\\setmainfont[{options_str}]{{{variants['regular']}}}")

    # For any additional (nonstandard) styles, register them as new font faces.
    main_styles = {"regular", "bold", "italic", "bolditalic"}
    additional_styles = [s for s in variants if s not in main_styles]
    for style in additional_styles:
        cmd_name = "\\" + best_family.replace(" ", "").lower() + style + "font"
        header_lines.append(f"\\newfontface{cmd_name}[Path={fonts_dir}/]{{{variants[style]}}}")

    header_content = "\n".join(header_lines) + "\n"

    try:
        with open(header_filename, "w", encoding="utf-8") as f:
            f.write(header_content)
        print(f"✅ Dynamischer Font-Header erstellt: {header_filename}")
        return True
    except Exception as e:
        print(f"❌ Fehler beim Schreiben des dynamischen Font-Headers: {e}")
        return False

def replace_pdf_links(md_content):
    """
    Replaces markdown links to PDFs with LaTeX code to include the PDF pages,
    scaled to 75%, centered, and with a gray border.

    For example, a markdown link like:
      [Some PDF Title](pdf/SomeDocument.pdf)

    is replaced with:
      \clearpage
      \includepdf[pages=-,frame,scale=0.75]{\detokenize{pdf/SomeDocument.pdf}}
      \clearpage
    """
    pattern = r'\[([^\]]+)\]\(([^)]+\.pdf)\)'
    def repl(match):
        pdf_path = match.group(2)
        # Insert \includepdf with the desired options.
        return (
            "\n\\clearpage\n"
            "\\includepdf[pages=-,"
            "frame,"              # draws a border
            "scale=0.75]"         # 75% scale; page numbering remains as-is.
            "{\\detokenize{" + pdf_path + "}}\n"
            "\\clearpage\n"
        )
    return re.sub(pattern, repl, md_content)

def generate_pdf():
    """
    Erzeugt eine deutsche Titelseite-PDF und ein Hauptdokument-PDF, die dann zusammengefügt werden.
    Anforderungen:
      1) Die Titelseite hat KEINE Seitenzahlen.
      2) Das Inhaltsverzeichnis (TOC) hat KEINE Seitenzahlen.
      3) Die eigentliche Seitenzählung beginnt NACH dem TOC.
      4) Die Silbentrennung ist deaktiviert.
      5) Abschnittstitel sind linksbündig (ragged right), während Absätze voll gerechtfertigt sind.
      6) Pandoc (via subprocess) wird mit korrekter UTF-8-Verarbeitung eingesetzt.

    Dynamische Fonts werden via eines generierten LaTeX-Headers (siehe generate_dynamic_font_header) geladen.

    Zusätzlich:
      Markdown-Links zu PDFs (z.B. [Title](pdf/file.pdf)) werden erkannt und automatisch so
      umgewandelt, dass alle Seiten des PDFs ins Dokument eingebunden werden – dabei werden die
      Seiten skaliert (75%), zentriert und mit einem grauen Rahmen versehen, wobei die Seitenzahlen
      erhalten bleiben.
    """
    input_dir = "md"  # Ordner mit den Markdown-Dateien.
    output_pdf = "da.pdf"
    cover_pdf = "temp_cover.pdf"
    document_pdf = "temp_document.pdf"
    disable_hyphenation_file = "disable_hyphenation.tex"
    dynamic_font_file = "dynamic_font.tex"

    # Neuer LaTeX-Header: Deaktiviert Silbentrennung und fügt Layout-Anpassungen ein.
    # Enthält außerdem den Hack, um die pdfpages-Rahmenfarbe auf Grau zu setzen.
    disable_hyphenation = r"""
\usepackage[none]{hyphenat}
\sloppy
\usepackage{caption}
\captionsetup[figure]{aboveskip=10pt, belowskip=10pt}
\setlength{\textfloatsep}{10pt plus 2pt minus 2pt}
\setlength{\floatsep}{10pt plus 2pt minus 2pt}
\setlength{\intextsep}{10pt plus 2pt minus 2pt}
\usepackage{tocloft}
\setlength{\cftbeforetoctitleskip}{-1em}
\setlength{\cftaftertoctitleskip}{1em}
\setlength{\cftparskip}{0pt}
\flushbottom

\usepackage{titlesec}
\titleformat{\section}{\raggedright\Large\bfseries}{}{0em}{}
\titleformat{\subsection}{\raggedright\large\bfseries}{}{0em}{}
\titleformat{\subsubsection}{\raggedright\normalsize\bfseries}{}{0em}{}

% We need pdfpages for embedding external PDFs
\usepackage{pdfpages}

% We need xcolor to set the frame color to gray
\usepackage{xcolor}

% ------------------------------------------------------------------
% Hack to force the border color (frame) in pdfpages to be gray.
% (pdfpages normally draws the frame in black.)
% ------------------------------------------------------------------
\makeatletter
\def\AM@ruleColor{gray}%
\def\AM@rule{%
    \@tempdima\AM@pageht
    \advance\@tempdima-\dp\@currbox
    \edef\AM@pageht{\the\@tempdima}
    \leavevmode
    \color{\AM@ruleColor}
    \vrule\@width\AM@frame\@height\AM@pageht
    \hb@xt@\wd\@currbox{\hss
        \vbox to \ht\@currbox{\box\@currbox\vss}%
    \hss}%
}
\makeatother
"""

    try:
        with open(disable_hyphenation_file, "w", encoding="utf-8") as f:
            f.write(disable_hyphenation)
        print(f"✅ Header (Silbentrennung, TOC-Anpassung, Abstände, grauer Rahmen) erstellt: {disable_hyphenation_file}")
    except Exception as e:
        print(f"❌ Fehler beim Erstellen der Header-Datei: {e}")
        return

    # Dynamischen Font-Header erzeugen.
    if not generate_dynamic_font_header(dynamic_font_file, fonts_dir="fonts"):
        print("❌ Dynamischer Font-Header konnte nicht erzeugt werden. Abbruch.")
        return

    # Prüfe, ob das Eingabeverzeichnis existiert.
    if not os.path.exists(input_dir):
        print(f"❌ Verzeichnis '{input_dir}' existiert nicht.")
        return

    # Alle Markdown-Dateien (sortiert) einlesen.
    md_files = sorted(glob(os.path.join(input_dir, "*.md")))
    if not md_files:
        print(f"❌ Keine Markdown-Dateien gefunden in '{input_dir}'.")
        return

    ########################################################################
    # 1) Titelseite erzeugen (ohne Seitenzahlen)
    ########################################################################
    try:
        with open(md_files[0], "r", encoding="utf-8") as f:
            original_cover_md = f.read()
        # Ersetze PDF-Links (falls dort schon PDFs verlinkt sind).
        original_cover_md = replace_pdf_links(original_cover_md)

        # LaTeX-Befehle voranstellen, damit die Titelseite keine Seitenzahlen hat.
        cover_md = (
            r"\pagenumbering{gobble}" "\n"
            r"\thispagestyle{empty}" "\n" +
            original_cover_md
        )

        cmd_cover = [
            "pandoc",
            "-f", "markdown+footnotes",
            "-o", cover_pdf,
            "--pdf-engine=xelatex",
            "-V", "geometry=a4paper",
            "-V", "fontsize=14pt",
            "-V", "margin=1in",
            "-V", "fig-pos=H",
            "-H", disable_hyphenation_file,
            "-H", dynamic_font_file
        ]

        subprocess.run(cmd_cover, input=cover_md, text=True, check=True, encoding="utf-8")
        print(f"✅ Titelseite erstellt: {cover_pdf}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Fehler bei der Erstellung der Titelseite: {e}")
        return

    ########################################################################
    # 2) Hauptdokument erzeugen
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
        # Ersetze PDF-Links in jedem Markdown-Inhalt.
        content = replace_pdf_links(content)
        combined_md += f"\n\\newpage\n\n{content}\n"

    try:
        cmd_document = [
            "pandoc",
            "-f", "markdown+footnotes",
            "-o", document_pdf,
            "--pdf-engine=xelatex",
            "-V", "geometry=a4paper",
            "-V", "fontsize=12pt",
            "-V", "lang=de",
            "-V", "margin=1in",
            "-V", "fig-pos=H",
            "--number-sections",
            "-H", disable_hyphenation_file,
            "-H", dynamic_font_file
        ]

        subprocess.run(cmd_document, input=combined_md, text=True, check=True, encoding="utf-8")
        print(f"✅ Hauptdokument erstellt: {document_pdf}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Fehler bei der Erstellung des Hauptdokuments: {e}")
        return

    ########################################################################
    # 3) Titelseite und Hauptdokument zusammenführen
    ########################################################################
    try:
        merger = PdfMerger()
        merger.append(cover_pdf)
        merger.append(document_pdf)
        merger.write(output_pdf)
        merger.close()
        print(f"✅ Finale PDF erfolgreich erstellt: {output_pdf}")

        # Temporäre Dateien löschen.
        for temp_file in [cover_pdf, document_pdf, disable_hyphenation_file, dynamic_font_file]:
            try:
                os.remove(temp_file)
            except Exception as e:
                print(f"⚠️ Konnte '{temp_file}' nicht löschen: {e}")
        print("🗑️ Temporäre Dateien gelöscht.")
    except Exception as e:
        print(f"❌ Fehler beim Zusammenfügen der PDFs: {e}")

if __name__ == "__main__":
    generate_pdf()
