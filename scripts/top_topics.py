#!/usr/bin/env python3
"""Rank support topics so you fix the content that matters most.

Reads a ticket export (ticket_id, created, topic, channel), compares the last
30 days with the 30 days before, and writes a ranked report.

The data in data/tickets.csv is synthetic. With a real export, only the column
names need to match.

Usage:
    python scripts/top_topics.py
    python scripts/top_topics.py --as-of 2026-11-30 --report reports/top-topics.md
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tickets", default="data/tickets.csv")
    parser.add_argument("--report", default="reports/top-topics.md")
    parser.add_argument("--as-of", default=None, help="End date (YYYY-MM-DD). Default: latest ticket date.")
    parser.add_argument("--window", type=int, default=30, help="Window length in days.")
    args = parser.parse_args()

    tickets = pd.read_csv(args.tickets, parse_dates=["created"])
    end = pd.Timestamp(args.as_of) if args.as_of else tickets["created"].max()
    last_start = end - pd.Timedelta(days=args.window - 1)
    prev_start = last_start - pd.Timedelta(days=args.window)

    last = tickets[(tickets["created"] >= last_start) & (tickets["created"] <= end)]
    prev = tickets[(tickets["created"] >= prev_start) & (tickets["created"] < last_start)]

    table = pd.DataFrame({
        "last": last["topic"].value_counts(),
        "previous": prev["topic"].value_counts(),
    }).fillna(0).astype(int)
    table["change"] = table["last"] - table["previous"]
    table["share"] = (table["last"] / max(table["last"].sum(), 1) * 100).round(0).astype(int)
    table = table.sort_values(["last", "change"], ascending=False)

    def verdict(row: pd.Series) -> str:
        if row["change"] >= 5 and row["previous"] <= 3:
            return "Rising fast: new or newly confusing"
        if row["last"] >= 12:
            return "Fix first: high volume"
        if row["change"] >= 3:
            return "Watch: rising"
        return "-"

    table["note"] = table.apply(verdict, axis=1)

    lines = [
        "# Most-asked topics",
        "",
        f"Window: {last_start.date()} to {end.date()} ({args.window} days) compared with the {args.window} days before. "
        f"Tickets in window: {len(last)}.",
        "",
        "| Rank | Topic | Last 30 days | Previous 30 days | Change | Share | Note |",
        "|---|---|---|---|---|---|---|",
    ]
    for rank, (topic, row) in enumerate(table.iterrows(), start=1):
        lines.append(
            f"| {rank} | {topic} | {row['last']} | {row['previous']} | {row['change']:+d} | {row['share']}% | {row['note']} |")
    lines += [
        "",
        "Volume alone does not decide what to fix. Read a sample of tickets in the top topics, "
        "fix the page, then check whether the count falls in the next window.",
        "",
    ]
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
