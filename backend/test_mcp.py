
import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():

    # Tell the MCP client how to start our server
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "backend.mcp_server"]
    )

    # Connect to the MCP server
    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            # Initialize the MCP connection
            await session.initialize()

            print("\nConnected to WarrantyWise MCP Server!")

            # Discover available tools
            tools_result = await session.list_tools()

            print("\nAvailable MCP Tools:")

            for tool in tools_result.tools:
                print(f"- {tool.name}: {tool.description}")

            # Call the receipt search tool
            print("\nTesting search_receipts...")

            result = await session.call_tool(
                "search_receipts",
                arguments={"search_term": "Sony"}
            )

            print("\nSearch Result:")

            for item in result.content:
                if hasattr(item, "text"):
                    print(item.text)

            # Call the warranty checker
            print("\nTesting check_product_warranty...")

            warranty_result = await session.call_tool(
                "check_product_warranty",
                arguments={"receipt_id": "WW001"}
            )

            for item in warranty_result.content:
                if hasattr(item, "text"):
                    print(item.text)

            # Prepare a claim draft
            print("\nTesting prepare_warranty_claim...")

            claim_result = await session.call_tool(
                "prepare_warranty_claim",
                arguments={
                    "receipt_id": "WW001",
                    "issue_description": "Headphones are not powering on."
                }
            )

            for item in claim_result.content:
                if hasattr(item, "text"):
                    print(item.text)


if __name__ == "__main__":
    asyncio.run(main())
