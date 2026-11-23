
import json
import sys
import uuid
import re

from datetime import date

import httpx

from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File
)

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from PIL import Image

from backend.warranty_engine import (
    check_warranty,
    save_receipt
)

from backend.receipt_processor import (
    extract_receipt_text,
    extract_receipt_details
)

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


app = FastAPI(
    title="WarrantyWise API",
    description="AI-powered warranty management assistant using Qwen and MCP",
    version="0.6.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# -----------------------------------------
# CONFIGURATION
# -----------------------------------------

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:3b"

pending_receipts = {}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "pdf"
}


STOP_WORDS = {
    "my", "the", "a", "an", "is", "are", "was", "were",
    "stopped", "working", "not", "and", "or", "check",
    "whether", "they", "it", "under", "warranty",
    "prepare", "claim", "for", "me", "please", "can",
    "you", "help", "with", "i", "have", "has", "do",
    "does", "want", "need", "to", "be", "still",
    "its", "their", "this", "that"
}


# -----------------------------------------
# REQUEST MODELS
# -----------------------------------------

class AssistantRequest(BaseModel):
    message: str
    receipt_id: str | None = None


class ReceiptConfirmation(BaseModel):
    pending_id: str
    brand: str
    product: str
    purchase_date: str
    price: float | None = None
    warranty_years: int | None = None


# -----------------------------------------
# FALLBACK REQUEST UNDERSTANDING
# -----------------------------------------

def extract_search_term(user_request):

    words = (
        user_request.lower()
        .replace(".", "")
        .replace(",", "")
        .replace("?", "")
        .replace("!", "")
        .split()
    )

    useful_words = [
        word for word in words
        if word not in STOP_WORDS
    ]

    return " ".join(useful_words[:2])


def wants_claim(user_request):

    request = user_request.lower()

    phrases = [
        "prepare a claim",
        "prepare claim",
        "claim draft",
        "file a claim",
        "make a claim",
        "raise a claim",
        "help me claim",
        "claim it",
        "warranty claim",
        "start a claim"
    ]

    return any(
        phrase in request
        for phrase in phrases
    )


# -----------------------------------------
# QWEN AI REQUEST UNDERSTANDING
# -----------------------------------------

async def understand_user_request(user_message):
    """
    Use local Qwen to understand the customer's request.

    Qwen identifies:
    - Product search keywords
    - Whether the customer requested a claim

    Qwen does NOT decide warranty coverage.
    """

    prompt = f"""
You are the request-understanding component of WarrantyWise.

Analyze the customer's message.

Return ONLY a valid JSON object with these two fields:

{{
    "search_term": "brand and product keywords",
    "wants_claim": true
}}

Rules:

1. Identify the actual brand and product mentioned.
2. Remove conversational words such as my, please, check,
   whether, working, and stopped.
3. Keep useful product identification words.
4. Set wants_claim to true ONLY if the customer explicitly
   asks to prepare, create, file, raise, or start a warranty claim.
5. If the customer only asks to check warranty status,
   set wants_claim to false.
6. Never invent a product name.
7. Do not decide whether a product is under warranty.
8. Do not create a warranty claim.
9. Return JSON only.

Customer message:
{user_message}
"""

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0
        }
    }

    try:

        async with httpx.AsyncClient(
            timeout=90.0
        ) as client:

            response = await client.post(
                OLLAMA_URL,
                json=payload
            )

            response.raise_for_status()

            result = response.json()

            ai_content = (
                result.get("message", {})
                .get("content", "")
            )

            parsed = json.loads(ai_content)

            search_term = parsed.get("search_term", "")

            claim_intent = parsed.get("wants_claim", False)

            if not isinstance(search_term, str):
                raise ValueError("Invalid search term from Qwen.")

            if not isinstance(claim_intent, bool):
                raise ValueError("Invalid claim intent from Qwen.")

            search_term = search_term.strip()[:150]

            if not search_term:
                raise ValueError("Qwen did not identify a product.")

            print("\nQwen AI understood the request:")
            print("Search term:", search_term)
            print("Claim requested:", claim_intent)

            return {
                "search_term": search_term,
                "wants_claim": claim_intent,
                "ai_powered": True
            }

    except (
        httpx.HTTPError,
        json.JSONDecodeError,
        ValueError,
        KeyError,
        TypeError
    ) as error:

        print("\nQwen request understanding failed:", error)

        print("Using Python fallback request understanding.")

        return {
            "search_term": extract_search_term(user_message),
            "wants_claim": wants_claim(user_message),
            "ai_powered": False
        }


# -----------------------------------------
# MCP RESPONSE PARSER
# -----------------------------------------

def parse_mcp_result(result_text):
    """
    Parse MCP output containing:
    - One JSON object
    - A JSON array
    - Multiple JSON objects separated by newlines
    """

    if not result_text:
        return None

    result_text = result_text.strip()

    try:
        return json.loads(result_text)

    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()

    results = []

    position = 0

    while position < len(result_text):

        while (
            position < len(result_text)
            and result_text[position].isspace()
        ):
            position += 1

        if position >= len(result_text):
            break

        try:

            value, end_position = decoder.raw_decode(
                result_text,
                position
            )

            results.append(value)

            position = end_position

        except json.JSONDecodeError:

            return None

    if not results:
        return None

    if len(results) == 1:
        return results[0]

    return results


# -----------------------------------------
# MCP TOOL EXECUTION
# -----------------------------------------

async def call_mcp_tool(session, tool_name, arguments):

    print(f"Calling MCP tool: {tool_name}")

    result = await session.call_tool(
        tool_name,
        arguments=arguments
    )

    if result.isError:
        raise RuntimeError(
            f"MCP tool failed: {tool_name}"
        )

    output = []

    for item in result.content:

        if hasattr(item, "text"):
            output.append(item.text)

    return "\n".join(output)


# -----------------------------------------
# HOME
# -----------------------------------------

@app.get("/")
def home():

    return {
        "message": "Welcome to WarrantyWise!",
        "status": "API is running",
        "ai_model": OLLAMA_MODEL,
        "mcp_enabled": True
    }


# -----------------------------------------
# WARRANTY CHECK
# -----------------------------------------

@app.get("/warranty/{receipt_id}")
def get_warranty(receipt_id: str):

    result = check_warranty(receipt_id)

    if result is None:

        raise HTTPException(
            status_code=404,
            detail="Receipt not found"
        )

    return result


# -----------------------------------------
# RECEIPT UPLOAD
# -----------------------------------------

@app.post("/receipts/upload")
async def upload_receipt(file: UploadFile = File(...)):

    filename = file.filename or ""

    extension = (
        filename.lower().rsplit(".", 1)[-1]
        if "." in filename
        else ""
    )

    if extension not in ALLOWED_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail="Only JPG, JPEG, PNG and PDF files are supported."
        )

    file_bytes = await file.read(
        MAX_UPLOAD_SIZE + 1
    )

    if not file_bytes:

        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty."
        )

    if len(file_bytes) > MAX_UPLOAD_SIZE:

        raise HTTPException(
            status_code=413,
            detail="File size cannot exceed 10 MB."
        )

    try:

        if (
            extension == "pdf"
            and not file_bytes.startswith(b"%PDF")
        ):

            raise ValueError(
                "The uploaded file is not a valid PDF."
            )

        if extension in ["jpg", "jpeg", "png"]:

            import io

            with Image.open(
                io.BytesIO(file_bytes)
            ) as image:

                image.verify()

        ocr_text = extract_receipt_text(
            file_bytes,
            filename
        )

        if not ocr_text:

            raise ValueError(
                "No readable text was found in this receipt."
            )

        extracted = await extract_receipt_details(
            ocr_text
        )

        if not isinstance(extracted, dict):

            raise ValueError(
                "AI returned invalid receipt information."
            )

        extracted_details = {
            "brand": extracted.get("brand"),
            "product": extracted.get("product"),
            "purchase_date": extracted.get("purchase_date"),
            "price": extracted.get("price"),
            "warranty_years": extracted.get("warranty_years")
        }

        for field in ["brand", "product"]:

            value = extracted_details[field]

            if (
                not isinstance(value, str)
                or not value.strip()
            ):

                extracted_details[field] = None

            else:

                extracted_details[field] = value.strip()[:150]

        purchase_date = extracted_details["purchase_date"]

        try:

            if purchase_date:
                date.fromisoformat(purchase_date)

        except (ValueError, TypeError):

            extracted_details["purchase_date"] = None

        price = extracted_details["price"]

        if (
            not isinstance(price, (int, float))
            or isinstance(price, bool)
            or price < 0
        ):

            extracted_details["price"] = None

        warranty_years = extracted_details["warranty_years"]

        if (
            not isinstance(warranty_years, int)
            or isinstance(warranty_years, bool)
            or warranty_years <= 0
        ):

            extracted_details["warranty_years"] = None

        pending_id = str(uuid.uuid4())

        pending_receipts[pending_id] = extracted_details

        return {
            "success": True,
            "message": (
                "Receipt processed. Review the extracted "
                "information before saving."
            ),
            "pending_id": pending_id,
            "extracted": extracted_details,
            "ocr_text": ocr_text[:5000],
            "requires_confirmation": True
        }

    except HTTPException:
        raise

    except ValueError as error:

        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    except httpx.HTTPError:

        raise HTTPException(
            status_code=502,
            detail=(
                "Could not connect to the local AI model. "
                "Check whether Ollama is running."
            )
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Receipt processing failed: {str(error)}"
        )

    finally:

        await file.close()


# -----------------------------------------
# CONFIRM AND SAVE RECEIPT
# -----------------------------------------

@app.post("/receipts/confirm")
def confirm_receipt(request: ReceiptConfirmation):

    pending = pending_receipts.get(
        request.pending_id
    )

    if pending is None:

        raise HTTPException(
            status_code=404,
            detail="Pending receipt not found. Please upload it again."
        )

    brand = request.brand.strip()

    product = request.product.strip()

    if not brand or not product:

        raise HTTPException(
            status_code=400,
            detail="Brand and product are required."
        )

    try:

        purchase_date = date.fromisoformat(
            request.purchase_date
        )

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail="Purchase date must use YYYY-MM-DD format."
        )

    if purchase_date > date.today():

        raise HTTPException(
            status_code=400,
            detail="Purchase date cannot be in the future."
        )

    if (
        request.price is not None
        and request.price < 0
    ):

        raise HTTPException(
            status_code=400,
            detail="Price cannot be negative."
        )

    if (
        request.warranty_years is not None
        and request.warranty_years <= 0
    ):

        raise HTTPException(
            status_code=400,
            detail="Warranty duration must be greater than zero."
        )

    receipt_id = (
        "WW" + uuid.uuid4().hex[:8].upper()
    )

    receipt = {
        "receipt_id": receipt_id,
        "product": product,
        "brand": brand,
        "purchase_date": purchase_date.isoformat(),
        "warranty_years": request.warranty_years,
        "price": request.price
    }

    try:

        save_receipt(receipt)

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Could not save receipt: {str(error)}"
        )

    pending_receipts.pop(
        request.pending_id,
        None
    )

    warranty = check_warranty(receipt_id)

    return {
        "success": True,
        "message": "Receipt successfully saved.",
        "receipt": receipt,
        "warranty": warranty
    }


# -----------------------------------------
# QWEN + MCP WARRANTY ASSISTANT
# -----------------------------------------

@app.post("/assistant")
async def warranty_assistant(request: AssistantRequest):

    user_message = request.message.strip()

    if not user_message:

        raise HTTPException(
            status_code=400,
            detail="Please enter a message."
        )

    selected_receipt_id = (
        request.receipt_id.strip()
        if request.receipt_id
        else None
    )

    # Step 1: Understand the user's request using Qwen.

    ai_result = await understand_user_request(
        user_message
    )

    search_term = ai_result["search_term"]

    claim_requested = ai_result["wants_claim"]

    if not selected_receipt_id and not search_term:

        raise HTTPException(
            status_code=400,
            detail="Please mention a product name or brand."
        )

    # Step 2: Connect to the actual MCP server.

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "backend.mcp_server"]
    )

    try:

        async with stdio_client(
            server_params
        ) as (read, write):

            async with ClientSession(
                read,
                write
            ) as session:

                await session.initialize()

                # Step 3: Search receipts or use exact selection.

                if selected_receipt_id:

                    print(
                        "Checking selected receipt:",
                        selected_receipt_id
                    )

                    receipt_id = selected_receipt_id

                else:

                    print(
                        "Qwen identified product:",
                        search_term
                    )

                    search_text = await call_mcp_tool(
                        session,
                        "search_receipts",
                        {
                            "search_term": search_term
                        }
                    )

                    receipts = parse_mcp_result(
                        search_text
                    )

                    if isinstance(receipts, dict):

                        if "error" in receipts:

                            raise RuntimeError(
                                receipts["error"]
                            )

                        receipts = [receipts]

                    if not receipts:

                        return {
                            "success": True,
                            "found": False,
                            "ai_powered": ai_result["ai_powered"],
                            "message": (
                                "I couldn't find a matching purchase "
                                "receipt. Warranty coverage cannot "
                                "be verified yet."
                            ),
                            "report": {
                                "searched_for": search_term,
                                "receipt_status": "Not found",
                                "warranty_status": "Cannot verify",
                                "claim_status": "Not prepared",
                                "next_steps": [
                                    "Add or upload your purchase receipt.",
                                    "Check that the product name or brand is correct.",
                                    "Try the warranty check again."
                                ]
                            },
                            "product": None,
                            "claim": None
                        }

                    # Step 4: Handle multiple receipts.

                    if len(receipts) > 1:

                        print(
                            f"Found {len(receipts)} matching receipts."
                        )

                        return {
                            "success": True,
                            "found": True,
                            "multiple_matches": True,
                            "ai_powered": ai_result["ai_powered"],
                            "message": (
                                "I found multiple matching receipts. "
                                "Please select the correct purchase."
                            ),
                            "matches": receipts
                        }

                    receipt_id = receipts[0].get(
                        "receipt_id"
                    )

                    if not receipt_id:

                        raise RuntimeError(
                            "The matching receipt has no receipt ID."
                        )

                # Step 5: Check warranty using MCP.

                warranty_text = await call_mcp_tool(
                    session,
                    "check_product_warranty",
                    {
                        "receipt_id": receipt_id
                    }
                )

                warranty = parse_mcp_result(
                    warranty_text
                )

                if not isinstance(warranty, dict):

                    raise RuntimeError(
                        "Could not understand warranty response."
                    )

                if "error" in warranty:

                    raise RuntimeError(
                        warranty["error"]
                    )

                # Step 6: Prepare claim only when BOTH conditions
                # are satisfied:
                # - Qwen identifies an explicit claim request.
                # - MCP confirms Under Warranty.

                claim = None

                if (
                    claim_requested
                    and warranty.get("status") == "Under Warranty"
                ):

                    claim_text = await call_mcp_tool(
                        session,
                        "prepare_warranty_claim",
                        {
                            "receipt_id": receipt_id,
                            "issue_description": user_message
                        }
                    )

                    claim = parse_mcp_result(
                        claim_text
                    )

                    if not isinstance(claim, dict):
                        claim = None

                # Step 7: Generate final factual response
                # from verified MCP results.

                if warranty.get("status") == "Under Warranty":

                    message = (
                        "Your product is currently under warranty."
                    )

                    if (
                        isinstance(claim, dict)
                        and claim.get("claim_status") == "Draft prepared"
                    ):

                        message += (
                            " A claim draft has been prepared. "
                            "It has not been submitted."
                        )

                    elif claim_requested:

                        message += (
                            " A claim draft could not be confirmed."
                        )

                    else:

                        message += (
                            " No claim draft was prepared because "
                            "you did not request one."
                        )

                elif warranty.get("status") == "Warranty Expired":

                    message = (
                        "Your product's warranty has expired. "
                        "A warranty claim draft has not been prepared."
                    )

                else:

                    message = (
                        "The warranty duration is missing or "
                        "unverified. Please confirm the warranty "
                        "details before relying on a coverage result."
                    )

                return {
                    "success": True,
                    "found": True,
                    "ai_powered": ai_result["ai_powered"],
                    "message": message,
                    "product": {
                        "receipt_id": receipt_id,
                        "brand": warranty.get("brand"),
                        "product": warranty.get("product"),
                        "purchase_date": warranty.get("purchase_date"),
                        "expiry_date": warranty.get("expiry_date"),
                        "status": warranty.get("status")
                    },
                    "claim": claim
                }

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "WarrantyWise encountered an error: "
                f"{str(error)}"
            )
        )


# -----------------------------------------
# RUN SERVER
# -----------------------------------------

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )
