import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Any, Tuple

logger = logging.getLogger(__name__)

# Lowercase mapping keys to canonical column names
DEALS_SCHEMA_MAP = {
    "deal name": "deal_name",
    "item name": "deal_name",
    "owner code": "owner_code",
    "client code": "client_code",
    "deal status": "deal_status",
    "close date (a)": "actual_close_date",
    "closure probability": "closure_probability",
    "masked deal value": "deal_value",
    "tentative close date": "tentative_close_date",
    "deal stage": "deal_stage",
    "product deal": "product_type",
    "sector/service": "sector",
    "created date": "created_date"
}

WO_SCHEMA_MAP = {
    "deal name masked": "deal_name",
    "item name": "deal_name",
    "customer name code": "client_code",
    "serial #": "serial_no",
    "nature of work": "nature_of_work",
    "last executed month of recurring project": "last_executed_month",
    "execution status": "execution_status",
    "data delivery date": "data_delivery_date",
    "date of po/loi": "date_of_po_loi",
    "document type": "document_type",
    "probable start date": "probable_start_date",
    "probable end date": "probable_end_date",
    "bd/kam personnel code": "bd_kam_code",
    "sector": "sector",
    "type of work": "type_of_work",
    "is any skylark software platform part of the client deliverables in this deal?": "has_skylark_software",
    "last invoice date": "last_invoice_date",
    "latest invoice no.": "latest_invoice_no",
    "amount in rupees (excl of gst) (masked)": "amount_excl_gst",
    "amount in rupees (incl of gst) (masked)": "amount_incl_gst",
    "billed value in rupees (excl of gst.) (masked)": "billed_value_excl_gst",
    "billed value in rupees (incl of gst.) (masked)": "billed_value_incl_gst",
    "collected amount in rupees (incl of gst.) (masked)": "collected_amount",
    "amount to be billed in rs. (exl. of gst) (masked)": "to_be_billed_excl_gst",
    "amount to be billed in rs. (incl. of gst) (masked)": "to_be_billed_incl_gst",
    "amount receivable (masked)": "amount_receivable",
    "ar priority account": "ar_priority",
    "quantity by ops": "quantity_ops",
    "quantities as per po": "quantity_po",
    "quantity billed (till date)": "quantity_billed",
    "balance in quantity": "quantity_balance",
    "invoice status": "invoice_status",
    "expected billing month": "expected_billing_month",
    "actual billing month": "actual_billing_month",
    "actual collection month": "actual_collection_month",
    "wo status (billed)": "wo_status_billed",
    "collection status": "collection_status",
    "collection date": "collection_date",
    "billing status": "billing_status"
}

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

def normalize_sector(val: Any) -> str:
    """Normalize sector strings to a standard list."""
    if pd.isna(val) or not str(val).strip():
        return "Unknown"
    s = str(val).strip().lower()
    if s in SECTOR_NORMALIZATION_MAP:
        return SECTOR_NORMALIZATION_MAP[s]
    return s.title()

def normalize_status(val: Any) -> str:
    """Standardize status field values by trimming whitespace."""
    if pd.isna(val):
        return "Unknown"
    return str(val).strip()

def clean_deals_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and canonicalize the Deals dataframe.
    """
    if df.empty:
        return df

    # 1. Rename columns based on lowercase map
    rename_dict = {}
    for col in df.columns:
        norm_col = str(col).strip().lower()
        if norm_col in DEALS_SCHEMA_MAP:
            rename_dict[col] = DEALS_SCHEMA_MAP[norm_col]
            
    df_clean = df.rename(columns=rename_dict)

    # Make sure we have all canonical columns, adding missing ones as NaN
    for canonical_col in DEALS_SCHEMA_MAP.values():
        if canonical_col not in df_clean.columns:
            df_clean[canonical_col] = np.nan

    # 2. Filter out garbage header duplication rows (e.g. Nezuko / Bugs Bunny duplicate rows)
    # We can detect this if deal_status is literally 'Deal Status' or deal_stage is 'Deal Stage'
    df_clean = df_clean[df_clean["deal_status"] != "Deal Status"]
    df_clean = df_clean[df_clean["deal_stage"] != "Deal Stage"]

    # 3. Trim string columns
    for col in ["deal_name", "owner_code", "client_code", "deal_status", "deal_stage", "product_type"]:
        df_clean[col] = df_clean[col].apply(lambda x: str(x).strip() if pd.notna(x) else np.nan)

    # 4. Standardize sector
    df_clean["sector"] = df_clean["sector"].apply(normalize_sector)
    
    # 5. Standardize status
    df_clean["deal_status"] = df_clean["deal_status"].apply(normalize_status)

    # 6. Parse numeric columns
    df_clean["deal_value"] = pd.to_numeric(df_clean["deal_value"], errors="coerce")

    # 7. Parse date columns to datetime.date (None if NaT)
    for col in ["actual_close_date", "tentative_close_date", "created_date"]:
        df_clean[col] = pd.to_datetime(df_clean[col], errors="coerce").dt.date
        df_clean[col] = df_clean[col].apply(lambda x: x if pd.notna(x) else None)

    # 8. Standardize closure probability to float (e.g. High -> 0.8) and keep original raw label
    df_clean["raw_closure_probability"] = df_clean["closure_probability"]
    
    def parse_prob(val, status):
        # Implicit probabilities based on status
        if status == "Won":
            return 1.0
        elif status == "Dead":
            return 0.0
        
        # Explicit probabilities
        if pd.isna(val):
            return np.nan
        s = str(val).strip().lower()
        if "high" in s:
            return 0.8
        elif "medium" in s:
            return 0.5
        elif "low" in s:
            return 0.2
        return np.nan

    # Combine status and explicit probability to compute calculated probability
    df_clean["calculated_probability"] = df_clean.apply(
        lambda row: parse_prob(row["raw_closure_probability"], row["deal_status"]), axis=1
    )
    
    # Fill remaining NaNs for open deals with a default of 0.3
    df_clean.loc[df_clean["deal_status"] == "Open", "calculated_probability"] = \
        df_clean.loc[df_clean["deal_status"] == "Open", "calculated_probability"].fillna(0.3)
    df_clean.loc[df_clean["deal_status"] == "On Hold", "calculated_probability"] = \
        df_clean.loc[df_clean["deal_status"] == "On Hold", "calculated_probability"].fillna(0.2)
    # Remaining NaNs (e.g. status Unknown) defaults to 0.0
    df_clean["calculated_probability"] = df_clean["calculated_probability"].fillna(0.0)

    return df_clean

def clean_work_orders_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and canonicalize the Work Orders dataframe.
    """
    if df.empty:
        return df

    # 1. Rename columns based on lowercase map
    rename_dict = {}
    for col in df.columns:
        norm_col = str(col).strip().lower()
        if norm_col in WO_SCHEMA_MAP:
            rename_dict[col] = WO_SCHEMA_MAP[norm_col]
            
    df_clean = df.rename(columns=rename_dict)

    # Make sure we have all canonical columns, adding missing ones as NaN
    for canonical_col in WO_SCHEMA_MAP.values():
        if canonical_col not in df_clean.columns:
            df_clean[canonical_col] = np.nan

    # 2. Trim string columns
    str_cols = ["deal_name", "client_code", "serial_no", "nature_of_work", 
                "execution_status", "document_type", "bd_kam_code", "type_of_work", 
                "latest_invoice_no", "invoice_status", "wo_status_billed", 
                "collection_status", "billing_status"]
    
    for col in str_cols:
        df_clean[col] = df_clean[col].apply(lambda x: str(x).strip() if pd.notna(x) else np.nan)

    # 3. Standardize sector
    df_clean["sector"] = df_clean["sector"].apply(normalize_sector)
    
    # 4. Standardize execution status
    df_clean["execution_status"] = df_clean["execution_status"].apply(normalize_status)

    # 5. Parse numeric columns
    num_cols = ["amount_excl_gst", "amount_incl_gst", "billed_value_excl_gst", 
                "billed_value_incl_gst", "collected_amount", "to_be_billed_excl_gst", 
                "to_be_billed_incl_gst", "amount_receivable"]
    for col in num_cols:
        df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce").fillna(0.0)

    # 6. Parse date columns to datetime.date
    date_cols = ["data_delivery_date", "date_of_po_loi", "probable_start_date", 
                 "probable_end_date", "last_invoice_date", "collection_date"]
    for col in date_cols:
        df_clean[col] = pd.to_datetime(df_clean[col], errors="coerce").dt.date
        df_clean[col] = df_clean[col].apply(lambda x: x if pd.notna(x) else None)

    return df_clean

def load_and_clean_local_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Loads local Excel files and cleans them. (Useful for local testing).
    """
    deals_path = "d:\\skylarkdrones\\Deal funnel Data.xlsx"
    wo_path = "d:\\skylarkdrones\\Work_Order_Tracker Data.xlsx"
    
    df_deals_raw = pd.read_excel(deals_path)
    # The WO tracker Excel has header at row 1, so row 0 in df is the headers.
    df_wo_raw = pd.read_excel(wo_path, header=1)
    
    df_deals = clean_deals_df(df_deals_raw)
    df_wo = clean_work_orders_df(df_wo_raw)
    
    return df_deals, df_wo
