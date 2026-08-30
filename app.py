import streamlit as st
import os
import datetime
import logging
import pandas as pd
from dotenv import load_dotenv

# Import our custom modules
from monday_client import MondayClient, MondayAPIError
import data_cleaner
import business_logic
from agent_core import AgentCore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env variables from .env during local development
load_dotenv()

# Page configuration for a premium dashboard look
st.set_page_config(
    page_title="Skylark Drones — Monday.com BI Agent",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for rich executive aesthetics
st.markdown("""
<style>
    .reportview-container {
        background: #0f1116;
    }
    .sidebar .sidebar-content {
        background: #161920;
    }
    h1, h2, h3 {
        color: #e2e8f0 !important;
        font-weight: 600;
    }
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
    }
    .status-active {
        color: #10b981;
        font-weight: bold;
    }
    .status-inactive {
        color: #ef4444;
        font-weight: bold;
    }
    .metadata-block {
        font-size: 0.85em;
        color: #94a3b8;
        background-color: #1e293b;
        padding: 8px 12px;
        border-left: 3px solid #3b82f6;
        border-radius: 4px;
        margin-top: 10px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_html=True)

# App Header
st.title("🦅 Skylark Drones BI Agent")
st.markdown("An executive intelligence agent querying **Monday.com Work Orders & Deals** live.")

# Sidebar Configuration & Diagnostics
st.sidebar.image("https://www.skylarkdrones.com/assets/images/logo.png", width=180, error_handling="skip")
st.sidebar.markdown("### System Status")

# Check credentials
monday_token = os.getenv("MONDAY_API_TOKEN")
deals_board_id = os.getenv("DEALS_BOARD_ID")
wo_board_id = os.getenv("WORK_ORDERS_BOARD_ID")

openai_key = os.getenv("OPENAI_API_KEY")
anthropic_key = os.getenv("ANTHROPIC_API_KEY")

# For local testing fallback only (will not be exposed as a public toggle in production)
use_local_excel = os.getenv("USE_LOCAL_EXCEL", "false").lower() == "true"

# Display diagnostics in sidebar
if use_local_excel:
    st.sidebar.markdown("Data Source: 📂 **Local Excel Mock** (Local Dev Only)")
else:
    if monday_token and deals_board_id and wo_board_id:
        st.sidebar.markdown("Data Source: <span class='status-active'>✓ Monday.com API (Live)</span>", unsafe_html=True)
    else:
        st.sidebar.markdown("Data Source: <span class='status-inactive'>✗ Monday.com API (Missing Keys)</span>", unsafe_html=True)

# LLM Status
llm_provider = None
llm_key = None
if openai_key:
    llm_provider = "OpenAI"
    llm_key = openai_key
    st.sidebar.markdown("AI Engine: <span class='status-active'>✓ OpenAI Connected</span>", unsafe_html=True)
elif anthropic_key:
    llm_provider = "Anthropic"
    llm_key = anthropic_key
    st.sidebar.markdown("AI Engine: <span class='status-active'>✓ Anthropic Connected</span>", unsafe_html=True)
else:
    st.sidebar.markdown("AI Engine: <span class='status-inactive'>✗ Missing LLM Key</span>", unsafe_html=True)

st.sidebar.markdown("---")

# Quick Actions
st.sidebar.markdown("### Executive Quick Actions")

# We populate a session variable if a demo query is clicked
if "query_input" not in st.session_state:
    st.session_state.query_input = ""

def set_query(q_text):
    st.session_state.query_input = q_text

if st.sidebar.button("📊 Prepare Quarter Leadership Update"):
    set_query("Prepare a leadership update for this quarter.")

st.sidebar.markdown("### Suggested Queries")
demo_queries = [
    "How's our Energy pipeline looking this quarter?",
    "Which sectors have the strongest pipeline?",
    "What are our biggest deals?",
    "Which deals are most likely to close this quarter?",
    "Which work orders are delayed?",
    "What operational risks do we have?",
    "Compare Energy and Construction.",
    "Show me the data quality issues.",
    "Show me the pipeline."
]

for q in demo_queries:
    if st.sidebar.button(q, key=f"btn_{q}"):
        set_query(q)

st.sidebar.markdown("---")

# Data fetch function
def fetch_and_clean_data():
    """Fetches raw data (from Monday or Local Excel) and returns cleaned dataframes + quality report."""
    if use_local_excel:
        logger.info("Loading local Excel sheets for development mode.")
        df_deals, df_wo = data_cleaner.load_and_clean_local_data()
        quality_report = business_logic.generate_data_quality_report(df_deals, df_wo)
        return df_deals, df_wo, quality_report, "Local Excel", len(df_deals), len(df_wo), None
        
    if not monday_token or not deals_board_id or not wo_board_id:
        raise ValueError(
            "Monday.com credentials missing! Please configure the environment variables:\n"
            "- `MONDAY_API_TOKEN`\n"
            "- `DEALS_BOARD_ID`\n"
            "- `WORK_ORDERS_BOARD_ID`"
        )
        
    client = MondayClient(monday_token)
    
    try:
        # Fetch Deals
        _, df_deals_raw = client.fetch_board_items(deals_board_id)
        df_deals = data_cleaner.clean_deals_df(df_deals_raw)
        
        # Fetch Work Orders
        _, df_wo_raw = client.fetch_board_items(wo_board_id)
        df_wo = data_cleaner.clean_work_orders_df(df_wo_raw)
        
        # Quality report
        quality_report = business_logic.generate_data_quality_report(df_deals, df_wo)
        
        return df_deals, df_wo, quality_report, "Monday.com", len(df_deals), len(df_wo), None
    except MondayAPIError as e:
        logger.error(f"Monday API connection error: {e}")
        raise e
    except Exception as e:
        logger.error(f"Failed to fetch data: {e}")
        raise e

# Initial data load for diagnostic summary in sidebar
try:
    df_deals_diag, df_wo_diag, quality_diag, src_name, deals_count, wo_count, _ = fetch_and_clean_data()
    st.sidebar.markdown("### Data Summary")
    st.sidebar.text(f"Deals analyzed: {deals_count}")
    st.sidebar.text(f"Work Orders: {wo_count}")
    
    # Visual quality warning in sidebar
    unmatched_wo = quality_diag.get("work_orders_board", {}).get("unmatched_work_orders_count", 0)
    won_missing_vals = quality_diag.get("deals_board", {}).get("won_deals_missing_values", 0)
    
    st.sidebar.markdown("### Caveats Highlighted")
    if unmatched_wo > 0:
        st.sidebar.warning(f"⚠️ {unmatched_wo} work orders have unmatched Deal Names.")
    if won_missing_vals > 0:
        st.sidebar.warning(f"⚠️ {won_missing_vals} won deals are missing values.")
    if unmatched_wo == 0 and won_missing_vals == 0:
        st.sidebar.success("✓ No major cross-board mismatch.")
except Exception as ex:
    st.sidebar.error(f"Error loading board metadata: {ex}")

# Main Chat Interface
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "metadata" in msg:
            st.markdown(f"<div class='metadata-block'>{msg['metadata']}</div>", unsafe_html=True)

# Main chat input execution
user_query = st.chat_input("Ask a question about pipeline, sectors, delays, or prepare a leadership update...")

# If a quick action button was clicked, we override the user_query
if st.session_state.query_input:
    user_query = st.session_state.query_input
    st.session_state.query_input = ""  # Reset trigger

if user_query:
    # 1. Display user query
    with st.chat_message("user"):
        st.markdown(user_query)
    st.session_state.messages.append({"role": "user", "content": user_query})
    
    # 2. Get AI Response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        # Check system keys
        if not llm_key or not llm_provider:
            err_msg = "I am missing the AI reasoning engine API key (OPENAI_API_KEY or ANTHROPIC_API_KEY). Please configure it in your environment/secrets."
            message_placeholder.error(err_msg)
            st.session_state.messages.append({"role": "assistant", "content": err_msg})
        else:
            with st.spinner("Retrieving latest data and analyzing..."):
                try:
                    # Retrieve data dynamically at query time
                    df_deals, df_wo, quality_report, data_source, deals_cnt, wo_cnt, _ = fetch_and_clean_data()
                    
                    # Initialize Agent Core
                    agent = AgentCore(provider=llm_provider, api_key=llm_key)
                    
                    # Prepare messages
                    history = []
                    # We pass the last 5 turns of conversation to keep it token efficient
                    for msg in st.session_state.messages[-10:]:
                        history.append({"role": msg["role"], "content": msg["content"]})
                        
                    # Execute agent loop
                    response_text = agent.run_agent_turn(history, df_deals, df_wo)
                    
                    # Construct metadata section
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    metadata_html = f"**Data source:** ✓ {data_source} Live | **Deals analyzed:** {deals_cnt} | **Work orders:** {wo_cnt} | **Sync time:** {now_str}"
                    
                    # Display response
                    message_placeholder.markdown(response_text)
                    st.markdown(f"<div class='metadata-block'>{metadata_html}</div>", unsafe_html=True)
                    
                    # Save to state
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": response_text,
                        "metadata": metadata_html
                    })
                    
                except Exception as e:
                    # Safe deterministic fallback if everything fails
                    err_msg = (
                        "I couldn't retrieve the latest Monday.com data, so I won't provide potentially stale figures. "
                        "Please verify your credentials and connection.\n\n"
                        f"*Details: {str(e)}*"
                    )
                    message_placeholder.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})
                    
    # Force page rerun to display correctly
    st.rerun()
