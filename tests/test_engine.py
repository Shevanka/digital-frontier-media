import unittest
from production_engine.engine import validate_package
from production_engine.rss import clean_html, parse_date

class EngineTests(unittest.TestCase):
    def test_clean_html(self):
        self.assertEqual(clean_html("<p>Hello&nbsp; world</p>"), "Hello world")

    def test_parse_date(self):
        self.assertIsNotNone(parse_date("Wed, 05 Nov 2026 10:00:00 GMT"))
        self.assertIsNone(parse_date("not a date"))

    def test_validate_package_rejects_empty_data(self):
        errors = validate_package({})
        self.assertTrue(errors)
        self.assertTrue(any("Missing top-level field" in error for error in errors))

if __name__ == "__main__":
    unittest.main()
