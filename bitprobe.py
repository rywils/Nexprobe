#!/usr/bin/env python3

import argparse
import json
import os
import re
from datetime import datetime

from scanner.config import ScanConfig
from scanner.engine import ScanEngine
from scanner.reporting.markdown_report import MarkdownReportGenerator
from scanner.reporting.pdf_report import PDFReportGenerator
from scanner.reporting.dashboard import DashboardGenerator


def update_scan_history(history_path: str, client_name: str, report: dict, output_dir: str):
    entry = {
        "client_name": client_name,
        "target": report.get("target"),
        "scan_id": report.get("scan_id"),
        "timestamp": report.get("timestamp"),
        "risk": report.get("statistics", {}).get("risk", {}),
        "totals": {
            "findings": report.get("statistics", {}).get("total_findings", 0),
            "by_severity": report.get("statistics", {}).get("findings_by_severity", {}),
        },
        "output_directory": os.path.abspath(output_dir),
    }

    if os.path.exists(history_path):
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    else:
        history = []

    if not isinstance(history, list):
        history = []

    history.append(entry)

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    return history


def main():
    print(">>> NexProbe starting <<<")

    parser = argparse.ArgumentParser(description="Web Application Security Scanner")
    parser.add_argument("--target", "-t", help="Target URL to scan")
    parser.add_argument("--config", "-c", help="Path to YAML config file")
    parser.add_argument("--plugins", "-p", help="Comma-separated list of plugins to use")
    parser.add_argument("--output", "-o", choices=["json", "html", "cli", "md"], default="cli")
    parser.add_argument("--report-dir", "-r", default="./scan_results")

    args = parser.parse_args()

    # -----------------------------
    # LOAD CONFIG
    # -----------------------------
    if args.config:
        config = ScanConfig.from_yaml(args.config)
    elif args.target:
        plugins = args.plugins.split(",") if args.plugins else None
        config = ScanConfig.from_target(args.target, plugins)
    else:
        parser.error("Either --target or --config must be specified")

    # -----------------------------
    # CLIENT / TARGET NAME PROMPT
    # -----------------------------
    client_name = input("Enter Company/Target Name (for report labeling): ").strip()
    if not client_name:
        client_name = "Unknown Client"

    config.client_name = client_name

    # -----------------------------
    # OUTPUT DIRECTORY NAMING
    # -----------------------------
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", client_name)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    output_dir = os.path.join(args.report_dir, f"{safe_name}_{timestamp}")
    config.output_directory = output_dir

    if args.output:
        config.output_formats = [args.output]

    # -----------------------------
    # RUN SCAN
    # -----------------------------
    engine = ScanEngine(config)
    report = engine.run_scan()

    # -----------------------------
    # SAVE RAW JSON
    # -----------------------------
    os.makedirs(config.output_directory, exist_ok=True)

    raw_json_path = os.path.join(config.output_directory, "raw.json")
    with open(raw_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n[+] Raw JSON report saved to: {raw_json_path}")

    # -----------------------------
    # GENERATE MARKDOWN REPORT
    # -----------------------------
    md_generator = MarkdownReportGenerator(
        report_data=report,
        output_directory=config.output_directory,
        client_name=config.client_name,
    )

    md_path = md_generator.generate()
    print(f"[+] Markdown report generated: {md_path}")

    # -----------------------------
    # GENERATE PDF REPORT
    # -----------------------------
    pdf_generator = PDFReportGenerator(
        report_data=report,
        output_directory=config.output_directory,
        client_name=config.client_name,
    )

    pdf_path = pdf_generator.generate()
    print(f"[+] PDF report generated: {pdf_path}")

    # -----------------------------
    # UPDATE HISTORY + DASHBOARD
    # -----------------------------
    history_path = os.path.join(args.report_dir, "scan_history.json")
    history_entries = update_scan_history(history_path, client_name, report, output_dir)

    dashboard = DashboardGenerator(history_entries=history_entries, base_report_dir=args.report_dir)
    dashboard_path = dashboard.generate()
    print(f"[+] HTML dashboard updated: {dashboard_path}")


if __name__ == "__main__":
    main()
