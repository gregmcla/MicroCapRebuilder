#!/usr/bin/env python3
import datetime as dt
from pathlib import Path

import pandas as pd


PORTFOLIO_PATH = Path("data/portfolio.csv")
UPDATE_PATH = Path("data/portfolio_update.csv")
STARTING_CASH = 5000.0


def main() -> None:
    if not PORTFOLIO_PATH.exists():
        raise SystemExit(f"{PORTFOLIO_PATH} not found")

    # Load today's portfolio and validate required columns
    df_port = pd.read_csv(PORTFOLIO_PATH)
    required = {"Ticker", "Shares", "Price", "Cost"}
    missing = required - set(df_port.columns)
    if missing:
        raise SystemExit(
            f"Missing required columns in portfolio.csv: {', '.join(sorted(missing))}"
        )

    # Compute value column if absent
    if "Value" not in df_port.columns:
        df_port["Value"] = df_port["Shares"] * df_port["Price"]

    pos_val = df_port["Value"].sum()
    cash = STARTING_CASH - df_port["Cost"].sum()
    today = dt.date.today().isoformat()

    # Prepare TOTAL row based on shared schema
    schema = ["Date"] + [c for c in df_port.columns if c != "Date"] + ["Cash", "Equity"]
    total_row = {col: "" for col in schema}
    total_row.update(
        {
            "Date": today,
            "Ticker": "TOTAL",
            "Value": round(pos_val, 2),
            "Cash": round(cash, 2),
            "Equity": round(pos_val + cash, 2),
        }
    )

    # Append to existing portfolio_update.csv
    if UPDATE_PATH.exists():
        df_update = pd.read_csv(UPDATE_PATH)
        df_update = df_update.reindex(columns=schema)
    else:
        df_update = pd.DataFrame(columns=schema)

    df_update.loc[len(df_update)] = total_row
    df_update.to_csv(UPDATE_PATH, index=False)
    print(f"✅ TOTAL for {today} set to {pos_val+cash:.2f}")


if __name__ == "__main__":
    main()

