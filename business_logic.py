import pandas as pd
import numpy as np
import datetime
from typing import Dict, List, Any, Optional, Tuple

def get_quarter_dates(quarter: int, year: int) -> Tuple[datetime.date, datetime.date]:
    """Helper to get start and end dates for a calendar quarter."""
    if quarter == 1:
        return datetime.date(year, 1, 1), datetime.date(year, 3, 31)
    elif quarter == 2:
        return datetime.date(year, 4, 1), datetime.date(year, 6, 30)
    elif quarter == 3:
        return datetime.date(year, 7, 1), datetime.date(year, 9, 30)
    elif quarter == 4:
        return datetime.date(year, 10, 1), datetime.date(year, 12, 31)
    raise ValueError(f"Invalid quarter: {quarter}")

def parse_quarter_str(q_str: str) -> Optional[int]:
    """Parse common quarter representations like 'Q3', 'q3', '3' into an integer."""
    if not q_str:
        return None
    s = str(q_str).strip().lower().replace("q", "")
    try:
        q = int(s)
        if 1 <= q <= 4:
            return q
    except ValueError:
        pass
    return None

def filter_by_date_range(df: pd.DataFrame, date_col: str, quarter: Optional[int], year: Optional[int]) -> pd.DataFrame:
    """Filters a DataFrame by a quarter and year using a date column."""
    if df.empty or date_col not in df.columns:
        return df
        
    df_filtered = df.copy()
    dates = pd.to_datetime(df_filtered[date_col], errors="coerce")
    
    mask = pd.Series(True, index=df_filtered.index)
    if year is not None:
        mask = mask & (dates.dt.year == year)
        
    if quarter is not None:
        q_months = {
            1: [1, 2, 3],
            2: [4, 5, 6],
            3: [7, 8, 9],
            4: [10, 11, 12]
        }[quarter]
        mask = mask & (dates.dt.month.isin(q_months))
        
    return df_filtered[mask]

def get_pipeline_summary(df_deals: pd.DataFrame, sector: Optional[str] = None, quarter: Optional[int] = None, year: Optional[int] = None) -> Dict[str, Any]:
    """
    Calculates overall pipeline metrics for Open deals.
    Can be filtered by sector, quarter, and year (using tentative close date).
    """
    if df_deals.empty:
        return {"error": "No deal records available."}

    df_open = df_deals[df_deals["deal_status"] == "Open"].copy()
    
    # Apply filters
    if sector and sector.lower() != "all":
        df_open = df_open[df_open["sector"].str.lower() == sector.lower()]
        
    # For open deals, pipeline timing is based on tentative_close_date
    if quarter is not None or year is not None:
        df_open = filter_by_date_range(df_open, "tentative_close_date", quarter, year)

    # 1. Open Pipeline calculations
    total_open_value = df_open["deal_value"].sum()
    open_deal_count = len(df_open)
    weighted_pipeline = (df_open["deal_value"] * df_open["calculated_probability"]).sum()
    avg_deal_size = df_open["deal_value"].mean() if open_deal_count > 0 else 0.0
    
    # Details on deals with missing values
    missing_value_count = df_open["deal_value"].isna().sum()

    # 2. Stage breakdown for open pipeline
    stage_breakdown = {}
    if open_deal_count > 0:
        stage_group = df_open.groupby("deal_stage", dropna=False)
        for stage, group in stage_group:
            stage_name = str(stage) if pd.notna(stage) else "Unknown Stage"
            stage_breakdown[stage_name] = {
                "count": len(group),
                "total_value": group["deal_value"].sum(),
                "weighted_value": (group["deal_value"] * group["calculated_probability"]).sum()
            }

    # 3. Reference Won deals in same period/sector (for context)
    df_won = df_deals[df_deals["deal_status"] == "Won"].copy()
    if sector and sector.lower() != "all":
        df_won = df_won[df_won["sector"].str.lower() == sector.lower()]
    # Won deals timing is based on actual_close_date
    if quarter is not None or year is not None:
        df_won = filter_by_date_range(df_won, "actual_close_date", quarter, year)
        
    total_won_value = df_won["deal_value"].sum()
    won_count = len(df_won)
    won_missing_value = df_won["deal_value"].isna().sum()

    return {
        "sector_filter": sector or "All",
        "quarter_filter": quarter,
        "year_filter": year,
        "open_deals": {
            "total_value": total_open_value,
            "count": open_deal_count,
            "weighted_value": weighted_pipeline,
            "average_size": avg_deal_size,
            "missing_values_count": missing_value_count,
            "stage_breakdown": stage_breakdown
        },
        "won_deals": {
            "total_value": total_won_value,
            "count": won_count,
            "missing_values_count": won_missing_value
        }
    }

def get_pipeline_by_sector(df_deals: pd.DataFrame) -> List[Dict[str, Any]]:
    """Group open deals by sector and calculate metrics."""
    df_open = df_deals[df_deals["deal_status"] == "Open"]
    if df_open.empty:
        return []
        
    group = df_open.groupby("sector", dropna=False)
    sector_list = []
    for sector, grp in group:
        sector_name = str(sector) if pd.notna(sector) else "Unknown"
        sector_list.append({
            "sector": sector_name,
            "deal_count": len(grp),
            "total_value": grp["deal_value"].sum(),
            "weighted_value": (grp["deal_value"] * grp["calculated_probability"]).sum(),
            "avg_deal_size": grp["deal_value"].mean(),
            "missing_value_count": grp["deal_value"].isna().sum()
        })
        
    # Sort by total value descending
    sector_list.sort(key=lambda x: x["total_value"], reverse=True)
    return sector_list

def get_pipeline_by_stage(df_deals: pd.DataFrame) -> List[Dict[str, Any]]:
    """Group open deals by stage and calculate metrics."""
    df_open = df_deals[df_deals["deal_status"] == "Open"]
    if df_open.empty:
        return []
        
    group = df_open.groupby("deal_stage", dropna=False)
    stage_list = []
    for stage, grp in group:
        stage_name = str(stage) if pd.notna(stage) else "Unknown"
        stage_list.append({
            "stage": stage_name,
            "deal_count": len(grp),
            "total_value": grp["deal_value"].sum(),
            "weighted_value": (grp["deal_value"] * grp["calculated_probability"]).sum(),
        })
        
    # Sort stages alphabetically or logically if stage name has prefixes like 'A.', 'B.'
    stage_list.sort(key=lambda x: x["stage"])
    return stage_list

def get_top_deals(df_deals: pd.DataFrame, limit: int = 5) -> List[Dict[str, Any]]:
    """Get top N open deals sorted by deal value descending."""
    df_open = df_deals[df_deals["deal_status"] == "Open"].copy()
    if df_open.empty:
        return []
        
    df_sorted = df_open.sort_values(by="deal_value", ascending=False).head(limit)
    
    top_deals = []
    for _, row in df_sorted.iterrows():
        top_deals.append({
            "deal_name": row["deal_name"],
            "client_code": row["client_code"] if pd.notna(row["client_code"]) else "N/A",
            "deal_value": row["deal_value"],
            "probability": row["calculated_probability"],
            "raw_probability_label": row["raw_closure_probability"] if pd.notna(row["raw_closure_probability"]) else "N/A",
            "sector": row["sector"],
            "deal_stage": row["deal_stage"] if pd.notna(row["deal_stage"]) else "Unknown",
            "tentative_close_date": str(row["tentative_close_date"]) if row["tentative_close_date"] else "N/A"
        })
    return top_deals

def get_high_probability_deals(df_deals: pd.DataFrame) -> List[Dict[str, Any]]:
    """Get open deals with probability >= 80% (High probability)."""
    df_open = df_deals[df_deals["deal_status"] == "Open"].copy()
    if df_open.empty:
        return []
        
    df_high = df_open[df_open["calculated_probability"] >= 0.8]
    df_sorted = df_high.sort_values(by="deal_value", ascending=False)
    
    deals = []
    for _, row in df_sorted.iterrows():
        deals.append({
            "deal_name": row["deal_name"],
            "client_code": row["client_code"] if pd.notna(row["client_code"]) else "N/A",
            "deal_value": row["deal_value"],
            "probability": row["calculated_probability"],
            "sector": row["sector"],
            "tentative_close_date": str(row["tentative_close_date"]) if row["tentative_close_date"] else "N/A"
        })
    return deals

def get_delayed_work_orders(df_wo: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Identifies delayed work orders based on status values and dates.
    A work order is delayed if:
    1. Execution status is 'Pause / struck' or 'Details pending from Client' or 'Update Required'
    2. Billing or Invoice status is 'Stuck' or 'Update Required'
    3. The probable end date is in the past (today is compared against) and status is not 'Completed'
    """
    if df_wo.empty:
        return []
        
    today = datetime.date.today()
    delayed = []
    
    for _, row in df_wo.iterrows():
        is_delayed = False
        reasons = []
        
        exec_status = str(row.get("execution_status", "")).strip()
        bill_status = str(row.get("billing_status", "")).strip()
        inv_status = str(row.get("invoice_status", "")).strip()
        end_date = row.get("probable_end_date")
        
        # Check 1: Execution Status
        if exec_status in ["Pause / struck", "Details pending from Client", "Update Required"]:
            is_delayed = True
            reasons.append(f"Execution is '{exec_status}'")
            
        # Check 2: Billing / Invoice Status
        if bill_status in ["Stuck", "Update Required"] or inv_status in ["Stuck", "Update Required"]:
            is_delayed = True
            reasons.append(f"Billing status is '{bill_status or inv_status}'")
            
        # Check 3: Overdue probable end date
        if end_date and end_date < today and exec_status != "Completed":
            is_delayed = True
            reasons.append(f"Overdue: Target end date was {end_date} (today is {today})")
            
        if is_delayed:
            delayed.append({
                "deal_name": row["deal_name"] if pd.notna(row["deal_name"]) else "Unknown",
                "client_code": row["client_code"] if pd.notna(row["client_code"]) else "Unknown",
                "serial_no": row["serial_no"] if pd.notna(row["serial_no"]) else "N/A",
                "nature_of_work": row["nature_of_work"] if pd.notna(row["nature_of_work"]) else "N/A",
                "execution_status": exec_status if pd.notna(row["execution_status"]) else "N/A",
                "billing_status": bill_status if pd.notna(row["billing_status"]) else "N/A",
                "probable_end_date": str(end_date) if end_date else "N/A",
                "amount_excl_gst": row["amount_excl_gst"],
                "collected_amount": row["collected_amount"],
                "amount_receivable": row["amount_receivable"],
                "reasons": ", ".join(reasons)
            })
            
    # Sort by amount receivable descending
    delayed.sort(key=lambda x: x["amount_receivable"], reverse=True)
    return delayed

def get_operational_summary(df_wo: pd.DataFrame) -> Dict[str, Any]:
    """Calculates summary statistics for Work Order execution and billing."""
    if df_wo.empty:
        return {"error": "No work order records available."}
        
    total_wo = len(df_wo)
    
    # Execution breakdown
    exec_counts = df_wo["execution_status"].value_counts(dropna=False).to_dict()
    exec_summary = {str(k): int(v) for k, v in exec_counts.items()}
    
    # Billing Status breakdown
    billing_counts = df_wo["billing_status"].value_counts(dropna=False).to_dict()
    billing_summary = {str(k): int(v) for k, v in billing_counts.items()}
    
    # Financial metrics from Work Orders
    total_amount_excl_gst = df_wo["amount_excl_gst"].sum()
    total_amount_incl_gst = df_wo["amount_incl_gst"].sum()
    total_billed = df_wo["billed_value_excl_gst"].sum()
    total_collected = df_wo["collected_amount"].sum()
    total_receivable = df_wo["amount_receivable"].sum()
    
    # Delayed orders count
    delayed_list = get_delayed_work_orders(df_wo)
    delayed_count = len(delayed_list)
    delayed_receivable = sum(item["amount_receivable"] for item in delayed_list)
    
    return {
        "total_work_orders": total_wo,
        "execution_status_breakdown": exec_summary,
        "billing_status_breakdown": billing_summary,
        "financials": {
            "total_contract_value_excl_gst": total_amount_excl_gst,
            "total_contract_value_incl_gst": total_amount_incl_gst,
            "total_billed_value": total_billed,
            "total_collected_value": total_collected,
            "total_amount_receivable": total_receivable
        },
        "delayed_work_orders": {
            "count": delayed_count,
            "total_receivable": delayed_receivable
        }
    }

def get_revenue_summary(df_deals: pd.DataFrame, df_wo: pd.DataFrame) -> Dict[str, Any]:
    """Provides a consolidated view of Won deals value and work order billings/collections."""
    df_won = df_deals[df_deals["deal_status"] == "Won"]
    won_count = len(df_won)
    won_deal_value = df_won["deal_value"].sum()
    won_missing_value = df_won["deal_value"].isna().sum()
    
    total_contract_value = df_wo["amount_excl_gst"].sum()
    total_billed = df_wo["billed_value_excl_gst"].sum()
    total_collected = df_wo["collected_amount"].sum()
    total_receivable = df_wo["amount_receivable"].sum()
    
    return {
        "deals_won_count": won_count,
        "deals_won_total_value": won_deal_value,
        "deals_won_missing_value_count": won_missing_value,
        "work_orders_total_contract_value": total_contract_value,
        "work_orders_total_billed": total_billed,
        "work_orders_total_collected": total_collected,
        "work_orders_total_receivable": total_receivable,
        "unbilled_contract_value": max(0.0, total_contract_value - total_billed),
        "collection_rate_of_billed": (total_collected / total_billed * 100) if total_billed > 0 else 0.0,
        "collection_rate_of_total": (total_collected / total_contract_value * 100) if total_contract_value > 0 else 0.0
    }

def get_cross_board_sector_performance(df_deals: pd.DataFrame, df_wo: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Joins Deals and Work Orders to compare booking performance vs delivery execution/collections by sector.
    """
    if df_deals.empty or df_wo.empty:
        return []
        
    # Join on deal name (case-insensitive, trimmed)
    df_d = df_deals.copy()
    df_d["join_key"] = df_d["deal_name"].apply(lambda x: str(x).strip().lower() if pd.notna(x) else "")
    
    df_w = df_wo.copy()
    df_w["join_key"] = df_w["deal_name"].apply(lambda x: str(x).strip().lower() if pd.notna(x) else "")
    
    # Left join to capture all work orders mapped to deal info
    merged = pd.merge(df_w, df_d, on="join_key", how="left", suffixes=("_wo", "_deal"))
    
    # We use Deals sector as the canonical sector since it governs pipeline
    merged["sector_canonical"] = merged["sector_deal"].fillna(merged["sector_wo"])
    
    sector_perf = []
    group = merged.groupby("sector_canonical", dropna=False)
    for sector, grp in group:
        sector_name = str(sector) if pd.notna(sector) else "Unknown"
        
        # Booking metrics (from Deals for this sector)
        deals_in_sector = df_deals[df_deals["sector"] == sector_name]
        won_deals = deals_in_sector[deals_in_sector["deal_status"] == "Won"]
        open_deals = deals_in_sector[deals_in_sector["deal_status"] == "Open"]
        
        won_value = won_deals["deal_value"].sum()
        open_pipeline = open_deals["deal_value"].sum()
        weighted_pipeline = (open_deals["deal_value"] * open_deals["calculated_probability"]).sum()
        
        # Delivery & Collection metrics (from Work Orders joined to this sector)
        contract_value = grp["amount_excl_gst"].sum()
        billed_value = grp["billed_value_excl_gst"].sum()
        collected_value = grp["collected_amount"].sum()
        receivable_value = grp["amount_receivable"].sum()
        
        wo_count = len(grp)
        completed_wo = len(grp[grp["execution_status"] == "Completed"])
        ongoing_wo = len(grp[grp["execution_status"] == "Ongoing"])
        stuck_wo = len(grp[grp["execution_status"].isin(["Pause / struck", "Details pending from Client"])])
        
        sector_perf.append({
            "sector": sector_name,
            "won_deals_count": len(won_deals),
            "won_deals_value": won_value,
            "open_pipeline_value": open_pipeline,
            "weighted_pipeline_value": weighted_pipeline,
            "work_orders_count": wo_count,
            "completed_work_orders": completed_wo,
            "ongoing_work_orders": ongoing_wo,
            "stuck_work_orders": stuck_wo,
            "wo_contract_value": contract_value,
            "wo_billed_value": billed_value,
            "wo_collected_value": collected_value,
            "wo_receivable_value": receivable_value,
            "collection_rate_of_billed": (collected_value / billed_value * 100) if billed_value > 0 else 0.0,
            "collection_rate_of_contract": (collected_value / contract_value * 100) if contract_value > 0 else 0.0
        })
        
    sector_perf.sort(key=lambda x: x["won_deals_value"] + x["open_pipeline_value"], reverse=True)
    return sector_perf

def generate_data_quality_report(df_deals: pd.DataFrame, df_wo: pd.DataFrame) -> Dict[str, Any]:
    """Generates a structured, statistical data-quality report."""
    if df_deals.empty:
        return {"error": "Deals dataframe is empty."}
        
    total_deals = len(df_deals)
    
    # Deals issues
    deals_missing_sector = int((df_deals["sector"] == "Unknown").sum())
    deals_missing_value_total = int(df_deals["deal_value"].isna().sum())
    deals_missing_value_won = int(df_deals[df_deals["deal_status"] == "Won"]["deal_value"].isna().sum())
    deals_missing_value_open = int(df_deals[df_deals["deal_status"] == "Open"]["deal_value"].isna().sum())
    deals_missing_actual_close_won = int(df_deals[df_deals["deal_status"] == "Won"]["actual_close_date"].isna().sum())
    deals_missing_tentative_close_open = int(df_deals[df_deals["deal_status"] == "Open"]["tentative_close_date"].isna().sum())
    
    # Work Orders issues
    total_wo = len(df_wo)
    wo_empty_collection_dates = int(df_wo["collection_date"].isna().sum())
    wo_missing_execution_status = int((df_wo["execution_status"] == "Unknown").sum())
    
    # Match analysis
    deals_names_lower = set(df_deals["deal_name"].dropna().apply(lambda x: str(x).strip().lower()).unique())
    wo_unmatched = []
    for _, row in df_wo.iterrows():
        wo_name = row.get("deal_name")
        if pd.notna(wo_name):
            wo_name_clean = str(wo_name).strip().lower()
            if wo_name_clean not in deals_names_lower:
                wo_unmatched.append(str(wo_name))
                
    return {
        "deals_board": {
            "total_records": total_deals,
            "missing_sector": deals_missing_sector,
            "total_missing_values": deals_missing_value_total,
            "won_deals_missing_values": deals_missing_value_won,
            "open_deals_missing_values": deals_missing_value_open,
            "won_deals_missing_actual_close_date": deals_missing_actual_close_won,
            "open_deals_missing_tentative_close_date": deals_missing_tentative_close_open
        },
        "work_orders_board": {
            "total_records": total_wo,
            "empty_collection_dates": wo_empty_collection_dates,
            "missing_execution_status": wo_missing_execution_status,
            "unmatched_work_orders_count": len(wo_unmatched),
            "unmatched_work_orders_names": wo_unmatched
        }
    }
