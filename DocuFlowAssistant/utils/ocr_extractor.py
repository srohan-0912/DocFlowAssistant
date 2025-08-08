import os
import logging
from typing import Optional
from contextlib import contextmanager
import re
from PIL import Image
from pdf2image import convert_from_path
import docx2txt
import concurrent.futures
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\kavya\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"


logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    """Custom timeout exception"""
    pass

@contextmanager
def timeout(seconds, task_name="task"):
    def wrapper(func, *args, **kwargs):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(func, *args, **kwargs)
            try:
                return future.result(timeout=seconds)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"{task_name} timed out after {seconds} seconds")
    yield wrapper

def extract_text(file_path: str) -> str:
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

        # ✅ Log preview of extracted text
        logger.debug(f"[OCR] Extracted Text from {ext.upper()} (preview): {text[:500]}")

        # ✅ Save full extracted text to file for debugging
        try:
            os.makedirs("logs", exist_ok=True)
            with open("logs/debug_extracted_text.txt", "w", encoding="utf-8") as f:
                f.write(text)
            logger.debug("[OCR] Full extracted text written to logs/debug_extracted_text.txt")
        except Exception as log_error:
            logger.warning(f"[WARN] Could not save extracted text to file: {str(log_error)}")

        return text

    except Exception as e:
        logger.exception(f"[ERROR] Text extraction failed for {file_path}")
        raise Exception(f"Text extraction failed: {str(e)}")


def extract_from_pdf(file_path: str) -> str:
    try:
        with timeout(60, "PDF conversion") as run:
            images = run(convert_from_path, file_path, first_page=1, last_page=3, dpi=150, fmt='jpeg')
        
        extracted_text = ""
        for i, image in enumerate(images):
            logger.debug(f"Processing page {i+1} of PDF")
            try:
                with timeout(30, f"OCR page {i+1}") as run:
                    # Resize if needed
                    width, height = image.size
                    if width > 2000 or height > 2000:
                        ratio = min(2000/width, 2000/height)
                        new_size = (int(width * ratio), int(height * ratio))
                        image = image.resize(new_size, Image.LANCZOS)
                    
                    text = run(pytesseract.image_to_string, image, lang='eng',
                               config='--psm 1 --oem 1 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?@#$%^&*()_+-=[]{}|;:,.<>/ ')
                    
                    if not text.strip():
                        text = run(pytesseract.image_to_string, image, lang='eng', config='--psm 6 --oem 1')

                    extracted_text += f"\n--- Page {i+1} ---\n{text.strip()}\n"
            except TimeoutError:
                logger.warning(f"OCR timeout on page {i+1}, skipping")
                extracted_text += f"\n--- Page {i+1} ---\n[OCR timeout - page skipped]\n"

        if not extracted_text.strip() or "[OCR timeout - page skipped]" in extracted_text:
            logger.info("Attempting fallback OCR method...")
            return extract_from_pdf_fallback(file_path)
        logger.debug(f"[OCR] Extracted PDF Text (preview): {extracted_text[:500]}")
        return extracted_text.strip()

    except TimeoutError as e:
        raise Exception(f"PDF processing timed out: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}")

def extract_from_pdf_fallback(file_path: str) -> str:
    try:
        with timeout(90, "PDF fallback conversion") as run:
            images = run(convert_from_path, file_path, first_page=1, last_page=1, dpi=100, fmt='jpeg')
        
        if not images:
            raise Exception("Could not convert PDF to image")

        image = images[0]
        best_text = ""
        configs = ['--psm 4 --oem 1', '--psm 6 --oem 1', '--psm 12 --oem 1', '--psm 8 --oem 1']

        for config in configs:
            try:
                with timeout(20, f"Fallback OCR with {config}") as run:
                    text = run(pytesseract.image_to_string, image, lang='eng', config=config)
                    if len(text.strip()) > len(best_text.strip()):
                        best_text = text
            except TimeoutError:
                continue

        return f"--- Page 1 (Fallback Method) ---\n{best_text.strip()}" if best_text.strip() else "--- Page 1 ---\n[Unable to extract text]"

    except Exception as e:
        logger.error(f"Fallback PDF extraction failed: {str(e)}")
        return "--- Page 1 ---\n[Text extraction failed - please try a different document format]"

def extract_from_image(file_path: str) -> str:
    try:
        with timeout(30, "Image open") as run:
            image = run(Image.open, file_path)

        width, height = image.size
        if width > 2000 or height > 2000:
            ratio = min(2000 / width, 2000 / height)
            new_size = (int(width * ratio), int(height * ratio))
            image = image.resize(new_size, Image.LANCZOS)

        best_text = ""
        configs = ['--psm 1 --oem 1', '--psm 3 --oem 1', '--psm 6 --oem 1', '--psm 4 --oem 1']

        for config in configs:
            try:
                with timeout(10, f"OCR image with {config}") as run:
                    text = run(pytesseract.image_to_string, image, lang='eng', config=config)
                    if len(text.strip()) > len(best_text.strip()):
                        best_text = text
            except TimeoutError:
                continue

        if not best_text.strip():
            raise Exception("No text found in image")

        # ✅ Add this log to preview extracted text
        logger.debug(f"[OCR] Extracted Image Text (preview): {best_text[:300]}")

        return best_text.strip()

    except TimeoutError as e:
        raise Exception(f"Image processing timed out: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to extract text from image: {str(e)}")


def extract_from_docx(file_path: str) -> str:
    try:
        text = docx2txt.process(file_path)
        if not text.strip():
            raise Exception("No text found in DOCX file")
        
        # ✅ Log extracted text preview (for debugging)
        logger.debug(f"[OCR] Extracted DOCX Text (preview): {text[:500]}")
        return text.strip()
    except Exception as e:
        raise Exception(f"Failed to extract text from DOCX: {str(e)}")


def clean_text(text: str) -> str:
    if not text:
        return ""
    
    cleaned = text.lower()
    cleaned = re.sub(r'[^a-z0-9\s]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.strip()
    
    # ✅ Log cleaned text preview
    logger.debug(f"[CLEAN] Cleaned Text (preview): {cleaned[:300]}")
    logger.debug(f"[CLEAN] Original vs Cleaned (side-by-side):\nORIGINAL: {text[:200]}\nCLEANED : {cleaned[:200]}")
    return cleaned
