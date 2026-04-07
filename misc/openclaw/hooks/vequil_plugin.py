"""
vequil_plugin.py — OpenClaw Vequil Logging Plugin
Automatically stream agent actions and tool results to your Vequil Ledger.

Installation:
1. Copy this file into your OpenClaw 'hooks/' directory.
2. Set your environment variables:
   export VEQUIL_API_KEY="your-api-key"
   export VEQUIL_URL="http://localhost:8000/api/log"
3. Restart OpenClaw.
"""

import os
import json
import requests
import datetime
from pathlib import Path

# Config
VEQUIL_API_KEY = os.getenv("VEQUIL_API_KEY")
VEQUIL_URL = os.getenv("VEQUIL_URL", "http://localhost:8000/api/log")

def get_project_name():
    """Detect current project from working directory."""
    return Path.cwd().name

def log_to_vequil(payload):
    """Send action to the Vequil ingestion engine."""
    if not VEQUIL_API_KEY:
        print("⚠️ [Vequil] Missing VEQUIL_API_KEY. Action skipped.")
        return
    
    headers = {
        "X-API-Key": VEQUIL_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        res = requests.post(VEQUIL_URL, json=payload, headers=headers, timeout=2)
        if res.status_code != 200:
            print(f"❌ [Vequil] Log failed: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ [Vequil] Connection error: {e}")

# OpenClaw Hook: tool_result_persist
def tool_result_persist(context, result):
    """
    Hooked into every tool execution before it hits the session disk.
    - context: { sessionId, agentId, ... }
    - result: { toolName, output, ... }
    """
    try:
        # Extract metadata
        session_id = getattr(context, 'sessionId', 'anon-sess')
        agent_name = getattr(context, 'agentId', 'OpenClaw')
        
        # Prepare Vequil payload
        payload = {
            "Timestamp":    datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "Project":      get_project_name(),
            "SessionID":    session_id,
            "ActionID":     f"act_{os.urandom(4).hex()}",
            "ToolUsed":     result.get('toolName', 'unknown_tool'),
            "Model":        "gpt-4o", # Default for OC
            "ComputeCost":  0.0,      # To be estimated by Vequil
            "TaskStatus":   "COMPLETED",
            "Deployment":   "LOCAL"
        }
        
        # Stream it
        log_to_vequil(payload)
        
    except Exception as e:
        print(f"⚠️ [Vequil] Hook error: {e}")
    
    # Return result unchanged (OpenClaw requires returning the modified or original result)
    return result

if __name__ == "__main__":
    print("Vequil Logging Plugin for OpenClaw initialized.")
    if not VEQUIL_API_KEY:
        print("Note: VEQUIL_API_KEY environment variable is not set.")
