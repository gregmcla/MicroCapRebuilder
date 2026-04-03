#!/usr/bin/env python3
"""
Migrate all portfolios to screener-based universe system.
gov-infra is already done — skip it.
"""

import json
from pathlib import Path

PORTFOLIOS_DIR = Path("/Users/gregmclaughlin/MicroCapRebuilder/data/portfolios")

# Market cap values (in millions from config) → convert to absolute dollars
# max_market_cap_m of 999999 or None = no upper limit → use None in screener
def m_to_abs(val_m):
    """Convert market cap in millions to absolute dollars. None/999999 = no limit."""
    if val_m is None or val_m >= 999999:
        return None
    return int(val_m * 1_000_000)

# Portfolio configs: (screener_block, ai_refinement_block or None)
# screener_block: dict with enabled, optionally sectors/industries, market_cap_min, market_cap_max, region
# Market cap mins/maxes derived from universe.filters above

PORTFOLIO_CONFIGS = {
    "2-day-max-alpha-blitz": {
        # min: 50M, max: unlimited → 50_000_000, no upper
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "2-day-maximum-aggression": {
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "adjacent-supporters-of-ai": {
        # min: 500M, max: unlimited
        "screener": {
            "enabled": True,
            "sectors": ["Industrials", "Utilities", "Energy", "Technology"],
            "industries": [
                "Electrical Equipment & Parts",
                "Specialty Industrial Machinery",
                "Utilities - Regulated Electric",
                "Utilities - Independent Power Producers",
                "Solar",
                "Semiconductor Equipment & Materials"
            ],
            "market_cap_min": 500_000_000,
            "region": "us"
        },
        "ai_refinement": {
            "enabled": True,
            "prompt": "Select companies in the physical infrastructure layer that enables AI — power generation, grid infrastructure, cooling systems, data center construction, electrical components. Exclude pure software, cloud services, and chip designers."
        }
    },
    "ai-pickaxe-infrastructure": {
        # min: 50M, max: unlimited
        "screener": {
            "enabled": True,
            "sectors": ["Industrials", "Utilities", "Technology", "Real Estate"],
            "industries": [
                "Electrical Equipment & Parts",
                "Specialty Industrial Machinery",
                "Utilities - Independent Power Producers",
                "REIT - Specialty",
                "Semiconductor Equipment & Materials",
                "Electronic Components"
            ],
            "market_cap_min": 50_000_000,
            "region": "us"
        },
        "ai_refinement": {
            "enabled": True,
            "prompt": "Select companies that physically build AI infrastructure — data center REITs, power suppliers, cooling companies, fiber/network builders, semiconductor equipment. Exclude AI software, SaaS, and chip designers."
        }
    },
    "asymmetric-catalyst-hunters": {
        # min: 50M, max: 2000M → 2_000_000_000
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "market_cap_max": 2_000_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "asymmetric-microcap-compounder": {
        # min: 50M, max: 2000M
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "market_cap_max": 2_000_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "boomers": {
        # min: 50M, max: unlimited
        "screener": {
            "enabled": True,
            "sectors": ["Healthcare", "Real Estate", "Consumer Defensive"],
            "industries": [
                "Medical Devices",
                "Health Information Services",
                "Medical Care Facilities",
                "REIT - Healthcare Facilities",
                "Drug Manufacturers - Specialty & Generic",
                "Household & Personal Products",
                "Pharmaceutical Retailers"
            ],
            "market_cap_min": 50_000_000,
            "region": "us"
        },
        "ai_refinement": {
            "enabled": True,
            "prompt": "Select companies that directly profit from aging baby boomers — Medicare Advantage plans, senior housing, cardiac/orthopedic devices, home health, funeral services, hearing aids, elder care technology. Exclude pediatric, biotech R&D, and general hospitals."
        }
    },
    "cash-cow-compounders": {
        # min: 10000M → 10_000_000_000, max: unlimited
        "screener": {
            "enabled": True,
            "sectors": ["Industrials", "Financial Services", "Consumer Defensive", "Utilities"],
            "industries": [
                "Waste Management",
                "Railroads",
                "Insurance - Specialty",
                "Insurance - Property & Casualty",
                "Packaging & Containers",
                "Beverages - Non-Alcoholic",
                "Tobacco",
                "Integrated Freight & Logistics"
            ],
            "market_cap_min": 10_000_000_000,
            "region": "us"
        },
        "ai_refinement": {
            "enabled": True,
            "prompt": "Select boring, cash-generating companies with wide moats — waste haulers, railroads, title insurers, toll roads, consumer staples with pricing power. Exclude high-growth, unprofitable, or cyclical companies."
        }
    },
    "catalyst-momentum-scalper": {
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "defense-tech": {
        # min: 500M, max: None (no upper in config)
        "screener": {
            "enabled": True,
            "sectors": ["Industrials", "Technology"],
            "industries": [
                "Aerospace & Defense",
                "Security & Protection Services",
                "Specialty Industrial Machinery",
                "Scientific & Technical Instruments"
            ],
            "market_cap_min": 500_000_000,
            "region": "us"
        },
        "ai_refinement": {
            "enabled": True,
            "prompt": "Select defense technology and autonomous systems companies — drones, autonomous vehicles, cybersecurity for defense, space systems, directed energy, electronic warfare, defense AI. Exclude legacy defense primes focused on ships/tanks unless they have significant autonomous systems divisions."
        }
    },
    "diversified-all-cap-core": {
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "diversified-healthcare": {
        "screener": {
            "enabled": True,
            "sectors": ["Healthcare"],
            "market_cap_min": 50_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "high-conviction-compounders": {
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "max": {
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "microcap": {
        # min: 300M, max: 50000M → 50_000_000_000
        "screener": {
            "enabled": True,
            "market_cap_min": 300_000_000,
            "market_cap_max": 50_000_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "microcap-momentum-compounder": {
        # min: 50M, max: 2000M
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "market_cap_max": 2_000_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "momentum-scalper": {
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "pre-earnings-momentum": {
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "quality-momentum-growth": {
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "sector-momentum-rotation": {
        # min: 10000M, max: unlimited
        "screener": {
            "enabled": True,
            "market_cap_min": 10_000_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "tariff-moat-industrials": {
        # min: 300M, max: 5000M → 5_000_000_000
        "screener": {
            "enabled": True,
            "sectors": ["Industrials", "Basic Materials", "Consumer Cyclical"],
            "industries": [
                "Metal Fabrication",
                "Steel",
                "Building Products & Equipment",
                "Specialty Industrial Machinery",
                "Auto Parts",
                "Textile Manufacturing",
                "Packaging & Containers"
            ],
            "market_cap_min": 300_000_000,
            "market_cap_max": 5_000_000_000,
            "region": "us"
        },
        "ai_refinement": {
            "enabled": True,
            "prompt": "Select small and micro-cap US manufacturers and industrial companies that benefit from tariffs and trade protection — companies whose domestic competitors are shielded from cheap imports. Exclude importers, companies with heavy overseas manufacturing, and large multinationals."
        }
    },
    "test-auto-scan-delete-me": {
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "market_cap_max": 2_000_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "vcx-ai-concentration": {
        # min: 0, max: None → no limits
        "screener": {
            "enabled": True,
            "market_cap_min": 0,
            "region": "us"
        },
        "ai_refinement": None
    },
    "yolo-degen-momentum": {
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
    "yolo-momentum-chaos": {
        "screener": {
            "enabled": True,
            "market_cap_min": 50_000_000,
            "region": "us"
        },
        "ai_refinement": None
    },
}

SKIP = {"gov-infra"}

def migrate_portfolio(portfolio_id: str, screener_cfg: dict, ai_refinement_cfg):
    config_path = PORTFOLIOS_DIR / portfolio_id / "config.json"
    if not config_path.exists():
        print(f"  SKIP {portfolio_id}: config.json not found")
        return False

    with open(config_path) as f:
        config = json.load(f)

    sources = config.setdefault("universe", {}).setdefault("sources", {})

    # Disable etf_holdings
    if "etf_holdings" in sources:
        sources["etf_holdings"]["enabled"] = False
    else:
        sources["etf_holdings"] = {"enabled": False}

    # Add screener block
    sources["screener"] = screener_cfg

    # Add or remove ai_refinement block
    if ai_refinement_cfg is not None:
        sources["ai_refinement"] = ai_refinement_cfg
    else:
        # Remove it if it was there from a previous run
        sources.pop("ai_refinement", None)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return True


def validate_portfolio(portfolio_id: str):
    config_path = PORTFOLIOS_DIR / portfolio_id / "config.json"
    try:
        with open(config_path) as f:
            config = json.load(f)
        sources = config.get("universe", {}).get("sources", {})
        assert "screener" in sources, "missing screener key"
        assert sources["screener"].get("enabled") is True, "screener not enabled"
        etf = sources.get("etf_holdings", {})
        assert etf.get("enabled") is False, "etf_holdings still enabled"
        return True
    except Exception as e:
        print(f"  VALIDATION FAILED {portfolio_id}: {e}")
        return False


def main():
    print(f"Migrating {len(PORTFOLIO_CONFIGS)} portfolios...\n")
    ok = 0
    fail = 0

    for pid, cfg in PORTFOLIO_CONFIGS.items():
        if pid in SKIP:
            print(f"  SKIP {pid} (already done)")
            continue

        success = migrate_portfolio(pid, cfg["screener"], cfg["ai_refinement"])
        if success:
            valid = validate_portfolio(pid)
            if valid:
                ai_note = " + ai_refinement" if cfg["ai_refinement"] else ""
                sectors = cfg["screener"].get("sectors", [])
                sector_note = f" [{', '.join(sectors[:2])}{'...' if len(sectors) > 2 else ''}]" if sectors else " [all sectors]"
                print(f"  OK  {pid}{sector_note}{ai_note}")
                ok += 1
            else:
                fail += 1
        else:
            fail += 1

    print(f"\nDone: {ok} migrated, {fail} failed.")

    # Also print the gov-infra status
    gov_valid = validate_portfolio("gov-infra")
    print(f"gov-infra (reference): {'OK' if gov_valid else 'FAIL'}")


if __name__ == "__main__":
    main()
