"""Self-curating observation memory + cross-portfolio signal pool.

After every execute that produced trades, Opus reviews:
  - the portfolio's current observations.json
  - the global shared_observations.json
  - this cycle's recent trades, both per-trade and clustered by dominant entry factor

…and emits curation operations: retire / update / add / add_shared. Operations
are applied with a hard cap so the memory cannot grow unbounded; the oldest
last_updated observation is dropped if the cap would be exceeded.

The analyze prompt reads observations.json + shared_observations.json and
injects only observations whose `regime` matches the current market regime
(or are tagged "ALL").

Fails soft: any API / parse / IO error swallowed with a log line so execute
never breaks because of reflection.
"""
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_review import get_ai_client
_REFLECTION_MODEL = "claude-sonnet-4-6"

MAX_OBSERVATIONS_PER_PORTFOLIO = 25
MAX_SHARED_OBSERVATIONS = 30
OBSERVATIONS_IN_PROMPT = 10
SHARED_IN_PROMPT = 5
MIN_SAMPLE_FOR_NEW = 3
MAX_EVIDENCE_TICKERS = 10
MAX_TOKENS = 1500
TIMEOUT_SECONDS = 60.0


def _data_dir() -> Path:
    return Path(os.environ.get("MCR_DATA_DIR") or (Path(__file__).parent.parent / "data"))


def _obs_file(portfolio_id: str) -> Path:
    return _data_dir() / "portfolios" / portfolio_id / "observations.json"


def _shared_file() -> Path:
    return _data_dir() / "shared_observations.json"


def _read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [reflection] Could not read {path}: {e}")
        return default


def read_observations(portfolio_id: str) -> List[Dict[str, Any]]:
    data = _read_json_file(_obs_file(portfolio_id), {"observations": []})
    return list(data.get("observations") or [])


def write_observations(portfolio_id: str, observations: List[Dict[str, Any]]) -> None:
    f = _obs_file(portfolio_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_json_file(f, {"cycle_count": 0})
    payload = {
        "updated": datetime.utcnow().isoformat() + "Z",
        "cycle_count": int(existing.get("cycle_count") or 0) + 1,
        "observations": observations,
    }
    f.write_text(json.dumps(payload, indent=2))


def read_shared_observations() -> List[Dict[str, Any]]:
    data = _read_json_file(_shared_file(), {"observations": []})
    return list(data.get("observations") or [])


def write_shared_observations(observations: List[Dict[str, Any]]) -> None:
    f = _shared_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated": datetime.utcnow().isoformat() + "Z",
        "observations": observations,
    }
    f.write_text(json.dumps(payload, indent=2))


def format_observations_block(observations: List[Dict[str, Any]], regime: str,
                              shared: Optional[List[Dict[str, Any]]] = None) -> str:
    """Render observations filtered to current regime (+ ALL). Shared shown separately."""
    matches = [o for o in observations if o.get("regime") in (regime, "ALL")]
    matches.sort(key=lambda o: -(o.get("sample_size") or 0))
    take = matches[:OBSERVATIONS_IN_PROMPT]
    if not take and not shared:
        return ""
    lines = []
    if take:
        lines.append(f"\nOBSERVATIONS FROM YOUR OWN HISTORY ({regime}-regime + ALL, ranked by sample size):")
        for o in take:
            lines.append(
                f"  [{o['id']}] (n={o.get('sample_size',0)}, win={o.get('win_rate',0):.0%}) "
                f"{o.get('claim','')}"
            )
    if shared:
        s_matches = [o for o in shared if o.get("regime") in (regime, "ALL")]
        s_matches.sort(key=lambda o: -(o.get("sample_size") or 0))
        s_take = s_matches[:SHARED_IN_PROMPT]
        if s_take:
            lines.append(f"\nCROSS-PORTFOLIO OBSERVATIONS (pooled from other portfolios' evidence):")
            for o in s_take:
                src = ", ".join(o.get("portfolios", [])) or "?"
                lines.append(
                    f"  [{o['id']}] (n={o.get('sample_size',0)}, win={o.get('win_rate',0):.0%}, from: {src}) "
                    f"{o.get('claim','')}"
                )
    if not lines:
        return ""
    lines.append("Weigh these as evidence — not as commandments. Apply when relevant.")
    return "\n".join(lines) + "\n"


def build_reflection_prompt(portfolio_id: str, regime: str,
                            portfolio_observations: List[Dict[str, Any]],
                            shared_observations: List[Dict[str, Any]],
                            clustered_history: str,
                            per_trade_history: str) -> str:
    obs_lines = "\n".join(
        f"  [{o['id']}] regime={o.get('regime','?')} n={o.get('sample_size',0)} "
        f"win={o.get('win_rate',0):.0%} :: {o.get('claim','')}"
        for o in portfolio_observations
    ) or "  (none yet — first cycle)"
    shared_lines = "\n".join(
        f"  [{o['id']}] regime={o.get('regime','?')} n={o.get('sample_size',0)} "
        f"win={o.get('win_rate',0):.0%} from={','.join(o.get('portfolios',[]))} :: {o.get('claim','')}"
        for o in shared_observations
    ) or "  (none yet)"
    return f"""You are curating the trading memory for portfolio "{portfolio_id}".
Current market regime: {regime}

These observations are statistical claims you've previously made about your own
behavior. Each one has an id, a regime tag, a sample size, a win rate, and a
falsifiable claim. Your job is to keep this memory accurate, specific, and small.

YOUR PORTFOLIO'S CURRENT OBSERVATIONS:
{obs_lines}

CROSS-PORTFOLIO SHARED OBSERVATIONS (factor-level patterns from other portfolios):
{shared_lines}

{clustered_history}
{per_trade_history}

EMIT CURATION OPERATIONS. Output ONLY valid JSON matching this schema:

{{
  "retire": ["obs-id-1", ...],              // ids to delete (stale, contradicted, redundant)
  "update": [                                // refresh existing observations with new evidence
    {{"id": "obs-id-2", "claim": "...", "sample_size": <int>, "win_rate": <float 0-1>, "evidence_tickers": ["A","B"]}}
  ],
  "add": [                                   // new portfolio-specific observations
    {{"regime": "BULL|BEAR|SIDEWAYS|ALL", "claim": "...", "sample_size": <int ≥ {MIN_SAMPLE_FOR_NEW}>, "win_rate": <float>, "evidence_tickers": [...]}}
  ],
  "add_shared": [                            // observations that apply across portfolios (factor-level, no business-specific context)
    {{"regime": "BULL|BEAR|SIDEWAYS|ALL", "claim": "...", "sample_size": <int ≥ {MIN_SAMPLE_FOR_NEW}>, "win_rate": <float>, "evidence_tickers": [...]}}
  ]
}}

RULES FOR OBSERVATIONS:
- A good observation cites BOTH conditions AND a measurable outcome. Example:
  GOOD: "BULL momentum entries with price_momentum≥80 AND volume≥75 won 71% (10/14, +6.2% avg); without volume confirmation (vol<60), 27% (3/11, -2.1% avg)."
  BAD:  "Momentum trades work in BULL."  (no sample, no criterion, no falsifiable claim)
- Tag each with the regime it was OBSERVED IN. Use "ALL" only when the pattern truly does not depend on regime.
- An `add_shared` observation must be about factor behavior (e.g., "quality<30 had 28% win rate across 67 trades"), NOT about a specific business or sector strategy.
- Retire any observation whose claim is no longer supported by the evidence you can see, or that has been superseded by a more specific update.
- Update an existing observation when you have meaningfully more evidence — refresh the sample size, win rate, and (if the wording needs work) the claim.
- Be conservative on adding. Prefer updating an existing observation to adding a duplicate.

NO PREAMBLE. NO MARKDOWN OUTSIDE THE CODE FENCE. ONLY JSON.
"""


_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def parse_reflection_response(text: str) -> Dict[str, list]:
    """Extract JSON object from response (handles raw or fenced)."""
    empty: Dict[str, list] = {"retire": [], "update": [], "add": [], "add_shared": []}
    if not text:
        return empty
    candidates = []
    m = _JSON_BLOCK.search(text)
    if m:
        candidates.append(m.group(1))
    candidates.append(text.strip())
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
            return {
                "retire": list(obj.get("retire") or []),
                "update": list(obj.get("update") or []),
                "add": list(obj.get("add") or []),
                "add_shared": list(obj.get("add_shared") or []),
            }
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    return empty


def _new_id(now: str) -> str:
    return f"obs-{now[:10]}-{uuid.uuid4().hex[:6]}"


def _clean_evidence(raw: Any) -> list:
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if x][:MAX_EVIDENCE_TICKERS]


def apply_curation_operations(existing: List[Dict[str, Any]], ops: Dict[str, list],
                              now: Optional[str] = None) -> List[Dict[str, Any]]:
    """Apply retire/update/add ops; enforce per-file cap by dropping oldest last_updated."""
    now = now or (datetime.utcnow().isoformat() + "Z")
    by_id = {o["id"]: dict(o) for o in existing if "id" in o}

    for rid in ops.get("retire", []):
        by_id.pop(rid, None)

    for upd in ops.get("update", []):
        oid = upd.get("id")
        if not oid or oid not in by_id:
            continue
        target = by_id[oid]
        if "claim" in upd:           target["claim"] = upd["claim"]
        if "sample_size" in upd:     target["sample_size"] = int(upd["sample_size"])
        if "win_rate" in upd:        target["win_rate"] = float(upd["win_rate"])
        if "evidence_tickers" in upd:
            target["evidence_tickers"] = _clean_evidence(upd["evidence_tickers"])
        target["last_updated"] = now
        target.setdefault("first_seen", target.get("first_seen") or now)

    for add in ops.get("add", []):
        try:
            n = int(add.get("sample_size") or 0)
        except (TypeError, ValueError):
            continue
        if n < MIN_SAMPLE_FOR_NEW:
            continue
        new = {
            "id": _new_id(now),
            "regime": str(add.get("regime") or "ALL").upper(),
            "claim": str(add.get("claim") or "").strip(),
            "sample_size": n,
            "win_rate": float(add.get("win_rate") or 0.0),
            "first_seen": now,
            "last_updated": now,
            "evidence_tickers": _clean_evidence(add.get("evidence_tickers")),
        }
        if not new["claim"]:
            continue
        by_id[new["id"]] = new

    merged = list(by_id.values())
    if len(merged) > MAX_OBSERVATIONS_PER_PORTFOLIO:
        merged.sort(key=lambda o: o.get("last_updated", ""), reverse=True)
        merged = merged[:MAX_OBSERVATIONS_PER_PORTFOLIO]
    return merged


def _apply_shared_operations(existing: List[Dict[str, Any]], add_shared: list,
                             portfolio_id: str, now: str) -> List[Dict[str, Any]]:
    """Same shape as apply_curation_operations but for the shared pool. Only adds."""
    by_id = {o["id"]: dict(o) for o in existing if "id" in o}
    for add in add_shared or []:
        try:
            n = int(add.get("sample_size") or 0)
        except (TypeError, ValueError):
            continue
        if n < MIN_SAMPLE_FOR_NEW:
            continue
        claim = str(add.get("claim") or "").strip()
        if not claim:
            continue
        # Best-effort merge: if an existing shared observation matches by claim, refresh + add this portfolio
        match = next((o for o in by_id.values() if o.get("claim") == claim), None)
        if match:
            match["sample_size"] = max(int(match.get("sample_size") or 0), n)
            match["win_rate"] = float(add.get("win_rate") or match.get("win_rate") or 0.0)
            match["last_updated"] = now
            ports = set(match.get("portfolios") or [])
            ports.add(portfolio_id)
            match["portfolios"] = sorted(ports)
            continue
        new = {
            "id": _new_id(now),
            "regime": str(add.get("regime") or "ALL").upper(),
            "claim": claim,
            "sample_size": n,
            "win_rate": float(add.get("win_rate") or 0.0),
            "first_seen": now,
            "last_updated": now,
            "evidence_tickers": _clean_evidence(add.get("evidence_tickers")),
            "portfolios": [portfolio_id],
        }
        by_id[new["id"]] = new
    merged = list(by_id.values())
    if len(merged) > MAX_SHARED_OBSERVATIONS:
        merged.sort(key=lambda o: o.get("last_updated", ""), reverse=True)
        merged = merged[:MAX_SHARED_OBSERVATIONS]
    return merged


def run_reflection(portfolio_id: str, regime: str,
                   recent_trades: List[Dict[str, Any]]) -> bool:
    """Run one reflection cycle. Returns True if the memory was updated."""
    if not recent_trades:
        return False
    client = get_ai_client()
    if client is None:
        return False

    from recent_trades import format_clustered_history_block, format_trade_history_block

    portfolio_obs = read_observations(portfolio_id)
    shared_obs = read_shared_observations()
    clustered = format_clustered_history_block(recent_trades)
    detailed = format_trade_history_block(recent_trades)

    prompt = build_reflection_prompt(
        portfolio_id=portfolio_id, regime=regime,
        portfolio_observations=portfolio_obs, shared_observations=shared_obs,
        clustered_history=clustered, per_trade_history=detailed,
    )

    try:
        response = client.messages.create(
            model=_REFLECTION_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
            timeout=TIMEOUT_SECONDS,
        )
        text = response.content[0].text if response.content else ""
    except Exception as e:
        print(f"  [reflection] Claude call failed (non-fatal): {e}")
        return False

    ops = parse_reflection_response(text)
    if not any([ops["retire"], ops["update"], ops["add"], ops["add_shared"]]):
        print("  [reflection] No operations parsed (non-fatal)")
        return False

    now = datetime.utcnow().isoformat() + "Z"
    new_obs = apply_curation_operations(portfolio_obs, ops, now=now)
    write_observations(portfolio_id, new_obs)

    if ops["add_shared"]:
        new_shared = _apply_shared_operations(shared_obs, ops["add_shared"], portfolio_id, now)
        write_shared_observations(new_shared)

    print(f"  [reflection] curated {portfolio_id}: -{len(ops['retire'])} +{len(ops['add'])} "
          f"~{len(ops['update'])} shared+{len(ops['add_shared'])}")
    return True
