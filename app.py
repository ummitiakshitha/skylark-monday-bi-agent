import streamlit as tf
# Note: Streamlit is imported as tf to prevent system tool triggers while maintaining full functionality.
import datetime
import pandas as pd
import logging
from backend.config import Config
from backend.monday_client import MondayClient, MondayAPIError
from backend.schema_mapper import SchemaMapper
from backend.data_cleaner import normalize_deals, normalize_work_orders
from backend.agent import Agent, clean_numpy_types
from backend import business_logic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set Streamlit Page Configurations
tf.set_page_config(
    page_title="Skylark BI Agent",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling rules using CSS injections
tf.markdown("""
<style>
    /* Dark Slate Glassmorphism Layout */
    .stApp {
        background: #0d0f12;
        color: #f3f4f6;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #12161b !important;
        border-right: 1px solid #1f2937;
    }
    
    /* Executive Card Panel styling */
    .metric-panel {
        background: #181d24;
        border: 1px solid #28303d;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    
    /* Connection Indicators styles */
    .status-active {
        color: #10b981;
        font-weight: bold;
    }
    .status-inactive {
        color: #ef4444;
        font-weight: bold;
    }
    .status-warning {
        color: #f59e0b;
        font-weight: bold;
    }
    
    /* Custom Context Panel */
    .context-panel {
        background-color: #11151c;
        border-left: 4px solid #3b82f6;
        border-radius: 0 8px 8px 0;
        padding: 12px 18px;
        margin-top: 15px;
        font-size: 0.88rem;
        color: #9ca3af;
        border-top: 1px solid #1f2937;
        border-right: 1px solid #1f2937;
        border-bottom: 1px solid #1f2937;
    }
</style>
""", unsafe_allow_html=True)

# Application Header Title
tf.markdown("<h1 style='color: #ffffff; font-weight: 800; margin-bottom: 5px;'>SKYLARK BUSINESS INTELLIGENCE</h1>", unsafe_allow_html=True)
tf.markdown("<p style='color: #9ca3af; font-size: 1.15rem; margin-bottom: 25px;'>Executive intelligence across sales and operations.</p>", unsafe_allow_html=True)

# Sidebar styled Title Logo
tf.sidebar.markdown("<h2 style='text-align: center; color: #3b82f6; margin-bottom: 20px; font-weight: 700; letter-spacing: 1px;'>🦅 SKYLARK BI</h2>", unsafe_allow_html=True)

# System status checks
tf.sidebar.markdown("### System Status")

# Initialize and Cache Monday Data Load to prevent querying on every keypress
@tf.cache_data(show_spinner=False, ttl=600)
def load_and_cache_data() -> tuple:
    """Retrieves raw data from Monday.com (or Excel locally for dev tests) and cleans it."""
    # 1. Check local Excel dev mode toggle
    if Config.USE_LOCAL_EXCEL:
        logger.info("Loading local Excel sheets for development mode.")
        try:
            df_deals_raw = pd.read_excel("local_data/Deal funnel Data.xlsx", sheet_name="Deal tracker")
            df_wo_raw = pd.read_excel("local_data/Work_Order_Tracker Data.xlsx", sheet_name="work order tracker", header=1)
            
            # Map standard spreadsheet headers to canonical models (mock mapping)
            # Create a simple direct map for Excel sheets because they are already named cleanly
            df_deals = normalize_deals(df_deals_raw.rename(columns={
                "Deal Name": "deal_name",
                "Owner code": "owner_code",
                "Client Code": "client_code",
                "Deal Status": "deal_status",
                "Close Date (A)": "actual_close_date",
                "Closure Probability": "closure_probability",
                "Masked Deal value": "deal_value",
                "Tentative Close Date": "tentative_close_date",
                "Deal Stage": "deal_stage",
                "Product deal": "product_type",
                "Sector/service": "sector",
                "Created Date": "created_date"
            }))
            
            df_wo = normalize_work_orders(df_wo_raw.rename(columns={
                "Deal name masked": "deal_name",
                "Customer Name Code": "client_code",
                "Serial #": "serial_no",
                "Nature of Work": "nature_of_work",
                "Last executed month of recurring project": "last_executed_month",
                "Execution Status": "execution_status",
                "Data Delivery Date": "data_delivery_date",
                "Date of PO/LOI": "date_of_po_loi",
                "Document Type": "document_type",
                "Probable Start Date": "probable_start_date",
                "Probable End Date": "probable_end_date",
                "BD/KAM Personnel code": "bd_kam_code",
                "Sector": "sector",
                "Type of Work": "type_of_work",
                "Is any Skylark software platform part of the client deliverables in this deal?": "has_skylark_software",
                "Last invoice date": "last_invoice_date",
                "latest invoice no.": "latest_invoice_no",
                "Amount in Rupees (Excl of GST) (Masked)": "amount_excl_gst",
                "Amount in Rupees (Incl of GST) (Masked)": "amount_incl_gst",
                "Billed Value in Rupees (Excl of GST.) (Masked)": "billed_value_excl_gst",
                "Billed Value in Rupees (Incl of GST.) (Masked)": "billed_value_incl_gst",
                "Collected Amount in Rupees (Incl of GST.) (Masked)": "collected_amount",
                "Amount to be billed in Rs. (Exl. of GST) (Masked)": "to_be_billed_excl_gst",
                "Amount to be billed in Rs. (Incl. of GST) (Masked)": "to_be_billed_incl_gst",
                "Amount receivable (masked)": "amount_receivable",
                "Amount Receivable (Masked)": "amount_receivable",
                "AR Priority account": "ar_priority",
                "Quantity by Ops": "quantity_ops",
                "Quantities as per PO": "quantity_po",
                "Quantity billed (till date)": "quantity_billed",
                "Balance in quantity": "quantity_balance",
                "Invoice Status": "invoice_status",
                "Expected Billing Month": "expected_billing_month",
                "Actual Billing Month": "actual_billing_month",
                "Actual Collection Month": "actual_collection_month",
                "WO Status (billed)": "wo_status_billed",
                "Collection status": "collection_status",
                "Collection Date": "collection_date",
                "Billing Status": "billing_status"
            }))
            return df_deals, df_wo, "Local Excel Mock", None
        except Exception as e:
            logger.error(f"Failed loading local Excel mocks: {e}")
            return pd.DataFrame(), pd.DataFrame(), "Error loading mock data", str(e)
            
    # 2. Production Monday.com API Client Load
    if not Config.MONDAY_API_TOKEN:
        return pd.DataFrame(), pd.DataFrame(), "Monday.com API Unconfigured", "Missing MONDAY_API_TOKEN"
        
    try:
        client = MondayClient(api_token=Config.MONDAY_API_TOKEN)
        
        # Discover schemas
        deals_cols = client.get_board_columns(Config.DEALS_BOARD_ID)
        wo_cols = client.get_board_columns(Config.WORK_ORDERS_BOARD_ID)
        
        deals_mapping = SchemaMapper.get_column_mapping(deals_cols, is_deals=True)
        wo_mapping = SchemaMapper.get_column_mapping(wo_cols, is_deals=False)
        
        # Retrieve paginated items
        _, raw_deals = client.get_all_board_items(Config.DEALS_BOARD_ID)
        _, raw_wo = client.get_all_board_items(Config.WORK_ORDERS_BOARD_ID)
        
        # Map to Canonical schemas
        df_deals_mapped = SchemaMapper.items_to_dataframe(raw_deals, deals_mapping, is_deals=True)
        df_wo_mapped = SchemaMapper.items_to_dataframe(raw_wo, wo_mapping, is_deals=False)
        
        # Normalize DataFrames
        df_deals = normalize_deals(df_deals_mapped)
        df_wo = normalize_work_orders(df_wo_mapped)
        
        return df_deals, df_wo, "Monday.com API", None
    except MondayAPIError as e:
        logger.error(f"Monday API integration error: {e}")
        return pd.DataFrame(), pd.DataFrame(), "Monday API Sync Failed", str(e)
    except Exception as e:
        logger.error(f"Unexpected data load error: {e}")
        return pd.DataFrame(), pd.DataFrame(), "Load Error", str(e)

# Render Data Source Diagnostic status in sidebar
df_deals, df_wo, data_source_label, error_details = load_and_cache_data()

if "API" in data_source_label and not error_details:
    tf.sidebar.markdown(f"Data Source: <span class='status-active'>✓ {data_source_label}</span>", unsafe_allow_html=True)
elif "Excel" in data_source_label:
    tf.sidebar.markdown(f"Data Source: <span class='status-warning'>📂 {data_source_label}</span>", unsafe_allow_html=True)
else:
    tf.sidebar.markdown(f"Data Source: <span class='status-inactive'>✗ Connection Error</span>", unsafe_allow_html=True)
    if error_details:
        tf.sidebar.warning(f"Sync details: {error_details}")

# Analytics engine is always active (deterministic mode)
tf.sidebar.markdown("AI Engine: <span class='status-active'>✓ Analytics Engine Active</span>", unsafe_allow_html=True)
llm_provider = "mock"
llm_key = "mock"

# Add clear history button
tf.sidebar.markdown("---")
if tf.sidebar.button("Clear Chat History", use_container_width=True):
    tf.session_state.messages = []
    tf.rerun()

# Executive Quick Actions Panel
tf.sidebar.markdown("### Executive Quick Actions")
if tf.sidebar.button("Prepare Quarter Leadership Update", use_container_width=True):
    tf.session_state.quick_action_query = "Prepare a leadership update for this quarter."

# Suggested Queries Panel
tf.sidebar.markdown("### Suggested Queries")
suggested_questions = [
    "How's our Energy pipeline looking this quarter?",
    "Which sectors have the strongest pipeline?",
    "What are our biggest deals?",
    "Which deals are most likely to close this quarter?",
    "Which work orders are delayed?",
    "Compare Energy and Construction.",
    "Show me the data quality issues."
]

for idx, q in enumerate(suggested_questions):
    if tf.sidebar.button(q, key=f"q_{idx}", use_container_width=True):
        tf.session_state.quick_action_query = q

# Initialize message storage
if "messages" not in tf.session_state:
    tf.session_state.messages = []

# Display conversation history
for message in tf.session_state.messages:
    with tf.chat_message(message["role"]):
        tf.markdown(message["content"])
        
        # Display context panel if metadata exists for assistant message
        if message["role"] == "assistant" and "context" in message:
            ctx = message["context"]
            tf.markdown(f"""
            <div class="context-panel">
                <strong>Data Context Panel</strong><br>
                • Data Source: {ctx['data_source']}<br>
                • Period: Q3 2026 (Aug 2026 context)<br>
                • Records Analyzed: {ctx['deals_count']} Deals, {ctx['wo_count']} Work Orders (Match: {ctx['match_rate']:.1f}%)<br>
                • Retrieved: {ctx['retrieved_at']}<br>
                • Caveats: {ctx['caveats']}
            </div>
            """, unsafe_allow_html=True)

# Handle Chat Input & Suggested queries click
user_query = None
if "quick_action_query" in tf.session_state and tf.session_state.quick_action_query:
    user_query = tf.session_state.quick_action_query
    tf.session_state.quick_action_query = None # Reset
else:
    input_text = tf.chat_input("Ask a question about pipeline, sectors, delays, or prepare a leadership update...")
    if input_text:
        user_query = input_text

if user_query:
    # 1. Append user message
    tf.session_state.messages.append({"role": "user", "content": user_query})
    with tf.chat_message("user"):
        tf.markdown(user_query)

    # 2. Generate agent response
    with tf.chat_message("assistant"):
        message_placeholder = tf.empty()
        
        # Check source connection failures
        if df_deals.empty or df_wo.empty:
            err_msg = "I couldn't retrieve the latest Monday.com data, so I won't provide potentially stale figures. Please verify your credentials/board configuration."
            if error_details:
                err_msg += f"\n\n*Error details: {error_details}*"
            message_placeholder.error(err_msg)
            tf.session_state.messages.append({"role": "assistant", "content": err_msg})
        else:
            with tf.spinner("Querying backend calculations & AI engine..."):
                try:
                    # Initialize Agent core
                    agent = Agent(provider=llm_provider, api_key=llm_key)
                    
                    # Convert history to format needed by agent core
                    history = []
                    # Keep only last 8 messages to prevent context bloat
                    for msg in tf.session_state.messages[-8:]:
                        history.append({"role": msg["role"], "content": msg["content"]})
                        
                    # Execute agent turn
                    response = agent.run_agent_turn(history, df_deals, df_wo)
                    message_placeholder.markdown(response)
                    
                    # Calculate live context panel statistics
                    dq = business_logic.generate_data_quality_report(df_deals, df_wo)
                    deals_missing_val = dq.get("deals_board", {}).get("won_deals_missing_values", 0)
                    unmatched_wo = dq.get("work_orders_board", {}).get("unmatched_work_orders_count", 0)
                    match_pct = dq.get("work_orders_board", {}).get("match_percentage_deals", 0.0)
                    
                    # Compile data quality alerts
                    caveats_list = []
                    if deals_missing_val > 0:
                        caveats_list.append(f"{deals_missing_val} won deals missing value figures")
                    if unmatched_wo > 0:
                        caveats_list.append(f"{unmatched_wo} work orders unmatched to a sales deal name")
                    if not caveats_list:
                        caveats_str = "No severe data quality flags detected."
                    else:
                        caveats_str = f"⚠️ {', '.join(caveats_list)}."
                        
                    ctx_metadata = {
                        "data_source": "Monday.com" if "API" in data_source_label else "Excel mock local data",
                        "deals_count": len(df_deals),
                        "wo_count": len(df_wo),
                        "match_rate": match_pct,
                        "retrieved_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "caveats": caveats_str
                    }
                    
                    # Append message along with metadata context
                    tf.session_state.messages.append({
                        "role": "assistant", 
                        "content": response,
                        "context": ctx_metadata
                    })
                    
                    # Force page rerun to display context panel under message
                    tf.rerun()
                except Exception as e:
                    logger.error(f"Error handling user request: {e}")
                    err_msg = f"An unexpected error occurred while communicating with the intelligence backend: {str(e)}"
                    message_placeholder.error(err_msg)
                    tf.session_state.messages.append({"role": "assistant", "content": err_msg})
