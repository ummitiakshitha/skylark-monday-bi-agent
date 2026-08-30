import pandas as pd
import numpy as np
import datetime
from typing import Any, Tuple

SECTOR_NORMALIZATION_MAP = {
    "renewables": "Renewables",
    "mining": "Mining",
    "railways": "Railways",
    "others": "Others",
    "powerline": "Powerline",
    "construction": "Construction",
    "dsp": "DSP",
    "tender": "Tender",
    "manufacturing": "Manufacturing",
    "security and surveillance": "Security and Surveillance",
    "aviation": "Aviation",
    "defence": "Defence"
}

def normalize_text(val: Any) -> Any:
    """Strips outer whitespaces from strings, handles nulls."""
    if pd.isna(val) or not str(val).strip():
        return None
    return str(val).strip()

def normalize_sector(val: Any) -> str:
    """Standardizes sector values to uniform categories."""
    if pd.isna(val) or not str(val).strip():
        return "Unknown"
    s = str(val).strip().lower()
    if s in SECTOR_NORMALIZATION_MAP:
        return SECTOR_NORMALIZATION_MAP[s]
    return s.title()

def parse_date(val: Any) -> Any:
    """Parses any date representation safely to datetime.date or None."""
    if pd.isna(val) or not str(val).strip():
        return None
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            dt = pd.to_datetime(val, errors="coerce")
            if pd.notna(dt):
                return dt.date()
    except Exception:
        pass
    return None

def parse_number(val: Any) -> float:
    """Parses numeric fields, strips currency symbols and commas, returns float."""
    if pd.isna(val) or not str(val).strip():
        return 0.0
    s = str(val).strip().replace("$", "").replace("₹", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0

def normalize_deals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and canonicalizes the mapped Deals DataFrame.
    Filters Nezuko and Bugs Bunny rows.
    """
    if df.empty:
        return df
        
    df_clean = df.copy()
    
    # 1. Filter out duplicate header value rows
    if "deal_status" in df_clean.columns:
        df_clean = df_clean[df_clean["deal_status"] != "Deal Status"]
    if "deal_stage" in df_clean.columns:
        df_clean = df_clean[df_clean["deal_stage"] != "Deal Stage"]
        
    # 2. Text Normalizations
    for col in ["deal_name", "owner_code", "client_code", "deal_status", "deal_stage", "product_type"]:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(normalize_text)
            
    # 3. Sector Normalization
    if "sector" in df_clean.columns:
        df_clean["sector"] = df_clean["sector"].apply(normalize_sector)
    else:
        df_clean["sector"] = "Unknown"
        
    # 4. Numeric Parse
    if "deal_value" in df_clean.columns:
        # Note: keep NaN as NaN rather than 0.0 to track data quality issues (missing value)
        df_clean["deal_value"] = pd.to_numeric(df_clean["deal_value"], errors="coerce")
    else:
        df_clean["deal_value"] = np.nan
        
    # 5. Date Parse
    for col in ["actual_close_date", "tentative_close_date", "created_date"]:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(parse_date)
        else:
            df_clean[col] = None

    # 6. Map probabilities
    df_clean["raw_closure_probability"] = df_clean["closure_probability"] if "closure_probability" in df_clean.columns else None
    
    def calculate_prob(row):
        status = row.get("deal_status")
        prob_label = str(row.get("raw_closure_probability", "")).strip().lower() if pd.notna(row.get("raw_closure_probability")) else ""
        
        # Explicit status logic
        if status == "Won":
            return 1.0
        elif status == "Dead":
            return 0.0
            
        # Label logic
        if "high" in prob_label:
            return 0.8
        elif "medium" in prob_label:
            return 0.5
        elif "low" in prob_label:
            return 0.2
            
        # Default open fallback
        if status == "Open":
            return 0.3
        elif status == "On Hold":
            return 0.2
            
        return 0.0

    df_clean["calculated_probability"] = df_clean.apply(calculate_prob, axis=1)
    return df_clean

def normalize_work_orders(df: pd.DataFrame) -> pd.DataFrame:
    """Cleans and canonicalizes the mapped Work Orders DataFrame."""
    if df.empty:
        return df
        
    df_clean = df.copy()
    
    # 1. Text Normalizations
    str_cols = ["deal_name", "client_code", "serial_no", "nature_of_work", 
                "execution_status", "document_type", "bd_kam_code", "type_of_work", 
                "latest_invoice_no", "invoice_status", "wo_status_billed", 
                "collection_status", "billing_status"]
                
    for col in str_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(normalize_text)
            
    # 2. Sector Normalization
    if "sector" in df_clean.columns:
        df_clean["sector"] = df_clean["sector"].apply(normalize_sector)
    else:
        df_clean["sector"] = "Unknown"
        
    # 3. Numeric Parse
    num_cols = ["amount_excl_gst", "amount_incl_gst", "billed_value_excl_gst", 
                "billed_value_incl_gst", "collected_amount", "to_be_billed_excl_gst", 
                "to_be_billed_incl_gst", "amount_receivable"]
    for col in num_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(parse_number)
        else:
            df_clean[col] = 0.0
            
    # 4. Date Parse
    date_cols = ["data_delivery_date", "date_of_po_loi", "probable_start_date", 
                 "probable_end_date", "last_invoice_date", "collection_date"]
    for col in date_cols:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(parse_date)
        else:
            df_clean[col] = None
            
    return df_clean
