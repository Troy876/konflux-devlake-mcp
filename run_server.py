#!/usr/bin/env python3
"""
Simple launcher script for the Konflux DevLake MCP Server
"""

import sys
import os

# Add the parent directory to Python path so we can import database_mcp_server
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Import and run the main function
from database_mcp_server.main import main_sync

if __name__ == "__main__":
    main_sync() 