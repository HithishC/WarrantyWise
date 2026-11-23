# WarrantyWise — Your AI Warranty Claim Assistant

**An MCP-powered AI assistant that helps users find purchase records, verify product warranties, and prepare warranty claim drafts.**

## Problem

People often struggle to find purchase receipts, understand warranty coverage, and prepare warranty claims. This process can be confusing and time-consuming.

## Our Solution

WarrantyWise uses an AI agent and Model Context Protocol (MCP) tools to simplify the warranty claim process.

Users can describe their product issue in natural language. The AI agent searches available purchase records, checks warranty eligibility, and prepares a claim draft when the product is covered.

The user remains in control. A claim is never automatically submitted.

## Key Features

- **Natural-language interaction:** Describe your product or issue using everyday language.
- **AI-powered understanding:** Uses Qwen 2.5 (3B) through Ollama to understand user requests.
- **Receipt search:** Finds matching products in the available purchase records.
- **Multiple receipt selection:** Allows users to choose the correct purchase record.
- **Warranty verification:** Calculates warranty expiry and checks coverage.
- **Claim draft preparation:** Prepares a claim draft only when warranty coverage is verified.
- **Safety checks:** Does not assume missing warranty information or prepare claims when coverage cannot be verified.
- **Receipt upload:** Supports receipt image and PDF uploads with OCR-based data extraction and user confirmation.
- **User approval:** Claim drafts are not submitted automatically.

## How It Works

1. User describes a product issue.
2. The AI agent understands the request.
3. The MCP client discovers and invokes the available WarrantyWise tools.
4. The MCP server searches purchase records.
5. The warranty engine checks the product's coverage.
6. If coverage is verified, a claim draft is prepared.
7. The user reviews the draft. No claim is submitted automatically.

## MCP Tools

WarrantyWise exposes three MCP tools:

| Tool | Purpose |
|---|---|
| `search_receipts` | Searches available purchase records |
| `check_product_warranty` | Checks warranty status and expiry |
| `prepare_warranty_claim` | Prepares a claim draft for eligible products |

## Technology Stack

- **Language:** Python, JavaScript
- **AI Model:** Qwen 2.5 (3B)
- **AI Runtime:** Ollama
- **Backend:** FastAPI
- **Agent-to-tool communication:** Model Context Protocol (MCP)
- **Frontend:** HTML, CSS, JavaScript
- **Receipt processing:** PyMuPDF, Tesseract OCR, pytesseract
- **Data storage:** JSON-based sample purchase records
- **Server:** Uvicorn

## Project Structure

```text
WarrantyWise/
│
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── agent.py
│   ├── mcp_server.py
│   ├── warranty_engine.py
│   ├── receipt_processor.py
│   └── sample_data.json
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
├── requirements.txt
├── .gitignore
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.10 or later
- Ollama
- Node.js (for the JavaScript syntax check)
- Tesseract OCR for receipt image processing

### 1. Clone the repository

```powershell
git clone https://github.com/HithishC/WarrantyWise.git
cd WarrantyWise
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Start Ollama

Make sure Ollama is running and download the model:

```powershell
ollama pull qwen2.5:3b
```

### 5. Start the backend

From the project root:

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

The backend will be available at:

```text
http://127.0.0.1:8000
```

### 6. Open the frontend

Open `frontend/index.html` in your browser, or use the VS Code Live Server extension.

## Example Interaction

**User:**

"My Sony WH-CH720N headphones stopped working. Check whether they are under warranty and prepare a claim if eligible."

**WarrantyWise:**

- Searches matching Sony purchase records.
- Allows the user to select the correct receipt.
- Checks warranty coverage.
- Calculates the expiry date.
- Prepares a claim draft if the product is eligible.
- Clearly indicates that the draft has not been submitted.

If warranty information is missing or cannot be verified, WarrantyWise refuses to assume coverage.

## Safety and User Control

WarrantyWise follows a verification-first approach:

- Missing warranty duration is treated as unknown, not automatically eligible.
- Expired or unverifiable warranties cannot proceed to claim preparation.
- AI-generated understanding does not override the warranty engine's result.
- Claim preparation and claim submission are separate actions.
- The current MVP prepares drafts only; it does not submit claims to manufacturers.

## Current MVP Scope

This project is a working hackathon MVP using sample purchase records. It demonstrates AI-powered request understanding, MCP tool discovery and execution, warranty verification, and controlled claim-draft preparation.

Real manufacturer integrations and automated claim submission are outside the current MVP scope.

## Hackathon Track

**Track 1 — Make MCP Matter: Less Magic, More Utility**

WarrantyWise demonstrates how MCP can connect an AI agent to useful, controlled tools that solve a practical everyday problem.

---

**Built with the goal of making warranty claims simpler, safer, and more accessible.**