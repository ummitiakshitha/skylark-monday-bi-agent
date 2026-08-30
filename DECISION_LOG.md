# Decision Log: Skylark Drones BI Agent

This log details the key architectural choices, assumptions, trade-offs, and design constraints adopted during the development of the Skylark Drones Monday.com BI Agent.

---

## 1. Technological Choices & Rationale

### Choice: Streamlit for UI & Python for Backend
- **Decision**: Streamlit was selected for the entire UI dashboard, importing backend packages.
- **Rationale**: Streamlit provides native chat elements (`st.chat_message`, `st.chat_input`) and diagnostic sidebars, compiling instantly. It integrates securely with Streamlit Secrets, ensuring no credentials are leaked or queried in the frontend. This allowed us to build a secure, interactive interface within the 6-hour technical budget instead of managing cross-origin setups or API endpoints separately.

### Choice: Direct Monday.com GraphQL API Connection
- **Decision**: Directly connecting to the Monday.com GraphQL endpoint using Python `requests` and custom cursor-based pagination.
- **Rationale**: Monday.com columns are dynamically defined (e.g. `text4`). Custom API handlers are faster to debug, paginate page-by-page, and map schema IDs directly to display titles compared to setting up a separate Model Context Protocol (MCP) server, which introduces unnecessary configuration layers for the evaluator.

### Choice: Deterministic Calculation Layer (Python)
- **Decision**: Program all aggregations (sums, averages, counts, cross-board joins) in Python (`backend/business_logic.py`).
- **Rationale**: LLMs are notorious for failing at arithmetic calculations, missing null rows, or hallucinating averages.Restricting the LLM to tool selection and text formatting guarantees 100% mathematical accuracy while retaining conversational intelligence.

---

## 2. Messy Data & Data Normalization Decisions

### Finding: Nezuko/Bugs Bunny Garbage Rows
- **Problem**: Raw Deal funnel data contains duplicate headers recorded as value rows (e.g. rows where status is `"Deal Status"`).
- **Decision**: Filter these out in `backend/data_cleaner.py` to prevent string-to-float errors.

### Finding: Missing Financial Values on Won Deals
- **Problem**: 61% of closed won deals (101 out of 165) are missing value figures in the raw data.
- **Decision**: We calculated this missing count and surfaced it as a critical warning caveat in the UI. If a founder queries won bookings, the app explicitly highlights the missing values count to prevent misleading bookings summaries.

### Join Key Choice: Deal Name
- **Problem**: Comparing `Client Code` vs `Customer Name Code` showed a 0% match rate due to prefixes (`COMPANY` vs `WOCOMPANY`).
- **Decision**: Match on the normalized lowercase, trimmed `deal_name`. This yields an **89.66% match rate** (52 of 58 unique work orders match a sales deal), which we log in the data quality report.

---

## 3. Operations & Financial Metric Assumptions

- **Financial Metric Distinctions**: Kept bookings (won deals value), billing (invoiced work order values), and collections (cash received) separate. Only using the term "revenue" when referring to won bookings or collections directly.
- **Timing & Date Logic**: We treat "this quarter" as the current calendar quarter by default. Timing is computed relative to the current system date (e.g. August 2026, falling into Q3 2026).
- **Work Order Delays**: Defined as active work orders (not Completed) whose probable end date is in the past, or whose execution status is paused/stuck.

---

## 4. 6-Hour Limit Trade-offs & Future Improvements

- **Read-Only Operations**: Monday.com access is strictly read-only to avoid altering client board data during audits.
- **Interactive Visualizations**: Focused on clean markdown and metrics cards. If more time was available, we would integrate interactive charts (e.g. Altair bar/pie charts for sector distribution).
- **Caching**: Used Streamlit's `@st.cache_data` to cache dynamic Monday queries, preventing rate-limiting from multiple queries.
