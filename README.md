# Skylark Drones Monday.com BI Agent

Live Demo: `[[LIVE_DEMO_URL_PLACEHOLDER]]`
GitHub: `[[GITHUB_REPO_URL_PLACEHOLDER]]`

An enterprise-grade, conversational Business Intelligence Agent for Skylark Drones that queries **Monday.com Deals & Work Orders** live via the Monday.com GraphQL API to answer founder-level queries, audit data quality, and generate structured executive leadership updates.

---

## 1. Problem Interpretation & Solution Architecture

Founders and executives require real-time, accurate business intelligence answers based on sales deals and operational deliveries. However, raw data is distributed across multiple boards and contains inconsistencies, missing values, and template rows. 

Our solution provides a **Conversational BI Agent** powered by an LLM reasoning engine, integrated with a **Deterministic Calculation Layer** in Python. This ensures that all metric calculations, sums, averages, and collections rates are computed with 100% mathematical accuracy in Python (avoiding LLM hallucinations), while the LLM acts as the routing orchestrator mapping user queries to python tools and translating tabular data into summaries.

### Architecture Data Flow
```
                 USER
                   ↓
            STREAMLIT FRONTEND (app.py)
                   ↓
         BACKEND AGENT (backend/agent.py)
                   ↓
        ┌──────────┴──────────┐
        ↓                     ↓
 MONDAY API CLIENT       AI TOOL LOGIC
(backend/monday_client.py) (backend/prompts.py)
        ↓                     ↓
 Deals + Work Orders    Deterministic BI (backend/business_logic.py)
        ↓                     ↓
        └──────────┬──────────┘
                   ↓
            DATA QUALITY (backend/data_cleaner.py)
                   ↓
          AI EXPLANATION
                   ↓
           FOUNDER RESPONSE
```

---

## 2. Project Directory Structure

The project strictly separates concerns between the User Interface and Application logic:

```
skylark-bi-agent/
│
├── app.py                         # FRONTEND / Streamlit UI Dashboard
│
├── backend/                       # BACKEND Python Modules
│   ├── __init__.py
│   ├── config.py                  # Securely loads environment / secrets
│   ├── monday_client.py           # Monday.com GraphQL API connection client
│   ├── schema_mapper.py           # Translates raw column IDs to canonical schema
│   ├── data_cleaner.py            # Normalizes texts, sectors, dates, and probabilities
│   ├── business_logic.py          # Deterministic Python BI calculations
│   ├── prompts.py                 # System prompts for the AI Agent
│   └── agent.py                   # LLM agent orchestrator & tool executor
│
├── tests/                         # Automated unit & integration tests
│   ├── test_data_cleaner.py
│   ├── test_business_logic.py
│   ├── test_schema_mapper.py
│   └── test_join_logic.py
│
├── local_data/                    # Mock Excel spreadsheets for dev tests only
│   ├── Deal funnel Data.xlsx
│   └── Work_Order_Tracker Data.xlsx
│
├── screenshots/                   # Verification screenshots
│   ├── 01-home.png
│   ├── 02-energy-pipeline.png
│   ├── 03-cross-board.png
│   └── 04-leadership-update.png
│
├── discover_boards.py             # Script to list Monday.com board IDs
├── requirements.txt               # App dependencies
├── .env.example                   # Template env config
├── .gitignore                     # Git exclusions
├── README.md                      # Setup and architecture guide
└── DECISION_LOG.md                # Architectural design log
```

---

## 3. Monday.com Integration & GraphQL Setup

The production application queries Monday.com dynamically using the **GraphQL API v2** at `https://api.monday.com/v2`.

### Dynamic Schema Discovery
Monday.com generates dynamic IDs for custom columns (e.g., `text3`, `numbers2`). To prevent breaking the application, our client implements a robust **two-step schema mapping** in `backend/schema_mapper.py`:
1. **Dynamic Mapping**: Queries the board's columns metadata (`boards { columns { id title type } }`) to map active column IDs to user-configured titles (e.g., mapping `numbers2` to "Masked Deal value").
2. **Canonical Mapping**: Translates user-visible headers to standardized `snake_case` internal fields (e.g., "Masked Deal value" $\rightarrow$ `deal_value`).

### Pagination
Monday.com boards can contain hundreds of rows. The client implements recursive cursor-based pagination utilizing `items_page (limit: 100, cursor: $cursor)` in `backend/monday_client.py` to guarantee that all items are retrieved rather than only the first page.

---

## 4. Normalization & Data Cleaning

Data cleaning is handled inside `backend/data_cleaner.py`:
- **Text & Status Fields**: Strips whitespaces and standardizes text strings. Nulls are mapped to `None`.
- **Sectors**: Case-insensitive alignment maps variations (e.g., `"mining "` and `"Mining"`) to canonical titles like `"Mining"`. Acronyms like `"dsp"` are capitalized as `"DSP"`.
- **Status Probabilities**: Translates Deal closure probabilities into float constants (`High` $\rightarrow$ `0.8`, `Medium` $\rightarrow$ `0.5`, `Low` $\rightarrow$ `0.2`, `Won` $\rightarrow$ `1.0`, `Dead` $\rightarrow$ `0.0`, default Open $\rightarrow$ `0.3`).
- **Nezuko/Bugs Bunny Filters**: Filters out duplicate header rows that are recorded as value rows in the raw datasets.

---

## 5. Cross-Board Join Strategy
The client joins sales information (Deals) with delivery information (Work Orders) by matching the normalized `deal_name` (lowercase, whitespace-trimmed) from both boards. 

**Empirical Match Rate**: Analysis of the raw Excel sheets confirms an **89.66% match rate** (52 of 58 unique work orders successfully link back to a Sales Deal). Mismatched work orders are logged in the Data Quality report.

---

## 6. Business Logic & Calculations
Calculations in `backend/business_logic.py` are executed in pure Python/Pandas:
- **Weighted Pipeline**: Computed as $\sum (\text{deal\_value} \times \text{probability})$.
- **Collection Rate**: Calculated as $\frac{\text{Collected Amount}}{\text{Billed Value}} \times 100$ and $\frac{\text{Collected Amount}}{\text{Won Bookings}} \times 100$ per sector.
- **Delayed Work Orders**: Active work orders (not Completed) where the target execution date (`probable_end_date`) is in the past, or whose execution status is stalled (e.g., "Pause / struck").

---

## 7. Data Quality Audit & Caveats
The application generates a live data quality report summarizing:
- Total records.
- Missing values count (e.g. won deals missing values).
- Cross-board mismatches.

These metrics are dynamically displayed to the founder in a context panel under the chat response to ensure complete transparency of data health.

---

## 8. Security & Credentials Setup

The application reads secrets from environment variables (local `.env` file or Streamlit Secrets):
- `MONDAY_API_TOKEN` - Monday.com Developer API Token
- `DEALS_BOARD_ID` - Monday.com Deals Board ID
- `WORK_ORDERS_BOARD_ID` - Monday.com Work Orders Board ID
- `OPENAI_API_KEY` - OpenAI API Key
- `OPENAI_MODEL` - Defaults to `"gpt-4o"`

Create a local `.env` file from the template:
```bash
cp .env.example .env
# Edit .env to add your keys
```

---

## 9. Local Setup & Verification

1. Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Run automated test suites:
   ```bash
   python -m unittest discover -s tests
   ```
3. Run Streamlit locally in development mode (reads from Excel mock files):
   ```bash
   export USE_LOCAL_EXCEL="true"
   streamlit run app.py
   ```

---

## 10. Deployment to Streamlit Cloud

1. Commit and push the clean repository to GitHub.
2. Link the repository to your [Streamlit Community Cloud](https://share.streamlit.io/) account.
3. Under **App Settings -> Secrets**, paste the keys:
   ```toml
   MONDAY_API_TOKEN = "your_token"
   DEALS_BOARD_ID = "your_deals_id"
   WORK_ORDERS_BOARD_ID = "your_orders_id"
   OPENAI_API_KEY = "your_openai_key"
   ```
4. Click **Deploy**. The app will run publicly, querying Monday.com live at runtime with zero configurations required from the evaluator.
