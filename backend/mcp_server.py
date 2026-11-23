
from mcp.server.fastmcp import FastMCP

from backend.warranty_engine import (
    load_receipts,
    check_warranty
)

mcp = FastMCP("WarrantyWise")


@mcp.tool()
def search_receipts(search_term: str) -> list:
    """
    Search purchase receipts using product name or brand.
    Ignores generic product descriptions when matching.
    """

    receipts = load_receipts()

    results = []

    generic_words = {
        "headphones",
        "earphones",
        "earbuds",
        "laptop",
        "smartphone",
        "phone",
        "mobile",
        "device",
        "product",
        "my",
        "the",
        "for"
    }

    search_words = search_term.lower().split()

    # Remove generic descriptions when other useful words exist.
    useful_words = [
        word for word in search_words
        if word not in generic_words
    ]

    if useful_words:
        search_words = useful_words

    for receipt in receipts:

        searchable_text = (
            str(receipt.get("product") or "")
            + " "
            + str(receipt.get("brand") or "")
        ).lower()

        if all(word in searchable_text for word in search_words):
            results.append(receipt)

    return results


@mcp.tool()
def check_product_warranty(receipt_id: str) -> dict:

    result = check_warranty(receipt_id)

    if result is None:
        return {"error": "Receipt not found"}

    return result


@mcp.tool()
def prepare_warranty_claim(
    receipt_id: str,
    issue_description: str
) -> dict:

    warranty = check_warranty(receipt_id)

    if warranty is None:
        return {"error": "Receipt not found"}

    if warranty["status"] != "Under Warranty":

        return {
            "message": "Cannot prepare claim: warranty is expired or could not be verified.",
            "warranty": warranty
        }

    return {
        "claim_status": "Draft prepared",
        "receipt_id": receipt_id,
        "product": warranty["product"],
        "brand": warranty["brand"],
        "issue_description": issue_description,
        "warranty_status": warranty["status"],
        "purchase_date": warranty["purchase_date"],
        "expiry_date": warranty["expiry_date"],
        "requires_user_approval": True,
        "submission_status": "Not submitted"
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
