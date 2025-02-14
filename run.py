import os
import re
import subprocess
import unicodedata
from glob import glob
from PyPDF2 import PdfReader

# Constant for maximum size factor for images.
MAX_SIZE_FACTOR = 0.9

# Global variables for collecting entries.
abb_entries = []  # For figures (Abbildungsverzeichnis)
abb_count = 0

anh_entries = []  # For attachments (Anhängeverzeichnis)
anh_count = 0

def escape_latex(text):
    """
    Escapes LaTeX special characters.
    """
    if not isinstance(text, str):
        return text
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
    Scans the fonts directory and writes a dynamic font header.
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

def parse_properties(prop_string):
    """
    Parses a property string of the form:
      key="value", key2="value2", ...
    Supports properties in any order and both standard (") and smart (“ ”) quotes.
    Returns a dictionary.
    """
    pattern = re.compile(r'(\w+)\s*=\s*["“](.*?)["”]')
    return dict(pattern.findall(prop_string))

def replace_abb_syntax(md_content):
    """
    Replaces !Abb: syntax with a LaTeX figure block and collects data.
    Supports properties in any order.
    Expected syntax:
      !Abb: Some Title {pdf="pdf/17.pdf", note="Footnote text", scale="0.75", rotation="90"}
    """
    global abb_count, abb_entries
    pattern = re.compile(r'!Abb:\s*(.*?)\s*\{([^}]+)\}', flags=re.DOTALL)
    
    def abb_repl(match):
        global abb_count, abb_entries
        title = escape_latex(match.group(1).strip())
        prop_str = match.group(2)
        props = parse_properties(prop_str)
        pdf_file = unicodedata.normalize("NFC", props.get("pdf", "").strip())
        note = escape_latex(props.get("note", "").strip())
        
        # Get the scale factor; default is 1.0 if not specified.
        scale_str = props.get("scale", "").strip()
        try:
            scale_value = float(scale_str) if scale_str else 1.0
        except ValueError:
            scale_value = 1.0
        
        # Get rotation angle if provided.
        angle = props.get("rotation", props.get("angle", "")).strip()
        
        # Build the \includegraphics options. Only include angle if specified.
        include_opts = f"[angle={angle}]" if angle else ""
        
        abb_count += 1
        entry = f"Abb.{abb_count}: {title}. {note}"
        abb_entries.append(entry)
        
        figure_str = (
            "\\begin{figure}[H]\n"
            "\\centering\n"
            "\\adjustbox{max size={0.9\\textwidth}{0.9\\textheight},center,keepaspectratio}{%\n"
            "\\scalebox{" + str(scale_value) + "}{\\includegraphics" + include_opts + "{\\detokenize{" + pdf_file + "}}}\n"
            "}\n"
            "\\caption{" + title + "}\n"
            "\\end{figure}\n"
        )
        return figure_str
    
    return pattern.sub(abb_repl, md_content)

def replace_anh_syntax(md_content):
    """
    Replaces !Anh: syntax by embedding each PDF page.
    Supports properties in any order.
    Expected syntax:
      !Anh: Some Title {pdf="pdf/17.pdf", desc="Description text", angle="90"}
    """
    global anh_count, anh_entries
    pattern = re.compile(r'!Anh:\s*(.*?)\s*\{([^}]+)\}', flags=re.DOTALL)
    
    def anh_repl(match):
        global anh_count, anh_entries
        title = escape_latex(match.group(1).strip())
        prop_str = match.group(2)
        props = parse_properties(prop_str)
        pdf_file = unicodedata.normalize("NFC", props.get("pdf", "").strip())
        desc = escape_latex(props.get("desc", "").strip())
        anh_count += 1
        entry = f"Anh.{anh_count}: {title}. {desc}"
        anh_entries.append(entry)
        
        try:
            reader = PdfReader(pdf_file)
            num_pages = len(reader.pages)
        except Exception as e:
            print(f"⚠️ Could not determine page count for {pdf_file}: {e}")
            num_pages = 0
        
        pdf_includes = ""
        given_angle = props.get("angle", props.get("rotation", "")).strip()
        for i in range(1, num_pages + 1):
            page = reader.pages[i - 1]
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            angle_option = ""
            if given_angle:
                angle_option = f"angle={given_angle},"
            elif width > height:
                angle_option = "angle=90,"
            pdf_includes += (
                f"\\includepdf[pages={{{i}}},frame,scale=0.75,{angle_option}"
                "pagecommand={\\stepcounter{page}}]"
                f"{{\\detokenize{{{pdf_file}}}}}\n"
            )
        return pdf_includes
    
    return pattern.sub(anh_repl, md_content)

def replace_abs_syntax(md_content):
    """
    Replaces !Abs: syntax with a title page.
    Expected syntax:
      !Abs: Some Title {desc="Some description", note="Some note"}
    """
    pattern = re.compile(r'!Abs:\s*(.*?)\s*\{([^}]*)\}', flags=re.DOTALL)
    
    def abs_repl(match):
        title = escape_latex(match.group(1).strip())
        prop_str = match.group(2)
        props = parse_properties(prop_str)
        desc = escape_latex(props.get("desc", "").strip())
        note = escape_latex(props.get("note", "").strip())
        block = (
            "\\clearpage\n"
            "\\thispagestyle{empty}\n"
            "\\begin{flushleft}\n"
            f"{{\\Huge \\textbf{{{title}}}}}\\par\n"
            "\\vspace{0.5em}\n"
        )
        if desc:
            block += f"{{\\LARGE {desc}}}\\par\n"
            block += "\\vspace{1.5em}\n"
        if note:
            block += f"{{\\large {note}}}\\par\n"
        block += "\\end{flushleft}\n\\clearpage\n"
        return block
    
    return pattern.sub(abs_repl, md_content)

def exclude_cover_headers_from_toc(md_content):
    """
    Modifies all markdown headers in the cover page so they are excluded from the TOC.
    It appends the attribute "{-}" to each header.
    """
    def process_line(line):
        if line.lstrip().startswith("#"):
            if re.search(r'\s\{\s*-\s*\}\s*$', line):
                return line
            m = re.match(r'^(#+\s+.*?)(\s*\{.*\})\s*$', line)
            if m:
                header_text = m.group(1)
                attr_block = m.group(2)
                if not re.search(r'-\s*$', attr_block[:-1]):
                    new_attr = attr_block[:-1] + " -}"
                    return header_text + " " + new_attr
                else:
                    return line
            else:
                return line + " {-}"
        return line

    lines = md_content.splitlines()
    processed_lines = [process_line(line) for line in lines]
    return "\n".join(processed_lines)

def is_sticky_line(line):
    """
    Returns True if the given line is considered “sticky” – meaning it is
    a heading (starting with '#' characters) or is a line that is entirely
    marked up with strong (** or __) or italic (* or _) text (but not a bullet).
    """
    stripped = line.strip()
    # Check for markdown headings.
    if re.match(r'^#+\s+', stripped):
        return True
    # Check for strong text: **...** or __...__
    if (stripped.startswith("**") and stripped.endswith("**")) or \
       (stripped.startswith("__") and stripped.endswith("__")):
        return True
    # Check for italic text: *...* or _..._ (ensure it's not a bullet list).
    if (stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("* ")) or \
       (stripped.startswith("_") and stripped.endswith("_") and not stripped.startswith("_ ")):
        return True
    return False

def prevent_page_break_between_sticky_and_abb(md_content):
    """
    Scans the Markdown content for any sticky line (e.g., headings,
    or lines entirely enclosed in **, __, * or _)
    that is immediately (ignoring blank lines) followed by a LaTeX figure environment.
    If found, appends a "\nopagebreak[4]" to the sticky line so that the sticky text and the figure stay together.
    """
    lines = md_content.splitlines()
    new_lines = []
    for i, line in enumerate(lines):
        new_lines.append(line)
        if is_sticky_line(line):
            # Look ahead for the next non-empty line.
            next_line = ""
            for j in range(i+1, len(lines)):
                if lines[j].strip():
                    next_line = lines[j].strip()
                    break
            if next_line.startswith("\\begin{figure}"):
                # Append the nopagebreak command to the current sticky line.
                new_lines[-1] = line + " \\nopagebreak[4]"
    return "\n".join(new_lines)

def generate_pdf():
    """
    Generates one single PDF by concatenating Markdown files.
    - The cover page (first MD file) is included with no header or numbering.
    - Its markdown headers are modified to be excluded from the table of contents.
    - The TOC, main content, and final sections (including Anhänge) show headers and numbering.
    """
    input_dir = "md"
    output_pdf = "da.pdf"
    disable_hyphenation_file = "disable_hyphenation.tex"
    dynamic_font_file = "dynamic_font.tex"

    preamble = r"""
\usepackage[none]{hyphenat}
\usepackage{float}
\sloppy
\usepackage{caption}
\captionsetup[figure]{font=footnotesize, aboveskip=10pt, belowskip=10pt}
\setlength{\textfloatsep}{10pt plus 2pt minus 2pt}
\setlength{\floatsep}{10pt plus 2pt minus 2pt}
\setlength{\intextsep}{10pt plus 2pt minus 2pt}
\raggedbottom

\usepackage{tocloft}
\setlength{\cftbeforetoctitleskip}{-1em}
\setlength{\cftaftertoctitleskip}{1em}
\setlength{\cftparskip}{0pt}

\usepackage{titlesec}
\titleformat{\section}{\raggedright\Large\bfseries}{\thesection}{1em}{}
\titleformat{\subsection}{\raggedright\large\bfseries}{\thesubsection}{1em}{}
\titleformat{\subsubsection}{\raggedright\normalsize\bfseries}{\thesubsubsection}{1em}{}

% pdfpages for embedding PDFs
\usepackage{pdfpages}
\usepackage{xcolor}
\usepackage{xurl}
\usepackage{adjustbox} % Ensures images never exceed text size.
\renewcommand{\UrlBreaks}{\do\/\do-}
\usepackage[hang,flushmargin]{footmisc}
\setlength{\emergencystretch}{3em}

\usepackage[automark]{scrlayer-scrpage}
\clearpairofpagestyles
\automark[subsection]{section}
\ihead{\headmark}
\ohead{\pagemark}
\setlength{\headheight}{15pt}
\setkomafont{pagehead}{\normalfont}

% Added for better table formatting:
\usepackage{booktabs}
\usepackage{array}
\usepackage{longtable}
\setlength{\tabcolsep}{12pt} % Increase space between table columns
\renewcommand{\arraystretch}{1.2} % Increase row height for better readability
"""
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

    # Process the cover page.
    with open(md_files[0], "r", encoding="utf-8") as f:
        cover_md = f.read()
    cover_md = exclude_cover_headers_from_toc(cover_md)
    cover_md = "\\thispagestyle{empty}\n\\pagenumbering{gobble}\n" + cover_md
    cover_md += "\n\\clearpage\n\\pagenumbering{arabic}\n"
    cover_md = replace_abb_syntax(cover_md)
    cover_md = replace_anh_syntax(cover_md)
    cover_md = replace_abs_syntax(cover_md)

    # Process the remaining Markdown files.
    rest_md = ""
    for md_file in md_files[1:]:
        with open(md_file, "r", encoding="utf-8") as f:
            rest_md += "\n\\newpage\n\n" + f.read() + "\n"
    rest_md = replace_abb_syntax(rest_md)
    rest_md = replace_anh_syntax(rest_md)
    rest_md = replace_abs_syntax(rest_md)

    toc_block = r"""
\clearpage
\renewcommand*\contentsname{Inhaltsverzeichnis}
\tableofcontents
\clearpage
"""
    combined_md = cover_md + "\n" + toc_block + "\n" + rest_md

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

    # --- NEW STEP: Prevent page breaks between sticky text and following Abb figures ---
    combined_md = prevent_page_break_between_sticky_and_abb(combined_md)
    # -----------------------------------------------------------------------------

    try:
        cmd_document = [
            "pandoc",
            "-f", "markdown+footnotes",
            "-o", output_pdf,
            "--pdf-engine=xelatex",
            "-V", "geometry=a4paper",
            "-V", "fontsize=11pt",
            "-V", "lang=de",
            "-V", "margin=1in",
            "-V", "fig-pos=H",
            "--number-sections",
            "-H", disable_hyphenation_file,
            "-H", dynamic_font_file
        ]
        subprocess.run(cmd_document, input=combined_md, text=True, check=True, encoding="utf-8")
        print(f"✅ Final PDF created successfully: {output_pdf}")

        # Clean up temporary files.
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