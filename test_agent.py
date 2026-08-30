import unittest
import pandas as pd
import numpy as np
import datetime
import os

# Import modules to test
import data_cleaner
import business_logic
import agent_core

class TestDataCleaner(unittest.TestCase):
    def test_sector_normalization(self):
        # Test basic strip and case mapping
        self.assertEqual(data_cleaner.normalize_sector("mining "), "Mining")
        self.assertEqual(data_cleaner.normalize_sector("  renewables"), "Renewables")
        self.assertEqual(data_cleaner.normalize_sector("dsp"), "DSP")
        self.assertEqual(data_cleaner.normalize_sector("security and surveillance"), "Security and Surveillance")
        self.assertEqual(data_cleaner.normalize_sector("aviation"), "Aviation")
        self.assertEqual(data_cleaner.normalize_sector(None), "Unknown")
        self.assertEqual(data_cleaner.normalize_sector(np.nan), "Unknown")

    def test_status_normalization(self):
        self.assertEqual(data_cleaner.normalize_status("  Open  "), "Open")
        self.assertEqual(data_cleaner.normalize_status(np.nan), "Unknown")

    def test_date_and_number_parsing(self):
        # Create a mock deals dataframe
        raw_data = {
            "Deal Name": ["Deal A", "Nezuko", "Bugs Bunny"],
            "Deal Status": ["Open", "Deal Status", "Deal Status"], # Two duplicates
            "Masked Deal value": [500000.0, np.nan, np.nan],
            "Created Date": ["2026-08-30", "Created Date", "Created Date"],
            "Closure Probability": ["High", "Closure Probability", "Closure Probability"]
        }
        df_raw = pd.DataFrame(raw_data)
        df_clean = data_cleaner.clean_deals_df(df_raw)
        
        # Nezuko and Bugs Bunny rows must be filtered out
        self.assertEqual(len(df_clean), 1)
        self.assertEqual(df_clean.iloc[0]["deal_name"], "Deal A")
        self.assertEqual(df_clean.iloc[0]["deal_value"], 500000.0)
        self.assertEqual(df_clean.iloc[0]["created_date"], datetime.date(2026, 8, 30))
        self.assertEqual(df_clean.iloc[0]["calculated_probability"], 0.8)

class TestBusinessLogic(unittest.TestCase):
    def setUp(self):
        # Load local excel files for testing analytics functions
        self.df_deals, self.df_wo = data_cleaner.load_and_clean_local_data()

    def test_pipeline_totals(self):
        # Calculate pipeline metrics
        metrics = business_logic.get_pipeline_summary(self.df_deals)
        
        # Verify keys are present
        self.assertIn("open_deals", metrics)
        self.assertIn("won_deals", metrics)
        
        open_metrics = metrics["open_deals"]
        self.assertGreater(open_metrics["count"], 0)
        self.assertGreater(open_metrics["total_value"], 0)
        self.assertGreater(open_metrics["weighted_value"], 0)
        self.assertLess(open_metrics["weighted_value"], open_metrics["total_value"])

    def test_sector_grouping(self):
        sectors = business_logic.get_pipeline_by_sector(self.df_deals)
        self.assertGreater(len(sectors), 0)
        # Check first sector is sorted by total value descending
        self.assertGreaterEqual(sectors[0]["total_value"], sectors[-1]["total_value"])

    def test_quarter_filtering(self):
        # Test date range resolution
        q, y = agent_core.resolve_relative_quarter("Q3 2026")
        self.assertEqual(q, 3)
        self.assertEqual(y, 2026)
        
        # Test filtering
        metrics_q3 = business_logic.get_pipeline_summary(self.df_deals, quarter=3, year=2026)
        self.assertEqual(metrics_q3["quarter_filter"], 3)
        self.assertEqual(metrics_q3["year_filter"], 2026)

    def test_delayed_work_orders(self):
        delayed = business_logic.get_delayed_work_orders(self.df_wo)
        self.assertGreater(len(delayed), 0)
        
        # Check that reasons are documented for delay
        self.assertTrue(any("Execution is" in item["reasons"] or "Billing status" in item["reasons"] or "Overdue" in item["reasons"] for item in delayed))

    def test_data_quality_report(self):
        report = business_logic.generate_data_quality_report(self.df_deals, self.df_wo)
        
        # Verify structure
        self.assertIn("deals_board", report)
        self.assertIn("work_orders_board", report)
        
        deals_rep = report["deals_board"]
        wo_rep = report["work_orders_board"]
        
        # In our excel dataset, won_deals_missing_values is high (101)
        self.assertEqual(deals_rep["won_deals_missing_values"], 101)
        # collection_date is 100% missing in our work orders sheet (176)
        self.assertEqual(wo_rep["empty_collection_dates"], 176)

if __name__ == "__main__":
    unittest.main()
