"""Quick test: can we load the suite?"""
import sys, os, unittest
os.chdir(r"C:\Users\Zvonimir\Desktop\resonate-qwen-worker")
loader = unittest.TestLoader()
suite = loader.discover("tests", top_level_dir=".")
print(f"Loaded {suite.countTestCases()} tests")
