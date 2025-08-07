#!/usr/bin/env python3
import json
from pathlib import Path


def main():
    candidates = ["AAPL", "MSFT", "GOOG"]
    output_path = Path(__file__).parent.parent / "data" / "watchlist.jsonl"
    with output_path.open("w") as f:
        for t in candidates:
            f.write(json.dumps({"ticker": t}) + "\n")
    print("✅ watchlist.jsonl created")


if __name__ == "__main__":
    main()
