# Decision Log: Skylark Drones BI Agent

This log details the key architectural choices, assumptions, trade-offs, and design constraints adopted during the development of the Skylark Drones Monday.com BI Agent prototype.

---

## 1. Technology Choices & Rationale

### Choice: Python & Streamlit
- **Alternative Considered**: React (Next.js) + FastAPI.
- **Decision**: Streamlit was selected for the entire UI and backend framework.
- **Rationale**: The strict 6-hour time budget prioritized a working, deployed, and testable system. Streamlit provides instant, responsive chat components (`st.chat_message`, `st.chat_input`) and sidebar controls, while its deployment on Streamlit Community Cloud takes minutes. It eliminates the need for separate hosting of frontends, backends, CORS configuration, and server setups, freeing up hours to focus on the data quality, cleaning, and agent logic.

### Choice: Direct Monday.com GraphQL API
- **Alternative Considered**: Model Context Protocol (MCP) server.
- **Decision**: Directly accessing the Monday.com GraphQL API (`https://api.monday.com/v2`) via Python `requests`.
- **Rationale**: Monday.com GraphQL API has direct pagination and dynamic column definitions. Implementing an MCP server introduces unnecessary layers, setup overhead, and configuration complexities for the evaluator. Direct API calls are faster to debug, paginate, and test locally.

### Choice: Deterministic Calculation Layer (Python)
- **Alternative Considered**: Allowing the LLM to write pandas code or compute metrics itself.
- **Decision**: Pre-program all sums, averages, cross-board joins, rankings, and filters in a Python business logic file (`business_logic.py`).
- **Rationale**: LLMs are notorious for hallucinating calculations, missing nulls, or failing at weighted additions (e.g. `sum(value * probability)`). Pre-programming calculations in Python guarantees 100% mathematical accuracy. The LLM's role is restricted to translating query intent to function arguments, invoking the tool, and formatting the raw results for executive consumption.

---

## 2. Messy Data & Cross-Board Joins

### Finding: Garbage Header Rows
- **Issue**: The raw dataset contains duplicate header values disguised as records (e.g., the `Nezuko` and `Bugs Bunny` rows where columns contain values like `'Sector/service'` or `'Created Date'`).
- **Resolution**: Implemented a row filter in `data_cleaner.py` that excludes any row where `deal_status == 'Deal Status'`. These are reported as "excluded records" in the data quality report rather than crashing the system.

### Finding: Unmatched Won Values
- **Issue**: 61% of Won deals (101 out of 165) are missing deal value fields in the Deals sheet.
- **Resolution**: Surfaced this as a critical warning. If the user asks about won bookings, the agent explicitly prints a warning: *"Please note: 101 out of 165 won deals are missing financial values, meaning actual revenue is significantly underrepresented."*

### Cross-Board Join Strategy
- **Empirical Analysis**: Analysis of `Client Code` vs `Customer Name Code` showed zero overlap due to differing prefixes (`COMPANY` vs `WOCOMPANY`). However, comparing `Deal Name` in Deals and `Deal name masked` in Work Orders revealed a **90% match rate** (52 of 58 unique work orders match a deal name).
- **Decision**: Join exclusively on `deal_name` (inner/left join). Before joining, names are stripped of whitespace and converted to lowercase. Mismatched work orders are logged and returned in the data quality report to flag records requiring manual board adjustment.

---

## 3. Query Interpretation & Leadership Updates

### Relative Time Resolutions
- **Decision**: Interpretations of "this quarter", "last quarter", etc., are dynamically resolved in Python relative to the system's local date (August 2026, corresponding to Q3 2026). This ensures reproducible calculations without relying on LLM temporal guessing.

### Interpretation of "Leadership Update"
- We mapped "Prepare a leadership update for this quarter" to a structured executive summary generated from live data:
  - **Commercial**: Active and weighted pipeline metrics.
  - **Sector Performance**: Identifying strongest/weakest sectors by pipeline.
  - **Operations**: Work Order execution statuses (Completed vs Stalled).
  - **Risks**: Tracking delayed work orders and data quality gaps.
  - **Opportunities**: Identifying high-probability deals ($\ge 80\%$) closing soon.

---

## 4. Time-Limit Trade-offs & Future Improvements

Given the 6-hour limit, the following trade-offs were made:
- **No Writing Operations**: Monday.com access is strictly read-only, ensuring zero danger of modifying the client's board data.
- **Basic UI**: Simple chat layout instead of interactive charts.
- **If More Time Allowed**:
  - Add Streamlit visualization charts (e.g. Altair bar/pie charts for sector distribution).
  - Integrate a web webhook listener to automatically update cached DataFrames rather than querying Monday.com on every single chat message.
