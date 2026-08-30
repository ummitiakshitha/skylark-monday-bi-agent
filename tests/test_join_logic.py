import unittest
import pandas as pd
from backend.business_logic import generate_data_quality_report

class TestJoinLogic(unittest.TestCase):
    def test_cross_board_join_match_rate(self):
        # Create deals with differing whitespaces and casing
        deals_data = {
            "deal_name": ["  Deal Alpha  ", "DEAL BETA", "deal gamma"],
            "deal_status": ["Open", "Open", "Won"],
            "deal_value": [100.0, 200.0, 300.0],
            "sector": ["Mining", "Mining", "Mining"],
            "actual_close_date": [None, None, None],
            "tentative_close_date": [None, None, None]
        }
        df_deals = pd.DataFrame(deals_data)

        # Create work orders matching these deals with messy casing/spaces
        wo_data = {
            "deal_name": ["deal alpha", "  DEAL BETA  ", "Deal Gamma", "Unmatched Deal"],
            "client_code": ["C1", "C2", "C3", "C4"],
            "execution_status": ["Ongoing", "Ongoing", "Completed", "Ongoing"],
            "amount_receivable": [50.0, 50.0, 0.0, 100.0],
            "collection_date": [None, None, None, None]
        }
        df_wo = pd.DataFrame(wo_data)

        # Perform the audit report match rate calculations
        report = generate_data_quality_report(df_deals, df_wo)
        wo_stats = report["work_orders_board"]
        
        # 3 out of 4 work orders should match back perfectly (alpha, beta, gamma)
        self.assertEqual(wo_stats["matched_work_orders_count"], 3)
        self.assertEqual(wo_stats["unmatched_work_orders_count"], 1)
        self.assertEqual(wo_stats["match_percentage_deals"], 75.0)
        self.assertEqual(wo_stats["total_records"], 4)
        
        # Check deals stats
        deals_stats = report["deals_board"]
        self.assertEqual(deals_stats["total_records"], 3)
