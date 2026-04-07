# 🚀 Vequil Logging for OpenClaw

Streaming your agents to Vequil is direct and simple. Follow these steps to get your first log in under 60 seconds.

## 1. Setup

1.  **Download** the `vequil_plugin.py` file from the [Vequil misc folder](file:///Users/noahdonovan/vequil-alpha/misc/openclaw/hooks/vequil_plugin.py).
2.  **Locate** your OpenClaw installation folder on your machine.
3.  **Drop** the `vequil_plugin.py` file into the `hooks/` directory of your OpenClaw folder.

## 2. Connect Your Ledger

4.  **Open** your terminal or your `.env` file.
5.  **Add** your Vequil API Key:
    ```bash
    export VEQUIL_API_KEY="your-api-key-here"
    export VEQUIL_URL="http://localhost:8000/api/log"
    ```
    *(If you're using a .env file, just add: VEQUIL_API_KEY=your-api-key-here)*

## 3. Verify

6.  **Restart** your OpenClaw agent.
7.  **Run** any command in your OpenClaw console (e.g., "Hi agent, browse the web").
8.  **Open** the Vequil [Dashboard](file:///Users/noahdonovan/vequil-alpha/web/static/dashboard.html).
9.  **Refresh** the ledger – you should see your agent's actions appearing in real-time.

---
**Need help?** Join the Moltbook community or check the [Vequil Documentation](file:///Users/noahdonovan/vequil-alpha/docs/README.md).
