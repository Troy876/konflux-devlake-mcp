#!/usr/bin/env python3
"""
Konflux DevLake MCP Server - Entry Point
"""

import asyncio
import sys
from .main import main_sync

if __name__ == "__main__":
    main_sync() 