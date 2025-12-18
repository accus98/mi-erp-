import unittest
from core.tools.safe_eval import safe_eval
import datetime

class TestSafeEval(unittest.TestCase):
    def test_basic_math(self):
        self.assertEqual(safe_eval("1 + 1"), 2)
        self.assertEqual(safe_eval("10 * 2"), 20)
        
    def test_whitelist(self):
        self.assertEqual(safe_eval("len([1, 2])"), 2)
        self.assertTrue(safe_eval("datetime.datetime.now()"))
        self.assertEqual(safe_eval("True"), True)
        
    def test_block_import(self):
        with self.assertRaises(ValueError):
            safe_eval("__import__('os')")
            
    def test_block_builtins(self):
        with self.assertRaises(ValueError):
            safe_eval("open('test.txt')")
            
    def test_double_underscore(self):
        # We explicitly blocked double underscores except maybe for specific cases if logic changed.
        # Current implementation blocks it.
        with self.assertRaises(ValueError):
            safe_eval("''.__class__")

if __name__ == '__main__':
    unittest.main()
