#!/usr/bin/env python3
"""CLI launcher."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import streamlit.web.cli as stcli

if __name__ == "__main__":
    app_path = os.path.join(os.path.dirname(__file__), "..", "src", "alto", "app.py")
    sys.argv = ["streamlit", "run", app_path, "--server.port=8501"]
    stcli.main()
