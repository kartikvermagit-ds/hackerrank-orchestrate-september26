import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from evaluate import evaluate_sample_requests

if __name__ == '__main__':
    evaluate_sample_requests()
