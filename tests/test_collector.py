import unittest
import collect

class TestCollector(unittest.TestCase):
    def test_matching(self):
        self.assertTrue(collect.relevant({"name": "Expense Tracker", "description": ""}))
        self.assertFalse(collect.relevant({"name": "Weather", "description": "Forecast"}))
        self.assertFalse(collect.relevant({"name": "Employee reimbursement expense app", "description": ""}))

    def test_configuration_fingerprint(self):
        self.assertEqual(len(collect.CONFIG_HASH), 12)

if __name__ == "__main__":
    unittest.main()
