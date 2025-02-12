import os
import pypandoc

def convert_docx_to_markdown(doc_folder):
    """ Convert all .docx files in the given folder to Markdown and save in an 'md' subfolder. """
    md_folder = os.path.join(doc_folder, "md")
    os.makedirs(md_folder, exist_ok=True)
    
    for file in os.listdir(doc_folder):
        if file.endswith(".docx"):
            input_path = os.path.join(doc_folder, file)
            output_path = os.path.join(md_folder, f"{os.path.splitext(file)[0]}.md")
            try:
                pypandoc.convert_file(input_path, "markdown", format="docx", outputfile=output_path)
                print(f"✅ Converted: {file} -> {output_path}")
            except Exception as e:
                print(f"❌ Error converting {file}: {e}")

# Example Usage
convert_docx_to_markdown("doc")