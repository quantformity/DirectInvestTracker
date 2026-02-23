# Project: Investment Vibe (Equity & GIC Tracker)

## 🎯 Objective
Build a lightweight desktop application to track equity investments and Canadian GIC returns. The app must handle multi-currency accounts and provide real-time valuation consolidated into a single reporting currency.

## 🛠 Tech Stack & Deployment
- **Frontend:** Electron (React/Vue/Tailwind)
- **Backend:** Python (FastAPI/Flask)
- **Database:** SQLite
- **AI Integration:** External Ollama API (local LLM)
- **Containerization:** The entire stack (Frontend & Backend) must be deployable via **Docker**. 
  - Use `docker-compose` to orchestrate the app environment.
  - The app must communicate with Ollama via `host.docker.internal` or a user-defined IP.

---

## 🤖 AI Chat & Visualization Requirements

### 1. Interactive AI Chat Box
- **Interface:** A persistent or toggleable chat sidebar/modal.
- **LLM Integration:** Connect to an external Ollama instance using the `ollama-python` library or REST API.
- **Context Awareness:** The system prompt must include the schema of the SQLite database so the LLM knows what data is available (Symbols, MTM, PnL, Categories).

### 2. Natural Language Plotting (Vibe-to-Chart)
- **Prompt-to-Plot:** Users should be able to ask: *"Plot my portfolio proportion by category"* or *"Show me the PnL trend for my USD accounts."*
- **Execution Flow:**
    1. LLM interprets the prompt and generates a data query (SQL) or a Python plotting snippet (Matplotlib/Plotly).
    2. Backend executes the query against the SQLite DB.
    3. Backend generates the chart as a Base64 image or JSON for the frontend.
    4. Frontend renders the chart directly within the chat interface.

---

## 🏛 Core Data Structure & Logic

### 1. Currency & Asset Model
- **Reporting Currency:** Global setting (e.g., CAD, USD).
- **Accounts:** Multi-currency support. Portfolio total = $\sum (\text{Account Balance} \times \text{FX Rate})$.
- **Equities:** Tracked via Yahoo Finance symbols.
- **Cash/GIC:** Cost fixed at $1.00; Quantity = Principal Amount. Includes a `yield_rate` field.

### 2. SQLite Schema
- `accounts`: ID, Name, Base_Currency.
- `positions`: ID, Account_ID, Symbol, Category, Quantity, Cost_Per_Share, Date_Added, Yield_Rate (for GIC).
- `market_data`: Symbol, Last_Price, PE_Ratio, Change_Percent, Beta, Timestamp.
- `fx_rates`: Pair (USD/CAD), Rate, Timestamp.

---

## 🖥 User Interface Pages

### 1. Position Management (CRUD)
- Manage cash, dividends, and asset positions.
- Manual entry for Yahoo Symbols and GIC rates.

### 2. Position Listing (Consolidated View)
- Table showing all assets across all accounts.
- **Columns:** Symbol, Category, Account, Qty, Local Cost, Spot Price, MTM (Local), PnL (Local), MTM (Reporting), PnL (Reporting), Proportion %.

### 3. Summary & Pivot Tables
- All values converted to Reporting Currency.
- Summarize by **Category**, **Account**, **Symbol**, and **Cash/GIC**.

### 4. Asset Price & Market Insights
- Real-time dashboard for portfolio symbols.
- Displays: Symbol, Date, Price, P/E, % Change, Beta, and Total MTM impact.

### 5. Historical Performance (On-the-Fly)
- **No historical snapshots in DB.** - Dynamically fetch historical `yfinance` data and reconstruct the PnL/MTM curve based on position `Date_Added`.

---

## ⚙️ Backend Automation
- **Frequency:** Every 5 minutes.
- **Tasks:** Sync latest equity prices and FX rates from Yahoo Finance; update SQLite.

---

## 📝 Development Notes for LLM
- **Docker Networking:** Ensure the container can access the host's GPU if Ollama is running locally, or configure the API endpoint as an environment variable.
- **Security:** Use a "Sanitized SQL" approach or limited Python execution environment when letting the LLM generate code for charts.
