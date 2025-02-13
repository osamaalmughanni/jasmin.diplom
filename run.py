import os
import re
import subprocess
import unicodedata
from glob import glob
from PyPDF2 import PdfReader

# Global variables to collect entries.
abb_entries = []  # For figures (Abbildungsverzeichnis)
abb_count = 0

anh_entries = []  # For attachments (Anhängeverzeichnis)
anh_count = 0

def escape_latex(text):
    """
    Escapes LaTeX special characters in the given text.
    """
    if not isinstance(text, str):
        return text
    # Order matters: backslash first.
    replacements = [
        ('\\', r'\textbackslash{}'),
        ('&', r'\&'),
        ('%', r'\%'),
        ('$', r'\$'),
        ('#', r'\#'),
        ('_', r'\_'),
        ('{', r'\{'),
        ('}', r'\}'),
        ('~', r'\textasciitilde{}'),
        ('^', r'\textasciicircum{}'),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text

def generate_dynamic_font_header(header_filename="dynamic_font.tex", fonts_dir="fonts"):
    """
    Scans the fonts directory for .ttf and .otf files, groups them by font family,
    and generates a LaTeX header file that dynamically sets the main font and registers
    available styles.
    """
    if not os.path.exists(fonts_dir):
        print(f"❌ Fonts directory '{fonts_dir}' does not exist.")
        return False

    font_files = glob(os.path.join(fonts_dir, "*.ttf")) + glob(os.path.join(fonts_dir, "*.otf"))
    if not font_files:
        print(f"❌ No font files found in '{fonts_dir}'.")
        return False

    families = {}
    for font_path in font_files:
        base = os.path.basename(font_path)
        name, _ = os.path.splitext(base)
        if '-' in name:
            family, style = name.rsplit('-', 1)
        else:
            family = name
            style = "regular"
        family = family.strip()
        style = style.lower().strip()
        if style in ("regular", "normal", "book"):
            style = "regular"
        elif style in ("bold", "black", "heavy"):
            style = "bold"
        elif style in ("italic", "oblique"):
            style = "italic"
        elif style in ("bolditalic", "bold-italic"):
            style = "bolditalic"

        if family not in families:
            families[family] = {}
        if style in families[family]:
            print(f"⚠️ Duplicate style '{style}' for font family '{family}'. Overriding previous entry.")
        families[family][style] = base

    best_family = None
    best_count = 0
    for fam, variants in families.items():
        if len(variants) > best_count:
            best_count = len(variants)
            best_family = fam

    if not best_family:
        print("❌ No valid font families found.")
        return False

    variants = families[best_family]
    if "regular" not in variants:
        fallback_variant = list(variants.values())[0]
        variants["regular"] = fallback_variant
        print(f"⚠️ No regular variant found for '{best_family}'. Using '{fallback_variant}' as regular.")

    header_lines = []
    header_lines.append("% Dynamically generated Font Header")
    header_lines.append("\\usepackage{fontspec}")
    options = [f"Path={fonts_dir}/", "Ligatures=TeX"]
    if "bold" in variants:
        options.append("BoldFont={" + variants["bold"] + "}")
    if "italic" in variants:
        options.append("ItalicFont={" + variants["italic"] + "}")
    if "bolditalic" in variants:
        options.append("BoldItalicFont={" + variants["bolditalic"] + "}")
    options_str = ", ".join(options)
    header_lines.append(f"\\setmainfont[{options_str}]{{{variants['regular']}}}")

    main_styles = {"regular", "bold", "italic", "bolditalic"}
    additional_styles = [s for s in variants if s not in main_styles]
    for style in additional_styles:
        cmd_name = "\\" + best_family.replace(" ", "").lower() + style + "font"
        header_lines.append(f"\\newfontface{cmd_name}[Path={fonts_dir}/]{{{variants[style]}}}")

    header_content = "\n".join(header_lines) + "\n"

    try:
        with open(header_filename, "w", encoding="utf-8") as f:
            f.write(header_content)
        print(f"✅ Dynamic font header created: {header_filename}")
        return True
    except Exception as e:
        print(f"❌ Error writing dynamic font header: {e}")
        return False

def replace_abb_syntax(md_content):
    """
    Processes custom syntax for figures.
    Expected syntax:
      !Abb: Some Title {pdf="pdf/17.pdf", note="Footnote text"}
    Replaces it with a LaTeX figure block and collects the data for the final Abbildungsverzeichnis.
    """
    global abb_count, abb_entries

    pattern = re.compile(
        r'^\!Abb:\s*(.*?)\s*\{pdf="([^"]+)",\s*note="([^"]+)"\}',
        flags=re.MULTILINE
    )
    def abb_repl(match):
        global abb_count, abb_entries
        title = escape_latex(match.group(1).strip())
        pdf_file = unicodedata.normalize("NFC", match.group(2).strip())
        note = escape_latex(match.group(3).strip())
        abb_count += 1
        # Collect the entry for the final list.
        entry = f"Abb.{abb_count}: {title}. {note}"
        abb_entries.append(entry)
        # Return a LaTeX figure block with a caption.
        return (
            "\\begin{figure}[htbp]\n"
            "\\centering\n"
            f"\\includegraphics[width=0.9\\textwidth]{{\\detokenize{{{pdf_file}}}}}\n"
            f"\\caption{{Abb.{abb_count}: {title}}}\n"
            "\\end{figure}\n"
        )
    return pattern.sub(abb_repl, md_content)

def replace_anh_syntax(md_content):
    """
    Processes custom syntax for attachments.
    Expected syntax:
      !Anh: Some Title {pdf="pdf/attachment.pdf", desc="A detailed description."}
    Replaces it by:
      1. A title block (with title and description).
      2. A blank page.
      3. Inserting each page of the PDF individually (using pdfpages) so that page numbering remains continuous.
    Also collects a clean entry for the final Anhängeverzeichnis.
    """
    global anh_count, anh_entries

    pattern = re.compile(
        r'^\!Anh:\s*(.*?)\s*\{pdf="([^"]+)"(?:,\s*desc="([^"]+)")?\}',
        flags=re.MULTILINE
    )
    def anh_repl(match):
        global anh_count, anh_entries
        title = escape_latex(match.group(1).strip())
        pdf_file = unicodedata.normalize("NFC", match.group(2).strip())
        desc = escape_latex(match.group(3).strip()) if match.group(3) else ""
        anh_count += 1
        # Collect the entry for the final list.
        entry = f"Anh.{anh_count}: {title}. {desc}"
        anh_entries.append(entry)
        
        # Title block for the attachment:
        title_block = (
            "\\clearpage\n"
            "\\thispagestyle{plain}\n"
            "\\begin{center}\n"
            f"{{\\Huge \\textbf{{{title}}}}}\\par\n"
        )
        if desc:
            title_block += f"{{\\Large {desc}}}\\par\n"
        title_block += "\\end{center}\n"
        title_block += "\\clearpage\n"
        
        # Insert a blank page.
        blank_page = (
            "\\clearpage\n"
            "\\thispagestyle{plain}\n"
            "\\mbox{}\n"
            "\\newpage\n"
        )
        
        # Determine the number of pages in the external PDF.
        try:
            reader = PdfReader(pdf_file)
            num_pages = len(reader.pages)
        except Exception as e:
            print(f"⚠️ Could not determine page count for {pdf_file}: {e}")
            num_pages = 0
        
        # Include each page individually.
        pdf_includes = ""
        for i in range(1, num_pages + 1):
            pdf_includes += (
                f"\\includepdf[pages={{{i}}},frame,scale=0.75,"
                "pagecommand={\\thispagestyle{empty}\\stepcounter{page}}]"
                f"{{\\detokenize{{{pdf_file}}}}}\n"
            )
        
        return title_block + blank_page + pdf_includes
    return pattern.sub(anh_repl, md_content)

def generate_pdf():
    """
    Generates one single PDF from all Markdown files with continuous page numbering.
    The document is built by concatenating all Markdown files (with custom replacements).
    At the end, two plain-text sections (Abbildungsverzeichnis and Anhängeverzeichnis)
    are appended that list the collected entries.
    """
    input_dir = "md"
    output_pdf = "da.pdf"
    disable_hyphenation_file = "disable_hyphenation.tex"
    dynamic_font_file = "dynamic_font.tex"

    # LaTeX preamble for layout and basic settings.
    preamble = r"""
\usepackage[none]{hyphenat}
\usepackage{float}
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

% pdfpages for embedding PDFs
\usepackage{pdfpages}
\usepackage{xcolor}
"""
    # Write the preamble to a file.
    try:
        with open(disable_hyphenation_file, "w", encoding="utf-8") as f:
            f.write(preamble)
        print(f"✅ Preamble written to: {disable_hyphenation_file}")
    except Exception as e:
        print(f"❌ Error writing preamble: {e}")
        return

    if not generate_dynamic_font_header(dynamic_font_file, fonts_dir="fonts"):
        print("❌ Dynamic font header generation failed. Aborting.")
        return

    if not os.path.exists(input_dir):
        print(f"❌ Directory '{input_dir}' does not exist.")
        return

    md_files = sorted(glob(os.path.join(input_dir, "*.md")))
    if not md_files:
        print(f"❌ No Markdown files found in '{input_dir}'.")
        return

    # Create one combined Markdown string.
    main_doc_header = r"""
\thispagestyle{plain}
\setcounter{page}{1}
\pagenumbering{arabic}
\renewcommand*\contentsname{Inhaltsverzeichnis}
\tableofcontents
\clearpage
"""
    combined_md = main_doc_header
    for md_file in md_files:
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()
        content = replace_abb_syntax(content)
        content = replace_anh_syntax(content)
        combined_md += "\n\\newpage\n\n" + content + "\n"

    # Append the final sections as plain Markdown (not in the TOC).
    combined_md += "\n\\newpage\n\n# Abbildungsverzeichnis\n\n"
    if abb_entries:
        for entry in abb_entries:
            combined_md += "- " + entry + "\n"
    else:
        combined_md += "Keine Abbildungen vorhanden.\n"
    
    combined_md += "\n\\newpage\n\n# Anhängeverzeichnis\n\n"
    if anh_entries:
        for entry in anh_entries:
            combined_md += "- " + entry + "\n"
    else:
        combined_md += "Keine Anhänge vorhanden.\n"

    try:
        cmd_document = [
            "pandoc",
            "-f", "markdown+footnotes",
            "-o", output_pdf,
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
        print(f"✅ Final PDF created successfully: {output_pdf}")

        # Optionally, remove temporary preamble files.
        for temp_file in [disable_hyphenation_file, dynamic_font_file]:
            try:
                os.remove(temp_file)
            except Exception as e:
                print(f"⚠️ Could not delete '{temp_file}': {e}")
        print("🗑️ Temporary files deleted.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during document creation: {e}")

if __name__ == "__main__":
    generate_pdf()
