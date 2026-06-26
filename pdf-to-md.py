from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    TesseractOcrOptions,
    PdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
import sys
from pathlib import Path

pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = True
pipeline_options.ocr_options = TesseractOcrOptions()  # Use Tesseract

doc_converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
)

if __name__ == "__main__":
    pdf_path = Path(sys.argv[1])
    result = doc_converter.convert(str(pdf_path))
    md_output = result.document.export_to_markdown()
    output_path = pdf_path.with_suffix(".md")
    output_path.write_text(md_output, encoding="utf-8")
    print(f"Saved: {output_path}")
