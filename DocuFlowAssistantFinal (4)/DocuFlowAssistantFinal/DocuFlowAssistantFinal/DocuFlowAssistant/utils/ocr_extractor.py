import os
import logging
import multiprocessing
from typing import Optional
from contextlib import contextmanager
import re
from PIL import Image
from pdf2image import convert_from_path
import docx2txt
import concurrent.futures
import pytesseract
import pdfplumber

# Path to Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\kavya\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

# Auto-detect CPU cores, leave 1 free
CPU_CORES = max(1, multiprocessing.cpu_count() - 1)

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    pass

@contextmanager
def timeout(seconds, task_name="task"):
    """Timeout wrapper for multiprocessing tasks."""
    with concurrent.futures.ProcessPoolExecutor(max_workers=CPU_CORES) as executor:
        def run(func, *args, **kwargs):
            try:
                return executor.submit(func, *args, **kwargs).result(timeout=seconds)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"{task_name} timed out after {seconds} seconds")
        yield run

def extract_text(file_path: str) -> str:
    """Main entry point for text extraction."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == '.pdf':
            text = extract_from_pdf(file_path)
        elif ext in ['.jpg', '.jpeg', '.png']:
            text = extract_from_image(file_path)
        elif ext == '.docx':
            text = extract_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        os.makedirs("logs", exist_ok=True)
        with open("logs/debug_extracted_text.txt", "w", encoding="utf-8") as f:
            f.write(text)

        return text
    except Exception as e:
        logger.exception(f"Text extraction failed for {file_path}")
        raise

def extract_from_pdf(file_path: str) -> str:
    """Extract text from PDF, using embedded text first, then OCR in parallel for ALL pages."""
    try:
        # Try embedded text first
        try:
            with pdfplumber.open(file_path) as pdf:
                embedded_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
            if embedded_text.strip():
                logger.debug("Embedded PDF text extracted successfully")
                return embedded_text
        except Exception as e:
            logger.debug(f"Embedded text extraction failed: {e}")

        # Convert all pages to images
        with timeout(300, "Full PDF conversion") as run:
            images = run(convert_from_path, file_path, dpi=150, fmt='jpeg')

        logger.info(f"OCR starting for {len(images)} pages using {CPU_CORES} cores")

        # OCR each page in parallel
        with concurrent.futures.ProcessPoolExecutor(max_workers=CPU_CORES) as executor:
            results = list(executor.map(process_pdf_page, enumerate(images, start=1)))

        extracted_text = "\n".join(results)

        if not extracted_text.strip() or "[OCR failed]" in extracted_text:
            logger.info("Using PDF fallback method")
            return extract_from_pdf_fallback(file_path)

        return extracted_text.strip()
    except TimeoutError as e:
        raise Exception(f"PDF processing timed out: {e}")

def process_pdf_page(args):
    """OCR a single PDF page."""
    page_number, image = args
    image = preprocess_image(image)
    try:
        text = pytesseract.image_to_string(image, lang='eng', config='--psm 1 --oem 1')
        if not text.strip():
            text = pytesseract.image_to_string(image, lang='eng', config='--psm 6 --oem 1')
        return f"--- Page {page_number} ---\n{text.strip()}"
    except Exception:
        return f"--- Page {page_number} ---\n[OCR failed]"

def extract_from_pdf_fallback(file_path: str) -> str:
    """Fallback OCR for PDFs using multiple configs."""
    try:
        with timeout(120, "PDF fallback conversion") as run:
            images = run(convert_from_path, file_path, dpi=100, fmt='jpeg')
        
        if not images:
            return "[No images extracted]"

        configs = ['--psm 4 --oem 1', '--psm 6 --oem 1', '--psm 12 --oem 1', '--psm 8 --oem 1']

        all_results = []
        for page_num, image in enumerate(images, start=1):
            image = preprocess_image(image)
            with concurrent.futures.ProcessPoolExecutor(max_workers=CPU_CORES) as executor:
                results = list(executor.map(run_ocr_config, [(image, cfg) for cfg in configs]))
            best_text = max(results, key=lambda t: len(t.strip()))
            all_results.append(f"--- Page {page_num} (Fallback) ---\n{best_text.strip() if best_text.strip() else '[No text]'}")

        return "\n".join(all_results)
    except Exception as e:
        logger.error(f"PDF fallback failed: {e}")
        return "[Failed to extract text]"

def extract_from_image(file_path: str) -> str:
    """Extract text from image using multiple OCR configs in parallel."""
    with timeout(30, "Image open") as run:
        image = run(Image.open, file_path)

    image = preprocess_image(image)
    configs = ['--psm 1 --oem 1', '--psm 3 --oem 1', '--psm 6 --oem 1', '--psm 4 --oem 1']

    with concurrent.futures.ProcessPoolExecutor(max_workers=CPU_CORES) as executor:
        results = list(executor.map(run_ocr_config, [(image, cfg) for cfg in configs]))

    best_text = max(results, key=lambda t: len(t.strip()))
    if not best_text.strip():
        raise Exception("No text found in image")
    return best_text.strip()

def run_ocr_config(args):
    """Run OCR for given config."""
    image, config = args
    try:
        return pytesseract.image_to_string(image, lang='eng', config=config)
    except Exception:
        return ""

def extract_from_docx(file_path: str) -> str:
    """Extract text from DOCX."""
    text = docx2txt.process(file_path)
    if not text.strip():
        raise Exception("No text found in DOCX")
    return text.strip()

def clean_text(text: str) -> str:
    """Clean up extracted text."""
    if not text:
        return ""
    cleaned = re.sub(r'[^a-z0-9\s]', '', text.lower())
    return re.sub(r'\s+', ' ', cleaned).strip()

def preprocess_image(image: Image.Image) -> Image.Image:
    """Resize, grayscale, and binarize image for better OCR."""
    width, height = image.size
    if width > 2000 or height > 2000:
        ratio = min(2000 / width, 2000 / height)
        image = image.resize((int(width * ratio), int(height * ratio)), Image.LANCZOS)
    image = image.convert("L")  # Grayscale
    image = image.point(lambda x: 0 if x < 200 else 255, '1')  # Binarize
    return image
