import os
import datetime
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd

# Import our deterministic business logic functions
import business_logic

logger = logging.getLogger(__name__)

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
            if tool_name == "get_pipeline_summary":
                sector = arguments.get("sector")
                time_expr = arguments.get("time_expression")
                quarter, year = None, None
                if time_expr:
                    quarter, year = resolve_relative_quarter(time_expr)
                return business_logic.get_pipeline_summary(df_deals, sector=sector, quarter=quarter, year=year)
                
            elif tool_name == "get_pipeline_by_sector":
                return {"sectors": business_logic.get_pipeline_by_sector(df_deals)}
                
            elif tool_name == "get_pipeline_by_stage":
                return {"stages": business_logic.get_pipeline_by_stage(df_deals)}
                
            elif tool_name == "get_top_deals":
                limit = arguments.get("limit", 5)
                return {"top_deals": business_logic.get_top_deals(df_deals, limit=limit)}
                
            elif tool_name == "get_high_probability_deals":
                return {"high_probability_deals": business_logic.get_high_probability_deals(df_deals)}
                
            elif tool_name == "get_delayed_work_orders":
                return {"delayed_work_orders": business_logic.get_delayed_work_orders(df_wo)}
                
            elif tool_name == "get_operational_summary":
                return business_logic.get_operational_summary(df_wo)
                
            elif tool_name == "get_revenue_and_collections":
                return business_logic.get_revenue_summary(df_deals, df_wo)
                
            elif tool_name == "get_cross_board_sector_performance":
                return {"sectors_performance": business_logic.get_cross_board_sector_performance(df_deals, df_wo)}
                
            elif tool_name == "get_data_quality_report":
                return business_logic.generate_data_quality_report(df_deals, df_wo)
                
            else:
                return {"error": f"Tool '{tool_name}' not implemented."}
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}")
            return {"error": f"Internal execution error: {str(e)}"}

    def run_agent_turn(self, conversation_history: List[Dict[str, str]], df_deals: pd.DataFrame, df_wo: pd.DataFrame) -> str:
        """Runs a full chat interaction turn, resolving tool calls recursively."""
        if self.provider == "openai":
            return self._run_openai_turn(conversation_history, df_deals, df_wo)
        elif self.provider == "anthropic":
            return self._run_anthropic_turn(conversation_history, df_deals, df_wo)
        return "Unsupported provider."

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
                args = json.loads(tool_call.function.argv if hasattr(tool_call.function, "argv") else tool_call.function.arguments)
                
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
