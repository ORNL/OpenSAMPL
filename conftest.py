import os
import sys

# Add the project root to the path so pytest can find the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))