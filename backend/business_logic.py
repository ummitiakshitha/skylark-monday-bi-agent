import pandas as pd
import numpy as np
import datetime
from typing import Dict, List, Any, Optional

def _filter_by_quarter(df: pd.DataFrame, date_col: str, quarter: Optional[int], year: Optional[int]) -> pd.DataFrame:
    """Helper to filter a DataFrame by calendar quarter and year on a date column."""
    if df.empty or not date_col or (quarter is None and year is None):
        return df
        
    mask = pd.Series(True, index=df.index)
    
    # Extract year and quarter using pandas datetime conversion or attribute access
    dates = pd.to_datetime(df[date_col], errors="coerce")
    
    if year is not None:
        mask = mask & (dates.dt.year == year)
        
    if quarter is not None:
        # Q1: 1, 2, 3; Q2: 4, 5, 6; Q3: 7, 8, 9; Q4: 10, 11, 12
        mask = mask & (dates.dt.quarter == quarter)
        
    return df[mask]

def get_pipeline_summary(df_deals: pd.DataFrame, sector: Optional[str] = None, quarter: Optional[int] = None, year: Optional[int] = None) -> Dict[str, Any]:
    """
    Computes overall open pipeline, average, and weighted pipeline metrics.
    Optionally filters by sector, and expected close quarter/year.
    """
    if df_deals.empty:
        return {
            "open_deals": {"count": 0, "total_value": 0.0, "average_size": 0.0, "weighted_value": 0.0, "missing_values_count": 0},
            "won_deals": {"count": 0, "total_value": 0.0, "average_size": 0.0, "missing_values_count": 0}
        }
        
    df = df_deals.copy()
    if sector and sector != "Unknown":
        df = df[df["sector"].str.lower() == sector.lower()]
        
    # Open deals pipeline calculations (use tentative close date for timing)
    df_open = df[df["deal_status"] == "Open"]
    if quarter or year:
        df_open = _filter_by_quarter(df_open, "tentative_close_date", quarter, year)
        
    open_count = len(df_open)
    open_missing_val = int(df_open["deal_value"].isna().sum())
    open_vals = df_open["deal_value"].dropna()
    open_total = float(open_vals.sum())
    open_avg = float(open_vals.mean()) if not open_vals.empty else 0.0
    
    # Weighted open pipeline
    weighted_val = float((df_open["deal_value"].fillna(0.0) * df_open["calculated_probability"]).sum())
    
    # Closed won deals calculations (use actual close date for timing)
    df_won = df[df["deal_status"] == "Won"]
    if quarter or year:
        df_won = _filter_by_quarter(df_won, "actual_close_date", quarter, year)
        
    won_count = len(df_won)
    won_missing_val = int(df_won["deal_value"].isna().sum())
    won_vals = df_won["deal_value"].dropna()
    won_total = float(won_vals.sum())
    won_avg = float(won_vals.mean()) if not won_vals.empty else 0.0
    
    return {
        "open_deals": {
            "count": open_count,
            "total_value": open_total,
            "average_size": open_avg,
            "weighted_value": weighted_val,
            "missing_values_count": open_missing_val
        },
        "won_deals": {
            "count": won_count,
            "total_value": won_total,
            "average_size": won_avg,
            "missing_values_count": won_missing_val
        }
    }

def get_pipeline_by_sector(df_deals: pd.DataFrame) -> List[Dict[str, Any]]:
    """Groups open pipeline metrics by sector, sorted by total value descending."""
    if df_deals.empty:
        return []
        
    df_open = df_deals[df_deals["deal_status"] == "Open"].copy()
    df_open["weighted_deal_value"] = df_open["deal_value"].fillna(0.0) * df_open["calculated_probability"]
    
    # Exclude rows where sector is empty/na
    df_open["sector"] = df_open["sector"].fillna("Unknown")
    
    grouped = df_open.groupby("sector").agg(
        deal_count=("deal_name", "count"),
        total_value=("deal_value", "sum"),
        weighted_value=("weighted_deal_value", "sum"),
        missing_value_count=("deal_value", lambda x: int(x.isna().sum()))
    ).reset_index()
    
    grouped = grouped.sort_values(by="total_value", ascending=False)
    
    # Cast numpy types to python native types
    results = []
    for _, row in grouped.iterrows():
        results.append({
            "sector": str(row["sector"]),
            "deal_count": int(row["deal_count"]),
            "total_value": float(row["total_value"]),
            "weighted_value": float(row["weighted_value"]),
            "missing_value_count": int(row["missing_value_count"])
        })
    return results

def get_pipeline_by_stage(df_deals: pd.DataFrame) -> List[Dict[str, Any]]:
    """Groups open pipeline counts and values by deal stage, sorted descending."""
    if df_deals.empty:
        return []
        
    df_open = df_deals[df_deals["deal_status"] == "Open"].copy()
    df_open["deal_stage"] = df_open["deal_stage"].fillna("Unknown Stage")
    
    grouped = df_open.groupby("deal_stage").agg(
        deal_count=("deal_name", "count"),
        total_value=("deal_value", "sum")
    ).reset_index().sort_values(by="total_value", ascending=False)
    
    results = []
    for _, row in grouped.iterrows():
        results.append({
            "stage": str(row["deal_stage"]),
            "deal_count": int(row["deal_count"]),
            "total_value": float(row["total_value"])
        })
    return results

def get_top_deals(df_deals: pd.DataFrame, limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieves top open deals sorted by value descending."""
    if df_deals.empty:
        return []
        
    df_open = df_deals[df_deals["deal_status"] == "Open"].copy()
    df_top = df_open.sort_values(by="deal_value", ascending=False).head(limit)
    
    results = []
    for _, row in df_top.iterrows():
        results.append({
            "deal_name": str(row["deal_name"]),
            "client_code": str(row["client_code"]) if pd.notna(row["client_code"]) else "Unknown",
            "deal_value": float(row["deal_value"]) if pd.notna(row["deal_value"]) else 0.0,
            "probability": float(row["calculated_probability"]),
            "sector": str(row["sector"]),
            "tentative_close_date": str(row["tentative_close_date"]) if row["tentative_close_date"] else "Unknown"
        })
    return results

def get_high_probability_deals(df_deals: pd.DataFrame) -> List[Dict[str, Any]]:
    """Gets open deals with a closure probability of 80% or above."""
    if df_deals.empty:
        return []
        
    df_high = df_deals[(df_deals["deal_status"] == "Open") & (df_deals["calculated_probability"] >= 0.8)]
    df_sorted = df_high.sort_values(by="deal_value", ascending=False)
    
    results = []
    for _, row in df_sorted.iterrows():
        results.append({
            "deal_name": str(row["deal_name"]),
            "client_code": str(row["client_code"]) if pd.notna(row["client_code"]) else "Unknown",
            "deal_value": float(row["deal_value"]) if pd.notna(row["deal_value"]) else 0.0,
            "probability": float(row["calculated_probability"]),
            "tentative_close_date": str(row["tentative_close_date"]) if row["tentative_close_date"] else "Unknown"
        })
    return results

def get_delayed_work_orders(df_wo: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Identifies work orders whose target execution date is in the past, or are paused/struck, 
    and are not completed.
    """
    if df_wo.empty:
        return []
        
    df = df_wo.copy()
    today = datetime.date.today()
    
    # Delayed active work order criteria:
    # 1. Not Completed
    # 2. Execution status is delayed-prone (Ongoing, Pause / struck, Details pending, etc.)
    # 3. Probable end date is in the past OR status indicates stalled/paused
    
    non_completed_mask = df["execution_status"].str.lower() != "completed"
    
    # Helper to check if date is in past
    def is_date_overdue(end_date):
        if not end_date:
            return False
        # Dates are datetime.date objects. Compare with current date.
        return end_date < today
        
    overdue_mask = df["probable_end_date"].apply(is_date_overdue)
    stalled_mask = df["execution_status"].str.lower().isin(["pause / struck", "details pending from client"])
    
    df_delayed = df[non_completed_mask & (overdue_mask | stalled_mask)]
    
    results = []
    for _, row in df_delayed.iterrows():
        reasons = []
        if is_date_overdue(row["probable_end_date"]):
            reasons.append(f"Target date overdue ({row['probable_end_date']})")
        if row["execution_status"] in ["Pause / struck", "Details pending from Client"]:
            reasons.append(f"Status is {row['execution_status']}")
            
        results.append({
            "deal_name": str(row["deal_name"]),
            "client_code": str(row["client_code"]) if pd.notna(row["client_code"]) else "Unknown",
            "execution_status": str(row["execution_status"]),
            "probable_end_date": str(row["probable_end_date"]) if row["probable_end_date"] else "None",
            "amount_receivable": float(row["amount_receivable"]) if pd.notna(row["amount_receivable"]) else 0.0,
            "reasons": ", ".join(reasons)
        })
        
    return results

def get_operational_summary(df_wo: pd.DataFrame) -> Dict[str, Any]:
    """Returns general operational summaries, billed values, collected amounts, and delayed counts."""
    if df_wo.empty:
        return {
            "total_work_orders": 0,
            "execution_status_breakdown": {},
            "financials": {"total_contract_value_excl_gst": 0.0, "total_billed_value": 0.0, "total_collected_value": 0.0, "total_receivable": 0.0},
            "delayed_work_orders": {"count": 0, "total_receivable": 0.0}
        }
        
    total_wo = len(df_wo)
    status_breakdown = df_wo["execution_status"].fillna("Unknown").value_counts().to_dict()
    
    # Financial metrics
    contract_val = float(df_wo["amount_excl_gst"].sum())
    billed_val = float(df_wo["billed_value_excl_gst"].sum())
    collected_val = float(df_wo["collected_amount"].sum())
    receivable_val = float(df_wo["amount_receivable"].sum())
    
    # Delayed work orders stats
    delayed_items = get_delayed_work_orders(df_wo)
    delayed_count = len(delayed_items)
    delayed_receivables = sum(item["amount_receivable"] for item in delayed_items)
    
    return {
        "total_work_orders": total_wo,
        "execution_status_breakdown": status_breakdown,
        "financials": {
            "total_contract_value_excl_gst": contract_val,
            "total_billed_value": billed_val,
            "total_collected_value": collected_val,
            "total_receivable": receivable_val
        },
        "delayed_work_orders": {
            "count": delayed_count,
            "total_receivable": delayed_receivables
        }
    }

def get_revenue_summary(df_deals: pd.DataFrame, df_wo: pd.DataFrame) -> Dict[str, Any]:
    """Compares Sales closed won values against operations billed and collected values."""
    won_bookings = float(df_deals[df_deals["deal_status"] == "Won"]["deal_value"].sum())
    billed_val = float(df_wo["billed_value_excl_gst"].sum())
    collected_val = float(df_wo["collected_amount"].sum())
    receivable_val = float(df_wo["amount_receivable"].sum())
    
    return {
        "won_bookings_value": won_bookings,
        "billed_value_excl_gst": billed_val,
        "collected_amount_incl_gst": collected_val,
        "amount_receivable": receivable_val
    }

def get_cross_board_sector_performance(df_deals: pd.DataFrame, df_wo: pd.DataFrame) -> List[Dict[str, Any]]:
    """Analyzes bookings, billed values, and collection rates at the sector level."""
    if df_deals.empty or df_wo.empty:
        return []
        
    # 1. Group Won deals value by sector
    df_won = df_deals[df_deals["deal_status"] == "Won"].copy()
    df_won["sector"] = df_won["sector"].fillna("Unknown")
    grouped_deals = df_won.groupby("sector")["deal_value"].sum().reset_index()
    grouped_deals.rename(columns={"deal_value": "won_deals_value"}, inplace=True)
    
    # 2. Group Work Orders financials by sector
    df_wo_copy = df_wo.copy()
    df_wo_copy["sector"] = df_wo_copy["sector"].fillna("Unknown")
    grouped_wo = df_wo_copy.groupby("sector").agg(
        wo_contract_value=("amount_excl_gst", "sum"),
        wo_billed_value=("billed_value_excl_gst", "sum"),
        wo_collected_value=("collected_amount", "sum"),
        wo_receivable_value=("amount_receivable", "sum")
    ).reset_index()
    
    # 3. Outer Join on Sector
    merged = pd.merge(grouped_deals, grouped_wo, on="sector", how="outer").fillna(0.0)
    
    results = []
    for _, row in merged.iterrows():
        billed = row["wo_billed_value"]
        collected = row["wo_collected_value"]
        won_value = row["won_deals_value"]
        
        collection_rate_billed = (collected / billed) * 100.0 if billed > 0.0 else 0.0
        collection_rate_won = (collected / won_value) * 100.0 if won_value > 0.0 else 0.0
        
        results.append({
            "sector": str(row["sector"]),
            "won_deals_value": float(won_value),
            "wo_contract_value": float(row["wo_contract_value"]),
            "wo_billed_value": float(billed),
            "wo_collected_value": float(collected),
            "wo_receivable_value": float(row["wo_receivable_value"]),
            "collection_rate_of_billed": float(collection_rate_billed),
            "collection_rate_of_bookings": float(collection_rate_won)
        })
        
    # Sort descending by bookings value
    results = sorted(results, key=lambda x: x["won_deals_value"], reverse=True)
    return results

def generate_data_quality_report(df_deals: pd.DataFrame, df_wo: pd.DataFrame) -> Dict[str, Any]:
    """Generates a structured data-quality health report from the cleaned DataFrames."""
    # Deals Board metrics
    total_deals = len(df_deals)
    missing_deals_val = int(df_deals["deal_value"].isna().sum()) if "deal_value" in df_deals.columns else total_deals
    missing_close_dates = int(df_deals["actual_close_date"].isna().sum()) if "actual_close_date" in df_deals.columns else total_deals
    missing_tentative_dates = int(df_deals["tentative_close_date"].isna().sum()) if "tentative_close_date" in df_deals.columns else total_deals
    missing_sectors = int((df_deals["sector"] == "Unknown").sum()) if "sector" in df_deals.columns else total_deals
    won_deals_missing_val = int(df_deals[df_deals["deal_status"] == "Won"]["deal_value"].isna().sum()) if "deal_status" in df_deals.columns and "deal_value" in df_deals.columns else 0
    open_deals_missing_val = int(df_deals[df_deals["deal_status"] == "Open"]["deal_value"].isna().sum()) if "deal_status" in df_deals.columns and "deal_value" in df_deals.columns else 0
    
    # Work Orders Board metrics
    total_wo = len(df_wo)
    empty_collection_dates = int(df_wo["collection_date"].isna().sum()) if "collection_date" in df_wo.columns else total_wo
    empty_delivery_dates = int(df_wo["data_delivery_date"].isna().sum()) if "data_delivery_date" in df_wo.columns else total_wo
    
    # Join analysis match percentages
    if total_wo > 0:
        deals_names_set = set(df_deals["deal_name"].dropna().str.strip().str.lower().unique())
        wo_names = df_wo["deal_name"].dropna().str.strip().str.lower()
        
        matched_wo_mask = wo_names.apply(lambda x: x in deals_names_set)
        matched_wo_count = int(matched_wo_mask.sum())
        unmatched_wo_count = total_wo - matched_wo_count
        match_percentage = (matched_wo_count / total_wo) * 100.0
    else:
        matched_wo_count = 0
        unmatched_wo_count = 0
        match_percentage = 0.0
        
    return {
        "deals_board": {
            "total_records": total_deals,
            "missing_sector": missing_sectors,
            "total_missing_values": missing_deals_val,
            "won_deals_missing_values": won_deals_missing_val,
            "open_deals_missing_values": open_deals_missing_val,
            "missing_close_dates_actual": missing_close_dates,
            "missing_close_dates_tentative": missing_tentative_dates
        },
        "work_orders_board": {
            "total_records": total_wo,
            "empty_collection_dates": empty_collection_dates,
            "empty_delivery_dates": empty_delivery_dates,
            "matched_work_orders_count": matched_wo_count,
            "unmatched_work_orders_count": unmatched_wo_count,
            "match_percentage_deals": match_percentage
        }
    }
