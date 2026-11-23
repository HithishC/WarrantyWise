
import json
import calendar
from datetime import date
from pathlib import Path

DATA_FILE = Path(__file__).parent / "sample_data.json"

def load_receipts():
    """Load all saved purchase receipts."""

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def save_receipt(receipt):
    """Save a confirmed receipt safely to the JSON database."""

    receipts = load_receipts()

    receipts.append(receipt)

    temporary_file = DATA_FILE.with_suffix(".tmp")

    with open(temporary_file, "w", encoding="utf-8") as file:
        json.dump(receipts, file, indent=2)

    temporary_file.replace(DATA_FILE)

    return receipt

def add_years(original_date, years):
    """Calculate warranty expiry, including leap-year handling."""

    new_year = original_date.year + years

    new_day = min(
        original_date.day,
        calendar.monthrange(new_year, original_date.month)[1]
    )

    return original_date.replace(
        year=new_year,
        day=new_day
    )

def check_warranty(receipt_id):
    """Check warranty using the receipt ID."""

    receipts = load_receipts()

    for receipt in receipts:

        if receipt["receipt_id"].lower() == receipt_id.lower():

            purchase_date = date.fromisoformat(
                receipt["purchase_date"]
            )

            warranty_years = receipt.get("warranty_years")

            # Never assume a missing warranty duration.
            if (
                warranty_years is None
                or not isinstance(warranty_years, int)
                or isinstance(warranty_years, bool)
                or warranty_years <= 0
            ):
                return {
                    "receipt_id": receipt["receipt_id"],
                    "product": receipt["product"],
                    "brand": receipt["brand"],
                    "purchase_date": purchase_date.isoformat(),
                    "expiry_date": None,
                    "warranty_years": None,
                    "price": receipt.get("price"),
                    "status": "Cannot verify"
                }

            expiry_date = add_years(
                purchase_date,
                warranty_years
            )

            today = date.today()

            if today <= expiry_date:
                status = "Under Warranty"
            else:
                status = "Warranty Expired"

            return {
                "receipt_id": receipt["receipt_id"],
                "product": receipt["product"],
                "brand": receipt["brand"],
                "purchase_date": purchase_date.isoformat(),
                "expiry_date": expiry_date.isoformat(),
                "warranty_years": warranty_years,
                "price": receipt.get("price"),
                "status": status
            }

    return None