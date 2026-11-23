
import io
import json
import re

import pymupdf
import httpx
import pytesseract

from PIL import Image

# Tesseract installation path
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# Local Ollama configuration
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:3b"

def extract_text_from_image(file_bytes):
    """Extract text from an uploaded image using Tesseract."""

    image = Image.open(io.BytesIO(file_bytes))

    if image.width * image.height > 25_000_000:
        raise ValueError("Image resolution is too large.")

    image = image.convert("RGB")

    extracted_text = pytesseract.image_to_string(
        image,
        lang="eng"
    )

    return extracted_text.strip()

def extract_text_from_pdf(file_bytes):
    """Extract text from a PDF, using OCR for scanned pages."""

    extracted_pages = []

    with pymupdf.open(
        stream=file_bytes,
        filetype="pdf"
    ) as document:

        if len(document) > 10:
            raise ValueError(
                "PDF cannot contain more than 10 pages."
            )

        for page in document:
            page_text = page.get_text().strip()

            # Use OCR for scanned PDF pages.
            if not page_text:
                pixmap = page.get_pixmap(
                    matrix=pymupdf.Matrix(2, 2),
                    alpha=False
                )

                image_bytes = pixmap.tobytes("png")

                image = Image.open(
                    io.BytesIO(image_bytes)
                )

                page_text = pytesseract.image_to_string(
                    image,
                    lang="eng"
                )

            extracted_pages.append(page_text)

    return "\n".join(extracted_pages).strip()

def extract_receipt_text(file_bytes, filename):
    """Choose the correct extraction method."""

    extension = filename.lower().rsplit(".", 1)[-1]

    if extension in ["jpg", "jpeg", "png"]:
        return extract_text_from_image(file_bytes)

    if extension == "pdf":
        return extract_text_from_pdf(file_bytes)

    raise ValueError(
        "Only JPG, JPEG, PNG and PDF files are supported."
    )

def extract_json_from_response(response_text):
    """Safely extract JSON from the AI response."""

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    match = re.search(
        r"\{.*\}",
        response_text,
        re.DOTALL
    )

    if not match:
        raise ValueError(
            "AI did not return valid receipt information."
        )

    return json.loads(match.group())

async def extract_receipt_details(ocr_text):
    """Use local Qwen to identify receipt information."""

    prompt = f"""
You are a purchase receipt information extraction system.

Extract information ONLY from the receipt text below.

Return one valid JSON object with these exact fields:

{{
    "brand": "brand name or null",
    "product": "product name or null",
    "purchase_date": "YYYY-MM-DD or null",
    "price": number or null,
    "warranty_years": number or null
}}

Rules:
1. Never invent missing information.
2. If a field is not clearly available, return null.
3. Do not calculate warranty duration.
4. Do not assume a standard manufacturer warranty.
5. Convert the purchase date to YYYY-MM-DD only when the date is clear.
6. Return JSON only. Do not include explanations.

RECEIPT TEXT:
{ocr_text}
"""

    async with httpx.AsyncClient(timeout=90.0) as client:

        response = await client.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "format": "json"
            }
        )

        response.raise_for_status()

        result = response.json()

    ai_response = result["message"]["content"]

    return extract_json_from_response(ai_response)