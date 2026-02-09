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

# ================================
# ✅ TESSERACT PATH FIX (IMPORTANT)
# ================================
if os.name == "nt":  # Windows
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
else:  # Linux / Render / Ubuntu
    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

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

        logger.debug(f"[OCR] Extracted Text Preview: {text[:500]}")

        os.makedirs("logs", exist_ok=True)
        with open("logs/debug_extracted_text.txt", "w", encoding="utf-8") as f:
            f.write(text)

        return text

    except Exception as e:
        logger.exception("[ERROR] Text extraction failed")
        raise Exception(f"Text extraction failed: {str(e)}")


def extract_from_pdf(file_path: str) -> str:
    try:
        with timeout(60, "PDF conversion") as run:
            images = run(
                convert_from_path,
                file_path,
                first_page=1,
                last_page=3,
                dpi=150,
                fmt='jpeg'
            )

        extracted_text = ""

        for i, image in enumerate(images):
            try:
                with timeout(30, f"OCR page {i+1}") as run:
                    width, height = image.size
                    if width > 2000 or height > 2000:
                        ratio = min(2000 / width, 2000 / height)
                        image = image.resize(
                            (int(width * ratio), int(height * ratio)),
                            Image.LANCZOS
                        )

                    text = run(
                        pytesseract.image_to_string,
                        image,
                        lang='eng',
                        config='--psm 6 --oem 1'
                    )

                    extracted_text += f"\n--- Page {i+1} ---\n{text.strip()}\n"

            except TimeoutError:
                extracted_text += f"\n--- Page {i+1} ---\n[OCR timeout]\n"

        if not extracted_text.strip():
            return extract_from_pdf_fallback(file_path)

        return extracted_text.strip()

    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}")


def extract_from_pdf_fallback(file_path: str) -> str:
    try:
        with timeout(90, "PDF fallback") as run:
            images = run(convert_from_path, file_path, dpi=100, fmt='jpeg')

        image = images[0]
        best_text = ""

        for config in ['--psm 4', '--psm 6', '--psm 12', '--psm 8']:
            try:
                with timeout(20, f"OCR fallback {config}") as run:
                    text = run(pytesseract.image_to_string, image, lang='eng', config=config)
                    if len(text.strip()) > len(best_text.strip()):
                        best_text = text
            except TimeoutError:
                continue

        return best_text.strip() if best_text else "[Unable to extract text]"

    except Exception:
        return "[PDF OCR fallback failed]"


def extract_from_image(file_path: str) -> str:
    try:
        with timeout(30, "Image open") as run:
            image = run(Image.open, file_path)

        width, height = image.size
        if width > 2000 or height > 2000:
            ratio = min(2000 / width, 2000 / height)
            image = image.resize(
                (int(width * ratio), int(height * ratio)),
                Image.LANCZOS
            )

        best_text = ""

        for config in ['--psm 6', '--psm 3', '--psm 4']:
            try:
                with timeout(10, f"OCR image {config}") as run:
                    text = run(pytesseract.image_to_string, image, lang='eng', config=config)
                    if len(text.strip()) > len(best_text.strip()):
                        best_text = text
            except TimeoutError:
                continue

        if not best_text:
            raise Exception("No text detected")

        return best_text.strip()

    except Exception as e:
        raise Exception(f"Failed to extract text from image: {str(e)}")


def extract_from_docx(file_path: str) -> str:
    try:
        text = docx2txt.process(file_path)
        if not text.strip():
            raise Exception("Empty DOCX")
        return text.strip()
    except Exception as e:
        raise Exception(f"DOCX extraction failed: {str(e)}")


def clean_text(text: str) -> str:
    if not text:
        return ""

    cleaned = text.lower()
    cleaned = re.sub(r'[^a-z0-9\s]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned
