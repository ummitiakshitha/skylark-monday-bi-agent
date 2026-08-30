import pandas as pd
from typing import Dict, List, Any

# Canonical schemas mapping display headers to standardized internal fields
DEALS_CANONICAL_MAP = {
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

WO_CANONICAL_MAP = {
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

class SchemaMapper:
    """Discovers and maps Monday.com dynamic raw schemas to canonical fields."""
    
    @staticmethod
    def get_column_mapping(columns_metadata: List[Dict[str, str]], is_deals: bool) -> Dict[str, str]:
        """
        Builds a map from Monday.com column_id -> canonical_field_name.
        Unrecognized columns are ignored.
        """
        canonical_map = DEALS_CANONICAL_MAP if is_deals else WO_CANONICAL_MAP
        mapping = {}
        
        for col in columns_metadata:
            col_id = col.get("id")
            col_title = col.get("title")
            
            if not col_id or not col_title:
                continue
                
            # Normalize title to lower case for comparison
            normalized_title = str(col_title).strip().lower()
            if normalized_title in canonical_map:
                mapping[col_id] = canonical_map[normalized_title]
                
        return mapping

    @staticmethod
    def items_to_dataframe(items: List[Dict[str, Any]], column_mapping: Dict[str, str], is_deals: bool) -> pd.DataFrame:
        """
        Maps a list of raw Monday items into a Pandas DataFrame with canonical columns.
        """
        records = []
        canonical_fields = DEALS_CANONICAL_MAP.values() if is_deals else WO_CANONICAL_MAP.values()
        
        for item in items:
            record = {field: None for field in canonical_fields}
            
            # Map item ID and raw name
            record["item_id"] = item.get("id")
            
            # Monday primary column is item name. In our mapping, it maps to deal_name.
            record["deal_name"] = item.get("name")
            
            # Map the other column values
            for col_val in item.get("column_values", []):
                col_id = col_val.get("id")
                col_text = col_val.get("text")
                
                if col_id in column_mapping:
                    canonical_field = column_mapping[col_id]
                    record[canonical_field] = col_text
                    
            records.append(record)
            
        return pd.DataFrame(records)
