# Skylark Drones Monday.com BI Agent

Live Demo: `[[LIVE_DEMO_URL_PLACEHOLDER]]`
GitHub: `[[GITHUB_REPO_URL_PLACEHOLDER]]`

An agentic business intelligence chat application that queries **Monday.com Work Orders & Deals** live via the Monday.com GraphQL API to answer founder-level queries, audit data quality, and generate structured executive leadership updates.

---

## 1. Problem Interpretation & Solution Architecture

Founders and executives need quick, accurate business intelligence answers based on live operational data. However, real-world data is messy, incomplete, and distributed across different boards. 

Our solution provides a **Conversational BI Agent** powered by an LLM reasoning engine, integrated with a **Deterministic Calculation Layer** written in Python. This guarantees that all metrics, averages, and collections are computed with 100% mathematical accuracy (eliminating LLM hallucinations), while the LLM maps natural queries to tools and translates structured analysis into executive takeaways.

### High-Level Architecture
```
                   +------------------------+
                   |  Streamlit Chat UI     |
                   +-----------+------------+
                               |
                               v (Query time)
                   +-----------+------------+
                   |   Monday.com GraphQL   |
                   +-----------+------------+
                               |
                               v (Fetch items & columns)
                   +-----------+------------+
                   |   Data Cleaning Layer  | (data_cleaner.py)
                   +-----------+------------+
                               |
                               v (Standardized DataFrames)
  +----------------------------+----------------------------+
  |                                                         |
  v (Runs LLM loop)                                         v (Executes tools)
+------------------------+  Tool Calls    +----------------------------+
|      Agent Core        +--------------->+  Deterministic Analytics   | (business_logic.py)
| (OpenAI/Anthropic tool) <---------------+  (Python GroupBy/Sums)     |
+------------------------+  Tool Results  +----------------------------+
```

---

## 2. Project Structure

```
d:\skylarkdrones\
├── .gitignore             # Git ignore definitions
├── requirements.txt       # App dependencies
├── discover_boards.py     # Script to list Monday.com board IDs
├── monday_client.py       # Monday.com GraphQL API interface
├── data_cleaner.py        # Schema mapping and data normalization layer
├── business_logic.py      # Deterministic business and financial logic (Python)
├── agent_core.py          # AI Agent prompt, tools, and LLM runner
├── app.py                 # Streamlit chat interface and dashboard
├── test_agent.py          # Unit tests (cleaning, sorting, filtering)
├── test_e2e_mock.py      # E2E conversational flow mock tests
├── README.md              # Setup and architecture documentation
└── DECISION_LOG.md        # Log of architectural decisions and trade-offs
```

---

## 3. Tech Stack

- **Core**: Python 3.10+
- **Frontend / Dashboard**: Streamlit (fast, responsive chat elements, secure sidebar)
- **Data Manipulation**: Pandas & OpenPyXL
- **Monday.com Interface**: GraphQL API `https://api.monday.com/v2` via `requests`
- **Reasoning Engine**: GPT-4o or Claude 3.5 Sonnet (supports function calling)

---

## 4. Setup & Configurations

### Monday.com Board Setup
1. Log in to your Monday.com account.
2. Create two boards: **Deals** and **Work Orders**.
3. Import the corresponding Excel files (`Deal funnel Data.xlsx` and `Work_Order_Tracker Data.xlsx`) to populate them.
4. Obtain your Personal API token from **Avatar -> Developer -> My Development Tokens**.

### Board ID Discovery
Once you have the API token, run:
```bash
export MONDAY_API_TOKEN="your_personal_token"
python discover_boards.py
```
This lists all board IDs. Note down the IDs for the **Deals** and **Work Orders** boards.

### Authentication & Environment Variables
Create a `.env` file in the project root for local development (this file is ignored by git):
```ini
MONDAY_API_TOKEN=your_monday_token_here
DEALS_BOARD_ID=your_deals_board_id_here
WORK_ORDERS_BOARD_ID=your_work_orders_board_id_here
OPENAI_API_KEY=your_openai_key_here
# OR
ANTHROPIC_API_KEY=your_anthropic_key_here
```

---

## 5. Schema Mapping & Data Normalization

On Monday.com, column IDs are generated dynamically (e.g., `text7`, `numbers2`). To prevent breaking the application, our client implements a robust **two-step schema mapping**:
1. **Dynamic Columns Mapping**: Queries the board's metadata (`columns { id title type }`) to map column IDs to user-configured titles (e.g. mapping `text7` to "Close Date (A)").
2. **Canonical Mapping**: Translates user-visible headers to standardized `snake_case` keys internally (e.g. "Close Date (A)" $\rightarrow$ `actual_close_date`).

### Normalizations Performed
- **Date Columns**: Coerced to standard Python `datetime.date` using `pd.to_datetime(errors='coerce')` to gracefully handle empty values and varying string formats.
- **Sectors**: Strip whitespace, lowercase, and align values (e.g. mapping `"mining "` and `"Mining"` to `"Mining"`). Acronyms like `"dsp"` are capitalized as `"DSP"`.
- **Status Fields**: Strip whitespace and map empty/null values to `"Unknown"`.
- **Garbage Row Filter**: Identifies and removes template/junk header rows that duplicate headers as value rows (e.g. `Nezuko` or `Bugs Bunny` rows).

---

## 6. Business Calculations & Calculations Layer

All metrics are computed in `business_logic.py` in pure Python, returning structures to the LLM.
- **Overall Pipeline**: Sum of deal values where `deal_status` is "Open".
- **Weighted Pipeline**: Sum of `deal_value * calculated_probability`.
- **Calculated Probability Rules**:
  - `Won` Deals $\rightarrow$ `1.0` (100%)
  - `Dead` Deals $\rightarrow$ `0.0` (0%)
  - `Open` Deals $\rightarrow$ Mapping `High` to `0.8`, `Medium` to `0.5`, `Low` to `0.2`. If missing, falls back to `0.3` (30%) or `0.2` if `On Hold`.
- **Cross-Board Join**: Left-joins Work Orders and Deals on `deal_name` (trimmed and lowercase). Calculates sector-level collection efficiency: `Collected Value / Billed Value` and `Collected Value / Contract Value`.

---

## 7. Agent & Tool Architecture

The LLM (GPT-4o or Claude 3.5 Sonnet) acts as the reasoning coordinator. It is bound to high-level **business-oriented tools**:
- `get_pipeline_summary`: Computes overall metrics, filters by sector/quarter.
- `get_pipeline_by_sector`: Returns sector rankings.
- `get_top_deals`: Returns top deals by value.
- `get_delayed_work_orders`: Lists overdue and stalled deliveries.
- `get_data_quality_report`: Statistics on missing fields.
- `get_revenue_and_collections`: Compares won contract bookings vs collections.

### Ambiguity and Date Handling
- **Ambiguous Queries**: If a user asks "show me the pipeline," the agent requests clarification: *"Do you want the overall current pipeline, a specific sector, or a stage breakdown?"*
- **Relative Quarters**: Resolves "this quarter" to Q3 2026 based on the system date (August 2026).

---

## 8. Data-Quality Transparency & Error Handling

- **Structured Auditing**: The data quality report exposes exact metrics (e.g. "101 out of 165 won deals are missing values"). If a user asks about won pipeline, the agent surfaces these warnings dynamically.
- **Fail-Safe Fallbacks**: If Monday.com is offline or credentials fail, the application displays a clear warning: *"I couldn't retrieve the latest Monday.com data, so I won't provide potentially stale figures. Please verify your credentials."*

---

## 9. Local Setup & Testing

1. Clone this repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the unit and E2E mock tests:
   ```bash
   python -m unittest test_agent.py
   python -m unittest test_e2e_mock.py
   ```
4. Start the local Streamlit application in development mode:
   ```bash
   export USE_LOCAL_EXCEL="true"
   streamlit run app.py
   ```

---

## 10. Deployment

To deploy to **Streamlit Community Cloud**:
1. Push this clean git repository to GitHub.
2. Log in to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Connect your repository and select `app.py` as the entry point.
4. Under **App Settings -> Secrets**, enter your production API credentials:
   ```toml
   MONDAY_API_TOKEN = "your_production_token"
   DEALS_BOARD_ID = "your_deals_board_id"
   WORK_ORDERS_BOARD_ID = "your_work_orders_board_id"
   OPENAI_API_KEY = "your_openai_api_key"
   # OR
   # ANTHROPIC_API_KEY = "your_anthropic_api_key"
   ```
5. Click deploy. The app will launch with a public URL, querying Monday.com live with zero configuration required from the evaluator.
