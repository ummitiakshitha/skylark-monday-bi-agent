import unittest
from backend.schema_mapper import SchemaMapper

class TestSchemaMapper(unittest.TestCase):
    def test_get_column_mapping_deals(self):
        # Mock Monday columns metadata response
        mock_cols = [
            {"id": "text7", "title": "Owner code", "type": "text"},
            {"id": "numbers1", "title": "Masked Deal value", "type": "numeric"},
            {"id": "date3", "title": "Tentative Close Date", "type": "date"},
            {"id": "status4", "title": "Unrelated Header", "type": "status"}
        ]
        
        mapping = SchemaMapper.get_column_mapping(mock_cols, is_deals=True)
        
        # Mapped properties
        self.assertEqual(mapping["text7"], "owner_code")
        self.assertEqual(mapping["numbers1"], "deal_value")
        self.assertEqual(mapping["date3"], "tentative_close_date")
        
        # Unmapped properties should be excluded
        self.assertNotIn("status4", mapping)

    def test_get_column_mapping_work_orders(self):
        mock_cols = [
            {"id": "text2", "title": "Deal name masked", "type": "text"},
            {"id": "numbers5", "title": "Amount receivable (masked)", "type": "numeric"},
            {"id": "status9", "title": "Execution Status", "type": "status"}
        ]
        
        mapping = SchemaMapper.get_column_mapping(mock_cols, is_deals=False)
        
        self.assertEqual(mapping["text2"], "deal_name")
        self.assertEqual(mapping["numbers5"], "amount_receivable")
        self.assertEqual(mapping["status9"], "execution_status")
