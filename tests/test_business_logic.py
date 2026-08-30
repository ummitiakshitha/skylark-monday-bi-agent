import unittest
import pandas as pd
import datetime
from backend.business_logic import (
    get_pipeline_summary, get_pipeline_by_sector, get_top_deals,
    get_high_probability_deals, get_delayed_work_orders, get_operational_summary
)

class TestBusinessLogic(unittest.TestCase):
    def setUp(self):
        # Create a mock cleaned Deals DataFrame
        deals_data = {
            "deal_name": ["Deal 1", "Deal 2", "Deal 3", "Deal 4"],
            "client_code": ["C1", "C2", "C3", "C4"],
            "deal_status": ["Open", "Open", "Won", "Dead"],
            "sector": ["Mining", "Renewables", "Mining", "Railways"],
            "deal_value": [1000000.0, 500000.0, 2000000.0, 300000.0],
            "calculated_probability": [0.8, 0.3, 1.0, 0.0],
            "tentative_close_date": [datetime.date(2026, 8, 15), datetime.date(2026, 11, 20), None, None],
            "actual_close_date": [None, None, datetime.date(2026, 7, 10), datetime.date(2026, 5, 5)]
        }
        self.df_deals = pd.DataFrame(deals_data)

        # Create a mock cleaned Work Orders DataFrame
        wo_data = {
            "deal_name": ["Deal 1", "Deal 3", "Deal 5"],
            "client_code": ["C1", "C3", "C5"],
            "execution_status": ["Ongoing", "Completed", "Pause / struck"],
            "amount_excl_gst": [800000.0, 1800000.0, 500000.0],
            "billed_value_excl_gst": [400000.0, 1800000.0, 100000.0],
            "collected_amount": [200000.0, 1800000.0, 0.0],
            "amount_receivable": [200000.0, 0.0, 100000.0],
            "probable_end_date": [datetime.date(2026, 6, 1), datetime.date(2026, 8, 1), datetime.date(2026, 12, 1)],
            "collection_date": [None, None, None]
        }
        self.df_wo = pd.DataFrame(wo_data)

    def test_get_pipeline_summary_overall(self):
        summary = get_pipeline_summary(self.df_deals)
        open_metrics = summary["open_deals"]
        won_metrics = summary["won_deals"]
        
        self.assertEqual(open_metrics["count"], 2)
        self.assertEqual(open_metrics["total_value"], 1500000.0) # Deal 1 + Deal 2
        # Weighted value = 1M * 0.8 + 500K * 0.3 = 800K + 150K = 950K
        self.assertEqual(open_metrics["weighted_value"], 950000.0)
        
        self.assertEqual(won_metrics["count"], 1)
        self.assertEqual(won_metrics["total_value"], 2000000.0)

    def test_get_pipeline_summary_quarter_filter(self):
        # Q3 2026 timing check
        summary = get_pipeline_summary(self.df_deals, quarter=3, year=2026)
        open_metrics = summary["open_deals"]
        won_metrics = summary["won_deals"]
        
        # Deal 1 tentative close (Aug 2026) is in Q3 2026, Deal 2 (Nov 2026) is in Q4
        self.assertEqual(open_metrics["count"], 1)
        self.assertEqual(open_metrics["total_value"], 1000000.0)
        
        # Deal 3 actual close (July 2026) is in Q3 2026
        self.assertEqual(won_metrics["count"], 1)
        self.assertEqual(won_metrics["total_value"], 2000000.0)

    def test_get_pipeline_by_sector(self):
        sectors = get_pipeline_by_sector(self.df_deals)
        self.assertEqual(len(sectors), 2) # Mining and Renewables are the open sectors
        self.assertEqual(sectors[0]["sector"], "Mining")
        self.assertEqual(sectors[0]["total_value"], 1000000.0)
        self.assertEqual(sectors[1]["sector"], "Renewables")
        self.assertEqual(sectors[1]["total_value"], 500000.0)

    def test_get_delayed_work_orders(self):
        delayed = get_delayed_work_orders(self.df_wo)
        
        # Deal 1: Ongoing, probable_end_date June 2026 (overdue relative to system/today context)
        # Deal 5: Pause / struck (stalled status is delayed regardless of end date)
        # Deal 3: Completed (cannot be delayed)
        
        self.assertEqual(len(delayed), 2)
        delayed_names = [item["deal_name"] for item in delayed]
        self.assertIn("Deal 1", delayed_names)
        self.assertIn("Deal 5", delayed_names)
        
    def test_get_operational_summary(self):
        summary = get_operational_summary(self.df_wo)
        self.assertEqual(summary["total_work_orders"], 3)
        self.assertEqual(summary["financials"]["total_receivable"], 300000.0) # Deal 1 + Deal 5
