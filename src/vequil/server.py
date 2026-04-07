from __future__ import annotations

import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .config import OUTPUT_DIR, WEB_DIR   # config.py loads .env automatically
from .pipeline import run_pipeline
from .notifier import notifier

import os

_API_KEY: str | None = os.getenv("DASHBOARD_API_KEY")


class VequilHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    # ── Auth check ────────────────────────────────────────────

    def _authorized(self) -> bool:
        """Returns True if no key is configured (dev mode) or the header matches."""
        if not _API_KEY:
            return True             # no key set → open in dev mode
        return self.headers.get("X-API-Key") == _API_KEY

    def _require_auth(self) -> bool:
        """Write a 401 and return False if not authorized."""
        if not self._authorized():
            self._write_json({"error": "Unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
            return False
        return True

    # ── Routing ───────────────────────────────────────────────

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/api/health":
            if not self._require_auth():
                return
            self._write_json({"status": "ok", "auth": bool(_API_KEY)})
            return

        if parsed.path == "/api/reconciliation":
            if not self._require_auth():
                return
            force_run = "run" in qs and qs["run"][0] == "1"
            event_id = qs["event_id"][0] if "event_id" in qs else None
            
            dashboard_dir = OUTPUT_DIR / "events" / event_id if event_id else OUTPUT_DIR
            dashboard_path = dashboard_dir / "dashboard.json"

            # Re-run the full pipeline if explicitly requested or no output exists
            if force_run or not dashboard_path.exists():
                run_pipeline(event_id=event_id)

            payload = json.loads(dashboard_path.read_text(encoding="utf-8"))
            
            # Inject resolutions
            res_file = Path(__file__).resolve().parents[2] / "data" / "resolutions.json"
            if res_file.exists():
                resolutions = json.loads(res_file.read_text(encoding="utf-8"))
                for finding in payload.get("discrepancies", []):
                    fid = f"{finding['processor']}_{finding['reference_id']}_{finding['discrepancy_type']}"
                    if fid in resolutions:
                        finding["resolution"] = resolutions[fid]
            
            self._write_json(payload)
            return

        if parsed.path == "/api/history":
            if not self._require_auth():
                return
            events_dir = OUTPUT_DIR / "events"
            history = []
            if events_dir.exists():
                for d in events_dir.iterdir():
                    if d.is_dir() and (d / "dashboard.json").exists():
                        history.append({
                            "event_id": d.name,
                            "created_at": d.stat().st_mtime
                        })
            self._write_json({"history": sorted(history, key=lambda x: x["created_at"], reverse=True)})
            return

        if parsed.path == "/api/export":
            if not self._require_auth():
                return
            event_id = qs.get("event_id", [None])[0]
            # Use root output dir if event_id is None OR an empty string
            report_dir = (OUTPUT_DIR / "events" / event_id) if (event_id and event_id.strip()) else OUTPUT_DIR
            report_path = report_dir / "reconciliation_report.xlsx"
            
            if not report_path.exists():
                run_pipeline(event_id=event_id)
            
            with report_path.open("rb") as f:
                content = f.read()
            
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", f'attachment; filename="vequil_report_{event_id or "latest"}.xlsx"')
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Expose-Headers", "Content-Disposition")
            self.end_headers()
            self.wfile.write(content)
            return

        if parsed.path == "/":
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/resolve":
            if not self._require_auth():
                return
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            
            ref_id = data.get("finding_id")
            resolution = data.get("resolution")
            
            if not ref_id:
                self._write_json({"error": "Missing finding_id"}, status=HTTPStatus.BAD_REQUEST)
                return

            res_file = Path(__file__).resolve().parents[2] / "data" / "resolutions.json"
            resolutions = {}
            if res_file.exists():
                resolutions = json.loads(res_file.read_text(encoding="utf-8"))
            
            resolutions[ref_id] = resolution
            res_file.write_text(json.dumps(resolutions, indent=2), encoding="utf-8")
            
            self._write_json({"status": "ok"})
            return
        if parsed.path == "/api/demo":
            # This is a public endpoint, no auth required.
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            email = data.get("email")
            
            if not email:
                self._write_json({"error": "Email is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            
            # Save to leads.json
            leads_file = Path(__file__).resolve().parents[2] / "data" / "leads.json"
            leads = []
            if leads_file.exists():
                try:
                    leads = json.loads(leads_file.read_text(encoding="utf-8"))
                except:
                    leads = []
            
            leads.append({
                "email": email,
                "timestamp": datetime.now().isoformat(),
                "ip": self.client_address[0]
            })
            leads_file.write_text(json.dumps(leads, indent=2), encoding="utf-8")
            
            # Send alert
            notifier.notify_lead(email)
            
            print(f"   [LEAD] New early access signup captured: {email}")
            self._write_json({"status": "ok", "message": "Signup captured"})
            return

        if parsed.path == "/api/log":
            if not self._require_auth():
                return
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                self._log_action(data)
                self._write_json({"status": "ok", "message": "Action logged"})
            except Exception as e:
                self._write_json({"error": str(e)}, status=HTTPStatus.BAD_REQUEST)
            return

    # ── Helpers ───────────────────────────────────────────────

    def _log_action(self, data: dict) -> None:
        """Appends a single agent action to the OpenClaw logs CSV."""
        from .config import RAW_DATA_DIR
        import csv
        
        log_file = RAW_DATA_DIR / "openclaw_logs.csv"
        fields = [
            "Timestamp", "Project", "SessionID", "ActionID", 
            "ToolUsed", "Model", "ComputeCost", "TaskStatus", "Deployment"
        ]
        
        file_exists = log_file.exists()
        with open(log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            if not file_exists:
                writer.writeheader()
            
            # Ensure all fields are present to avoid DictWriter errors
            row = {f: data.get(f, "—") for f in fields}
            # Auto-timestamp if missing
            if row["Timestamp"] == "—":
                row["Timestamp"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                
            writer.writerow(row)
        
        print(f"   [LOG] Agent action received: {row['ActionID']} ({row['ToolUsed']})")

    def _write_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: A002
        # Custom compact log: timestamp + method + path + status
        print(f"  {self.log_date_time_string()}  {args[0]}  →  {args[1]}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if _API_KEY:
        print(f"🔐 Auth enabled  (DASHBOARD_API_KEY is set)")
    else:
        print("⚠️  Auth disabled (set DASHBOARD_API_KEY in .env to enable)")

    host = "0.0.0.0"
    port = int(os.getenv("PORT", 8000))
    server = ThreadingHTTPServer((host, port), VequilHandler)
    print(f"🚀 Vequil server → http://{host}:{port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
