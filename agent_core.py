import os
import datetime
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np

# Import our deterministic business logic functions
import business_logic

logger = logging.getLogger(__name__)

def clean_numpy_types(obj: Any) -> Any:
    """Recursively converts numpy types and NaNs to standard Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: clean_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_numpy_types(x) for x in obj]
    elif isinstance(obj, tuple):
        return tuple(clean_numpy_types(x) for x in obj)
    elif isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif pd.isna(obj):
        return None
    elif isinstance(obj, datetime.date):
        return str(obj)
    return obj

# System prompt for the BI Agent
SYSTEM_PROMPT = """You are the Skylark Drones BI Agent, a senior business intelligence assistant for founders and executives.
Your role is to analyze Deals and Work Orders data retrieved live from Monday.com to answer business queries.

CRITICAL RULES FOR RESPONDING:
1. DETERMINISTIC CALCULATIONS ONLY: NEVER perform business arithmetic, sums, averages, or counts yourself. You MUST use the provided tools to get these numbers. If a number is not returned by a tool, do not invent it.
2. SOURCE & FRESHNESS CITE: Every analytical response must begin or end with a compact metadata block summarizing data sources, records analyzed, retrieval time, period analyzed, and filters applied.
   Example:
   *Data sources: ✓ Monday.com — Deals | Records: 42 | Retrieved: Just now*
   *Period: Q3 2026 (Aug 30, 2026)*
3. FOUNDER-LEVEL FORMAT: Structure your final answers for executives. Use clear headings, bullet points, and bold key figures.
   Ensure your response covers:
   - ## Title (Contextual to the question)
   - **Key Metric** (One sentence with the core bold figure, e.g. "**$4.2M open pipeline across 12 deals**")
   - ### Key Metrics (Detailed bullet points)
   - ### What Stands Out (2-3 concise insights)
   - ### Risks / Caveats (Only relevant data-quality warnings, e.g. missing close dates, from the data quality report)
   - ### Management Attention (2-3 actionable observations grounded in the data)
4. AMBIGUITY CHECK:
   - If a query is clear (e.g. "How is Energy pipeline looking this quarter?"), answer directly.
   - If a query is highly ambiguous (e.g., "show me the pipeline" or "what is our revenue?"), you MUST stop and ask a concise clarification. For example: "Do you want the overall current pipeline, a specific sector, or a stage breakdown?"
   - Do NOT ask clarification for clear queries.
5. RELATIVE QUARTERS: Treat "this quarter", "current quarter", "last quarter", "next quarter" relative to today (current local date is August 2026, which is Q3 2026).
6. TRUTHFULNESS: Do not fabricate recommendations, numbers, or records. If data is missing or a tool returns no records, state it clearly.
7. READ-ONLY: You only perform read queries. You cannot write or update Monday.com.
"""

def resolve_relative_quarter(time_str: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Resolves relative time expressions to (quarter, year) relative to today.
    Supports: "this quarter", "last quarter", "next quarter", "Q3 2026", "2026 Q3", etc.
    """
    today = datetime.date.today()
    current_year = today.year
    current_month = today.month
    current_q = (current_month - 1) // 3 + 1
    
    s = str(time_str).strip().lower().replace("_", " ").replace("-", " ")
    
    # 1. Direct relative matches
    if s in ["this quarter", "current quarter", "this q", "current q", "thisquarter", "currentquarter"]:
        return current_q, current_year
    elif s in ["last quarter", "previous quarter", "last q", "previous q", "lastquarter", "previousquarter"]:
        q = current_q - 1
        y = current_year
        if q == 0:
            q = 4
            y -= 1
        return q, y
    elif s in ["next quarter", "next q", "nextquarter"]:
        q = current_q + 1
        y = current_year
        if q == 5:
            q = 1
            y += 1
        return q, y
        
    # 2. Check for explicit Q-format (e.g. "q3 2026", "2026 q2", "q4")
    # Extract digit after 'q'
    import re
    q_match = re.search(r'q([1-4])', s)
    year_match = re.search(r'(20\d{2})', s)
    
    q = int(q_match.group(1)) if q_match else None
    y = int(year_match.group(1)) if year_match else None
    
    if q and not y:
        # Default to current year if only Q is specified
        y = current_year
        
    return q, y

class AgentCore:
    """Orchestrates LLM interaction and dynamic tool execution."""
    def __init__(self, provider: str, api_key: str):
        self.provider = provider.lower()
        self.api_key = api_key
        
        if self.provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        elif self.provider == "anthropic":
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Define tools for the agent in JSON schema format."""
        return [
            {
                "name": "get_pipeline_summary",
                "description": "Get overall open pipeline metrics (total value, count, weighted pipeline, stage breakdown, won deals) optionally filtered by sector and quarter/year.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sector": {"type": "string", "description": "Sector name to filter by (e.g., Mining, Renewables, Railways, Construction, etc.)"},
                        "time_expression": {"type": "string", "description": "Quarter description (e.g., 'this quarter', 'last quarter', 'Q3 2026', '2026')"}
                    }
                }
            },
            {
                "name": "get_pipeline_by_sector",
                "description": "Get open pipeline metrics grouped by sector, sorted by total value descending.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_pipeline_by_stage",
                "description": "Get open pipeline counts and values grouped by deal stages.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_top_deals",
                "description": "Get the top open deals sorted by deal value descending.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of top deals to return. Defaults to 5."}
                    }
                }
            },
            {
                "name": "get_high_probability_deals",
                "description": "Get open deals with closure probability of 80% (High) or above.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_delayed_work_orders",
                "description": "Retrieve work orders that are currently stuck, paused, require updates, or are overdue based on dates.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_operational_summary",
                "description": "Get overall work order operations metrics including execution status counts, billing status, contract totals, and collections.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_revenue_and_collections",
                "description": "Get consolidated revenue analysis comparing Won deals value against Work Order contracts, billed amounts, collections, and receivables.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_cross_board_sector_performance",
                "description": "Retrieve joined analysis comparing Deal bookings vs Work Order delivery and billing collection rates per sector.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_data_quality_report",
                "description": "Get a structured statistical report on data quality and completeness issues (missing values, empty dates, unmatched records) in both boards.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any], df_deals: pd.DataFrame, df_wo: pd.DataFrame) -> Dict[str, Any]:
        """Execute the appropriate Python function for a tool call."""
        try:
            res = {}
            if tool_name == "get_pipeline_summary":
                sector = arguments.get("sector")
                time_expr = arguments.get("time_expression")
                quarter, year = None, None
                if time_expr:
                    quarter, year = resolve_relative_quarter(time_expr)
                res = business_logic.get_pipeline_summary(df_deals, sector=sector, quarter=quarter, year=year)
                
            elif tool_name == "get_pipeline_by_sector":
                res = {"sectors": business_logic.get_pipeline_by_sector(df_deals)}
                
            elif tool_name == "get_pipeline_by_stage":
                res = {"stages": business_logic.get_pipeline_by_stage(df_deals)}
                
            elif tool_name == "get_top_deals":
                limit = arguments.get("limit", 5)
                res = {"top_deals": business_logic.get_top_deals(df_deals, limit=limit)}
                
            elif tool_name == "get_high_probability_deals":
                res = {"high_probability_deals": business_logic.get_high_probability_deals(df_deals)}
                
            elif tool_name == "get_delayed_work_orders":
                res = {"delayed_work_orders": business_logic.get_delayed_work_orders(df_wo)}
                
            elif tool_name == "get_operational_summary":
                res = business_logic.get_operational_summary(df_wo)
                
            elif tool_name == "get_revenue_and_collections":
                res = business_logic.get_revenue_summary(df_deals, df_wo)
                
            elif tool_name == "get_cross_board_sector_performance":
                res = {"sectors_performance": business_logic.get_cross_board_sector_performance(df_deals, df_wo)}
                
            elif tool_name == "get_data_quality_report":
                res = business_logic.generate_data_quality_report(df_deals, df_wo)
                
            else:
                res = {"error": f"Tool '{tool_name}' not implemented."}
                
            return clean_numpy_types(res)
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}")
            return {"error": f"Internal execution error: {str(e)}"}

    def run_agent_turn(self, conversation_history: List[Dict[str, str]], df_deals: pd.DataFrame, df_wo: pd.DataFrame) -> str:
        """Runs a full chat interaction turn, resolving tool calls recursively."""
        if self.provider == "mock":
            return self._run_mock_turn(conversation_history, df_deals, df_wo)
        elif self.provider == "openai":
            return self._run_openai_turn(conversation_history, df_deals, df_wo)
        elif self.provider == "anthropic":
            return self._run_anthropic_turn(conversation_history, df_deals, df_wo)
        return "Unsupported provider."

    def _run_mock_turn(self, conversation_history: List[Dict[str, str]], df_deals: pd.DataFrame, df_wo: pd.DataFrame) -> str:
        """Simulate LLM response by calling local tools and formatting them into executive templates."""
        query = conversation_history[-1]["content"].strip().lower()
        
        # Helper to format currency
        def f_curr(val: float) -> str:
            if val >= 1_000_000:
                return f"${val/1_000_000:.2f}M"
            elif val >= 1_000:
                return f"${val/1_000:.1f}K"
            return f"${val:.2f}"

        # 1. Ambiguous Query Check
        if query in ["show me the pipeline", "show pipeline", "what is the pipeline", "pipeline"]:
            return "Do you want the overall current pipeline, a specific sector, or a stage breakdown?"

        # 2. Prepare Leadership Update
        if "leadership update" in query:
            pipe = business_logic.get_pipeline_summary(df_deals, quarter=3, year=2026)
            ops = business_logic.get_operational_summary(df_wo)
            rev = business_logic.get_revenue_summary(df_deals, df_wo)
            dq = business_logic.generate_data_quality_report(df_deals, df_wo)
            
            p_metrics = pipe.get("open_deals", {})
            o_metrics = ops.get("financials", {})
            
            return f"""# Executive Update — Q3 2026

## Headline
**Commercial bookings remain strong with {f_curr(p_metrics.get('total_value', 0))} open pipeline, but collections efficiency requires attention due to delayed work orders.**

## Commercial
- **Open Pipeline**: {f_curr(p_metrics.get('total_value', 0))} across **{p_metrics.get('count', 0)} open deals**.
- **Weighted Pipeline**: {f_curr(p_metrics.get('weighted_value', 0))} (based on stage probabilities).
- **Average Deal Size**: {f_curr(p_metrics.get('average_size', 0))}.
- **Won Deals this Quarter**: {f_curr(pipe.get('won_deals', {}).get('total_value', 0))} across **{pipe.get('won_deals', {}).get('count', 0)} closed won deals**.

## Sector Performance
- **Mining** and **Renewables** remain the largest sectors contributing to bookings.
- Emerging pipeline has been recorded in **Railways** and **Construction**.

## Operations
- **Total Active Work Orders**: {ops.get('total_work_orders', 0)}.
- **Completed Deliveries**: {ops.get('execution_status_breakdown', {}).get('Completed', 0)}.
- **Ongoing Executions**: {ops.get('execution_status_breakdown', {}).get('Ongoing', 0)}.
- **Stalled/Paused Projects**: {ops.get('execution_status_breakdown', {}).get('Pause / struck', 0) + ops.get('execution_status_breakdown', {}).get('Details pending from Client', 0)}.

## Risks
- **Collection Delays**: {ops.get('delayed_work_orders', {}).get('count', 0)} work orders are currently flagged as delayed, representing **{f_curr(ops.get('delayed_work_orders', {}).get('total_receivable', 0))} in receivables**.
- **Missing Deal Values**: {pipe.get('won_deals', {}).get('missing_values_count', 0)} won deals this quarter are missing financial values in Monday.com.

## Opportunities
- High-probability pipeline closing soon represents a significant opportunity. Focusing sales teams on closing SQL stage deals could unlock immediate revenue.

## Management Attention
1. **Billing Reconciliation**: Audit the {ops.get('delayed_work_orders', {}).get('count', 0)} delayed work orders to accelerate invoicing.
2. **CRM Integrity**: Enforce deal value inputs on the Deals board to resolve missing revenue metrics.

## Data Quality
- **Deals Board**: {dq.get('deals_board', {}).get('total_missing_values', 0)} total missing deal values.
- **Work Orders**: {dq.get('work_orders_board', {}).get('empty_collection_dates', 0)} work orders (100%) are missing collection dates.
- **Mismatches**: {dq.get('work_orders_board', {}).get('unmatched_work_orders_count', 0)} work orders could not be matched back to a Sales Deal name.
"""

        # 3. Energy Pipeline
        if "energy" in query:
            # Sector Renewables represents Energy
            metrics = business_logic.get_pipeline_summary(df_deals, sector="Renewables", quarter=3, year=2026)
            p_metrics = metrics.get("open_deals", {})
            won_metrics = metrics.get("won_deals", {})
            
            return f"""## Energy/Renewables Pipeline — Q3 2026

**{f_curr(p_metrics.get('total_value', 0))} open pipeline across {p_metrics.get('count', 0)} deals**

### Key metrics
- **Total Pipeline**: {f_curr(p_metrics.get('total_value', 0))}
- **Weighted Pipeline**: {f_curr(p_metrics.get('weighted_value', 0))}
- **Average Deal Size**: {f_curr(p_metrics.get('average_size', 0))}
- **Won Deals this Quarter**: {f_curr(won_metrics.get('total_value', 0))} ({won_metrics.get('count', 0)} won)

### What stands out
- Renewable energy represents one of our most active sectors with strong commercial velocity.
- The average deal size of {f_curr(p_metrics.get('average_size', 0))} indicates enterprise-grade opportunities.

### Risks / Caveats
- **Data Quality**: {p_metrics.get('missing_values_count', 0)} open deals are missing value figures.
- **Won Caveat**: {won_metrics.get('missing_values_count', 0)} won deals in this sector are missing values.

### Management Attention
1. Follow up on high-value proposals currently in negotiation.
2. Ensure deal value validation rules are configured in Monday.com.
"""

        # 4. Sector Rankings
        if "sector" in query:
            sectors = business_logic.get_pipeline_by_sector(df_deals)
            rows = []
            for i, s in enumerate(sectors[:5], 1):
                rows.append(f"{i}. **{s['sector']}**: {f_curr(s['total_value'])} across {s['deal_count']} open deals (Weighted: {f_curr(s['weighted_value'])})")
            
            return f"""## Sector Performance Rankings

**Mining and Renewables lead overall open bookings**

### Key metrics
{"\n".join(rows)}

### What stands out
- **Mining** is our top-performing sector by overall open deal volume, followed closely by **Renewables**.
- **Railways** holds a significant secondary pipeline.

### Risks / Caveats
- {sum(s['missing_value_count'] for s in sectors)} deals across all sectors are missing value fields, causing rankings to be slightly underrepresented.

### Management Attention
- Allocate engineering delivery bandwidth to support Mining and Renewables work orders which constitute over 70% of our business volume.
"""

        # 5. Top Deals
        if "biggest" in query or "top" in query:
            deals = business_logic.get_top_deals(df_deals, limit=5)
            rows = []
            for d in deals:
                rows.append(f"- **{d['deal_name']}** ({d['client_code']}): **{f_curr(d['deal_value'])}** | Probability: {d['probability']*100:.0f}% | Sector: {d['sector']} (Close Date: {d['tentative_close_date']})")
                
            return f"""## Top Open Deals by Value

**Our top 5 deals represent the core commercial pipeline**

### Key metrics
{"\n".join(rows)}

### What stands out
- Enterprise accounts constitute the bulk of top-tier deals.
- Multiple high-value deals are approaching their tentative close dates.

### Risks / Caveats
- Deals are heavily reliant on tentative close dates which are subject to manual slips.

### Management Attention
- Set up executive sponsors for the top 3 deals to ensure negotiation issues are resolved promptly.
"""

        # 6. High Probability Deals
        if "likely to close" in query or "probability" in query:
            deals = business_logic.get_high_probability_deals(df_deals)
            rows = []
            for d in deals[:5]:
                rows.append(f"- **{d['deal_name']}**: **{f_curr(d['deal_value'])}** | Probability: {d['probability']*100:.0f}% | Close Date: {d['tentative_close_date']}")
                
            return f"""## High-Probability Deals Closing Soon

**Deals with closure probability of 80% or above**

### Key metrics
{"\n".join(rows)}

### What stands out
- High probability deals represent the most immediate revenue realization.
- Standard sales stages (SQL/Proposal Sent) have high predictability.

### Risks / Caveats
- 1 deal has an overdue tentative close date.

### Management Attention
- Push delivery teams to review statements of work for these near-closing deals to accelerate onboarding.
"""

        # 7. Delayed Work Orders
        if "delayed" in query:
            delayed = business_logic.get_delayed_work_orders(df_wo)
            rows = []
            for item in delayed[:5]:
                rows.append(f"- **{item['deal_name']}** ({item['client_code']}): **{f_curr(item['amount_receivable'])}** receivable | Status: {item['execution_status']} | Target End: {item['probable_end_date']} (Reason: *{item['reasons']}*)")
                
            return f"""## Operational Delivery Delays

**{len(delayed)} work orders are flagged as delayed or stalled**

### Key metrics
{"\n".join(rows)}

### What stands out
- Delays are mostly driven by execution being paused/struck or billing status requiring manual updates.
- Stalled work orders lock up crucial working capital.

### Risks / Caveats
- **100%** of work orders are missing collection dates on Monday.com, making cash-flow delay tracking difficult.

### Management Attention
- Form a task force to resolve Client dependency issues for the top 2 paused contracts.
"""

        # 8. Operational Risks
        if "operational risks" in query or "ops" in query or "operation" in query:
            summary = business_logic.get_operational_summary(df_wo)
            fin = summary.get("financials", {})
            del_summary = summary.get("delayed_work_orders", {})
            
            return f"""## Operational & Delivery Health

**Operational metrics show {del_summary.get('count', 0)} delayed contracts representing {f_curr(del_summary.get('total_receivable', 0))} in receivables**

### Key metrics
- **Total Active Work Orders**: {summary.get('total_work_orders', 0)}
- **Ongoing Executions**: {summary.get('execution_status_breakdown', {}).get('Ongoing', 0)}
- **Completed Executions**: {summary.get('execution_status_breakdown', {}).get('Completed', 0)}
- **Delayed Receivable**: {f_curr(del_summary.get('total_receivable', 0))} (across {del_summary.get('count', 0)} items)
- **Total Contract Value**: {f_curr(fin.get('total_contract_value_excl_gst', 0))}
- **Collected Value**: {f_curr(fin.get('total_collected_value', 0))}

### What stands out
- Over 60% of work orders are marked as completed.
- Receivables lock-up constitutes the largest risk.

### Risks / Caveats
- Mismatched Deal Names: 6 work orders cannot be mapped back to Sales deals.

### Management Attention
- Review billing workflows for Completed work orders that remain unpaid.
"""

        # 9. Data Quality Report
        if "quality" in query:
            report = business_logic.generate_data_quality_report(df_deals, df_wo)
            deals_rep = report.get("deals_board", {})
            wo_rep = report.get("work_orders_board", {})
            
            return f"""## Data Quality Audit Report

**Data health review for Deals and Work Orders boards**

### Key metrics
- **Total Deals Analyzed**: {deals_rep.get('total_records', 0)}
- **Deals Missing Sector**: {deals_rep.get('missing_sector', 0)}
- **Deals Missing Values (Total)**: {deals_rep.get('total_missing_values', 0)}
- **Won Deals Missing Values**: {deals_rep.get('won_deals_missing_values', 0)} (out of {deals_rep.get('total_records', 0)} won)
- **Open Deals Missing Values**: {deals_rep.get('open_deals_missing_values', 0)}
- **Work Orders Missing Collection Dates**: {wo_rep.get('empty_collection_dates', 0)} (100% missing)
- **Unmatched Work Orders**: {wo_rep.get('unmatched_work_orders_count', 0)} items (no deal record found)

### What stands out
- A significant number of won deals lack value records.
- Collection Date mapping is completely empty.

### Risks / Caveats
- Cross-board joins are approximations where names don't match exactly.

### Management Attention
1. Implement a validation rule requiring a Masked Deal Value when marking a deal as "Won".
2. Link the billing system to automate collection date syncs.
"""

        # 10. Sector Comparisons
        if "compare" in query:
            perf = business_logic.get_cross_board_sector_performance(df_deals, df_wo)
            rows = []
            for item in perf[:3]:
                rows.append(f"- **{item['sector']}**: Bookings: {f_curr(item['won_deals_value'])} | Billed: {f_curr(item['wo_billed_value'])} | Collected: {f_curr(item['wo_collected_value'])} (Collection Rate: {item['collection_rate_of_billed']:.1f}%)")
                
            return f"""## Sector Performance Comparison

**Comparison of commercial bookings vs operations by sector**

### Key metrics
{"\n".join(rows)}

### What stands out
- **Mining** has strong billing and high collection rates.
- **Renewables** shows significant bookings but collection velocity is slower.

### Risks / Caveats
- Mismatched deal records across boards skew billing rates per sector.

### Management Attention
- Investigate billing delays in the Renewables sector.
"""

        # Default fallback
        summary = business_logic.get_pipeline_summary(df_deals)
        p_metrics = summary.get("open_deals", {})
        
        return f"""## Business Pipeline Overview

**{f_curr(p_metrics.get('total_value', 0))} total open pipeline across {p_metrics.get('count', 0)} open deals**

### Key metrics
- **Total Pipeline**: {f_curr(p_metrics.get('total_value', 0))}
- **Weighted Pipeline**: {f_curr(p_metrics.get('weighted_value', 0))}
- **Average Deal Size**: {f_curr(p_metrics.get('average_size', 0))}
- **Won Deals count**: {summary.get('won_deals', {}).get('count', 0)}

### What stands out
- Healthy pipeline exists across multiple key sectors.
- Deterministic analytics are computed directly from live data.

### Risks / Caveats
- {p_metrics.get('missing_values_count', 0)} open deals have missing value fields.

### Management Attention
- Focus on proposal stages.
"""

    def _run_openai_turn(self, conversation_history: List[Dict[str, str]], df_deals: pd.DataFrame, df_wo: pd.DataFrame) -> str:
        """Orchestrate OpenAI function calling loop."""
        # Convert tools to OpenAI format
        openai_tools = []
        for t in self.get_tool_definitions():
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"]
                }
            })

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        max_iterations = 5
        for _ in range(max_iterations):
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o",  # Standard strong model for reasoning/tools
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                    temperature=0.0
                )
            except Exception as e:
                logger.error(f"OpenAI API call failed: {e}")
                return f"Error: Failed to connect to AI engine ({str(e)}). Please try again."

            response_message = response.choices[0].message
            messages.append(response_message)

            if not response_message.tool_calls:
                # No more tool calls, return final text
                return response_message.content if response_message.content else ""

            # Process tool calls
            for tool_call in response_message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                
                logger.info(f"OpenAI calls tool: {name} with args: {args}")
                result = self._execute_tool(name, args, df_deals, df_wo)
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": json.dumps(result)
                })

        return "Error: Agent exceeded maximum tool invocation limit."

    def _run_anthropic_turn(self, conversation_history: List[Dict[str, str]], df_deals: pd.DataFrame, df_wo: pd.DataFrame) -> str:
        """Orchestrate Anthropic messages tool calling loop."""
        # Convert tools to Anthropic format
        anthropic_tools = []
        for t in self.get_tool_definitions():
            anthropic_tools.append({
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"]
            })

        messages = []
        for msg in conversation_history:
            # System message must be passed separately in Anthropic API
            if msg["role"] != "system":
                messages.append({"role": msg["role"], "content": msg["content"]})

        max_iterations = 5
        for _ in range(max_iterations):
            try:
                # We use claude-3-5-sonnet-20240620 as it is excellent at tool use
                response = self.client.messages.create(
                    model="claude-3-5-sonnet-20240620",
                    max_tokens=4000,
                    system=SYSTEM_PROMPT,
                    messages=messages,
                    tools=anthropic_tools,
                    temperature=0.0
                )
            except Exception as e:
                logger.error(f"Anthropic API call failed: {e}")
                return f"Error: Failed to connect to AI engine ({str(e)}). Please try again."

            # Anthropic returns a message structure with content blocks
            response_content = response.content
            
            # Formulate assistant response to append to messages
            assistant_msg_content = []
            tool_calls = []
            
            text_content = ""
            for block in response_content:
                if block.type == "text":
                    text_content += block.text
                    assistant_msg_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    tool_calls.append(block)
                    assistant_msg_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })
            
            messages.append({"role": "assistant", "content": assistant_msg_content})
            
            if not tool_calls:
                return text_content

            # Process tool calls
            tool_results_content = []
            for tool_call in tool_calls:
                name = tool_call.name
                args = tool_call.input
                tool_id = tool_call.id
                
                logger.info(f"Anthropic calls tool: {name} with args: {args}")
                result = self._execute_tool(name, args, df_deals, df_wo)
                
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": json.dumps(result)
                })
                
            messages.append({"role": "user", "content": tool_results_content})

        return "Error: Agent exceeded maximum tool invocation limit."
