import pypandoc

def convert_doc_to_markdown(input_doc, output_md):
    """ Convert a .doc or .docx file to clean Markdown using Pandoc. """
    try:
        pypandoc.convert_file(input_doc, "markdown", format="docx", outputfile=output_md)
        print(f"✅ Conversion successful: {output_md}")
    except Exception as e:
        print(f"❌ Error converting file: {e}")

# Example Usage
convert_doc_to_markdown("doc.docx", "output.md")
