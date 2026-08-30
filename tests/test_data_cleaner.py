import unittest
import pandas as pd
import numpy as np
import datetime
from backend.data_cleaner import (
    normalize_text, normalize_sector, parse_date, parse_number, 
    normalize_deals, normalize_work_orders
)

class TestDataCleaner(unittest.TestCase):
    def test_normalize_text(self):
        self.assertEqual(normalize_text("  hello  "), "hello")
        self.assertIsNone(normalize_text("   "))
        self.assertIsNone(normalize_text(None))

    def test_normalize_sector(self):
        self.assertEqual(normalize_sector("renewables "), "Renewables")
        self.assertEqual(normalize_sector("mining"), "Mining")
        self.assertEqual(normalize_sector("dsp"), "DSP")
        self.assertEqual(normalize_sector("  "), "Unknown")
        self.assertEqual(normalize_sector(None), "Unknown")

    def test_parse_date(self):
        self.assertEqual(parse_date("2026-08-30"), datetime.date(2026, 8, 30))
        self.assertEqual(parse_date("30-08-2026"), datetime.date(2026, 8, 30))
        self.assertIsNone(parse_date("invalid date"))
        self.assertIsNone(parse_date("   "))

    def test_parse_number(self):
        self.assertEqual(parse_number("$15,300,000.50"), 15300000.50)
        self.assertEqual(parse_number("₹1,200.00"), 1200.0)
        self.assertEqual(parse_number("invalid number"), 0.0)
        self.assertEqual(parse_number(" "), 0.0)

    def test_normalize_deals_garbage_filter(self):
        # Create a mock raw Deals dataframe containing a duplicate header row
        data = {
            "deal_name": ["Deal A", "Nezuko", "Deal B"],
            "deal_status": ["Open", "Deal Status", "Won"],
            "closure_probability": ["High", "Closure Probability", "Low"],
            "deal_value": ["1000", "Masked Deal value", "2000"],
            "sector": ["mining", "Sector/service", "renewables"]
        }
        df = pd.DataFrame(data)
        cleaned = normalize_deals(df)
        
        # Nezuko garbage row should be filtered out
        self.assertEqual(len(cleaned), 2)
        self.assertNotIn("Nezuko", cleaned["deal_name"].values)
        self.assertEqual(cleaned.iloc[0]["sector"], "Mining")
        self.assertEqual(cleaned.iloc[1]["sector"], "Renewables")
        self.assertEqual(cleaned.iloc[0]["calculated_probability"], 0.8)
        self.assertEqual(cleaned.iloc[1]["calculated_probability"], 1.0) # Won status gets 100%
