
import asyncio
import json
import sys

from datetime import datetime

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


STOP_WORDS = {
    "my", "the", "a", "an", "is", "are", "was", "were",
    "stopped", "working", "not", "and", "or", "check",
    "whether", "they", "it", "under", "warranty",
    "prepare", "claim", "for", "me", "please", "can",
    "you", "help", "with", "i", "have", "has", "do",
    "does", "want", "need", "to", "be", "still",
    "its", "their", "this", "that", "whether"
}


def extract_search_term(user_request):
    """Extract useful product and brand keywords."""

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


def parse_result(result_text):
    """Safely convert MCP JSON output into Python data."""

    if not result_text or not result_text.strip():
        return None

    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        print("Could not understand the MCP response.")
        return None


async def call_mcp_tool(session, tool_name, arguments):
    """Execute an MCP tool and return its result."""

    print(f"\nCalling MCP tool: {tool_name}")
    print("Arguments:", arguments)

    result = await session.call_tool(
        tool_name,
        arguments=arguments
    )

    if result.isError:
        raise RuntimeError(
            f"MCP tool execution failed: {tool_name}"
        )

    output = []

    for item in result.content:
        if hasattr(item, "text"):
            output.append(item.text)

    return "\n".join(output)


def wants_claim(user_request):
    """Identify whether the user explicitly requested a claim."""

    request = user_request.lower()

    claim_phrases = [
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
        for phrase in claim_phrases
    )


def format_date(date_value):
    """Convert YYYY-MM-DD into a readable date."""

    if not date_value:
        return "Not available"

    try:
        date_object = datetime.strptime(
            date_value,
            "%Y-%m-%d"
        )

        return date_object.strftime("%B %d, %Y")

    except ValueError:
        return str(date_value)


def generate_response(receipt, warranty, claim):
    """
    Generate a response using only verified MCP results.
    No unverified AI-generated warranty claims are added.
    """

    print("\n" + "=" * 45)
    print("WARRANTYWISE AI")
    print("=" * 45)

    print(
        f"\nProduct: {warranty.get('brand', receipt.get('brand', 'Unknown'))} "
        f"{warranty.get('product', receipt.get('product', 'Unknown'))}"
    )

    print(
        "\nPurchase Date:",
        format_date(warranty.get("purchase_date"))
    )

    print(
        "Warranty Expiry:",
        format_date(warranty.get("expiry_date"))
    )

    status = warranty.get("status", "Unknown")

    print("\nWarranty Status:", status)

    if status == "Under Warranty":

        print(
            "\nYour product is currently covered "
            "under warranty."
        )

        if claim:
            if claim.get("claim_status") == "Draft prepared":
                print("\nClaim Status: Draft prepared")

                print(
                    "Issue:",
                    claim.get("issue_description", "Not available")
                )

                print(
                    "\nPlease review the claim draft "
                    "and approve it before submission."
                )

                print("Submission Status: Not submitted")

            else:
                print(
                    "\nThe claim tool did not confirm "
                    "that a draft was prepared."
                )

        else:
            print(
                "\nNo claim draft was prepared because "
                "you did not request one."
            )

    elif status == "Warranty Expired":

        print(
            "\nYour product's warranty has expired."
        )

        print(
            "A warranty claim draft has not been prepared."
        )

    else:
        print(
            "\nThe warranty status could not be confirmed."
        )

    print("\n" + "=" * 45)


async def main():

    print("Starting WarrantyWise AI Agent...")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "backend.mcp_server"]
    )

    try:
        async with stdio_client(server_params) as (read, write):

            async with ClientSession(read, write) as session:

                await session.initialize()

                print("Connected to WarrantyWise MCP Server!")

                tools_result = await session.list_tools()

                print("\nDiscovered MCP tools:")

                available_tools = [
                    tool.name for tool in tools_result.tools
                ]

                for tool_name in available_tools:
                    print("-", tool_name)

                required_tools = {
                    "search_receipts",
                    "check_product_warranty",
                    "prepare_warranty_claim"
                }

                if not required_tools.issubset(
                    set(available_tools)
                ):
                    print(
                        "\nRequired WarrantyWise MCP tools "
                        "are missing."
                    )
                    return

                user_request = input(
                    "\nWhat can I help you with? "
                ).strip()

                if not user_request:
                    print("Please enter a request.")
                    return

                # Step 1: Extract product keywords
                search_term = extract_search_term(user_request)

                if not search_term:
                    print(
                        "\nPlease provide a product name "
                        "or brand."
                    )
                    return

                print("\nSearching for:", search_term)

                # Step 2: Search receipts through MCP
                search_text = await call_mcp_tool(
                    session,
                    "search_receipts",
                    {"search_term": search_term}
                )

                receipts = parse_result(search_text)

                if receipts is None:
                    print(
                        "\nWarrantyWise: No matching receipt "
                        "was found. Please check the product "
                        "or brand name."
                    )
                    return

                if isinstance(receipts, dict):
                    receipts = [receipts]

                if not receipts:
                    print(
                        "\nWarrantyWise: I couldn't find "
                        "a matching receipt."
                    )
                    return

                # Step 3: Select a receipt
                if len(receipts) > 1:

                    print("\nMultiple receipts found:")

                    for index, receipt in enumerate(receipts, 1):
                        print(
                            f"{index}. {receipt['brand']} "
                            f"{receipt['product']} "
                            f"({receipt['receipt_id']})"
                        )

                    choice = input(
                        "Enter receipt number: "
                    ).strip()

                    if not choice.isdigit():
                        print("Invalid selection.")
                        return

                    selected = int(choice)

                    if selected < 1 or selected > len(receipts):
                        print("Invalid selection.")
                        return

                    receipt = receipts[selected - 1]

                else:
                    receipt = receipts[0]

                receipt_id = receipt["receipt_id"]

                # Step 4: Verify warranty through MCP
                warranty_text = await call_mcp_tool(
                    session,
                    "check_product_warranty",
                    {"receipt_id": receipt_id}
                )

                warranty = parse_result(warranty_text)

                if not isinstance(warranty, dict):
                    print("Unable to verify warranty.")
                    return

                if "error" in warranty:
                    print("\nWarrantyWise:", warranty["error"])
                    return

                # Step 5: Prepare claim only when requested
                claim = None

                if (
                    wants_claim(user_request)
                    and warranty.get("status") == "Under Warranty"
                ):

                    claim_text = await call_mcp_tool(
                        session,
                        "prepare_warranty_claim",
                        {
                            "receipt_id": receipt_id,
                            "issue_description": user_request
                        }
                    )

                    claim = parse_result(claim_text)

                    if not isinstance(claim, dict):
                        claim = None

                # Step 6: Generate a verified response
                generate_response(
                    receipt,
                    warranty,
                    claim
                )

    except Exception as error:
        print("\nWarrantyWise encountered an error:")
        print(error)


if __name__ == "__main__":
    asyncio.run(main())
