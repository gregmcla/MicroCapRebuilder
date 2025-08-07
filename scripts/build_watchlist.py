#!/usr/bin/env python3
import json

def main():
    candidates = ["AAPL","MSFT","GOOG"]
    with open("data/watchlist.jsonl", "w") as f:
        for t in candidates:
            f.write(json.dumps({"ticker": t}) + "\n")
    print("✅ watchlist.jsonl created")

if __name__ == "__main__":
    main()
