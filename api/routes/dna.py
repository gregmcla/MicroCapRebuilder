"""DNA Genome endpoints (Feature #16) — stated vs measured strategy DNA,
plus cross-portfolio PCA cluster map."""

from pathlib import Path

from fastapi import APIRouter, Depends, Query

from api.deps import validate_portfolio_id

from dna_genome import (
    AXES,
    compute_profile,
    compute_stated_dna,
    compute_measured_dna,
    compute_cluster_pca,
    profile_to_dict,
    DnaGenome,
)
from data_files import load_config


router = APIRouter(prefix="/api")


@router.get("/{portfolio_id}/dna")
def get_dna_profile(
    portfolio_id: str = Depends(validate_portfolio_id),
    window: str = Query(default="all", description='Window: "all" (full history) or "90" (last 90 days)'),
):
    """Return the full DnaProfile: stated + measured + per-axis drift."""
    config = load_config(portfolio_id)
    name = str(config.get("strategy", {}).get("name", portfolio_id) or portfolio_id)
    profile = compute_profile(portfolio_id, name, config, window=window)
    return profile_to_dict(profile)


@router.get("/{portfolio_id}/dna/stated")
def get_stated_dna(portfolio_id: str = Depends(validate_portfolio_id)):
    """Just the stated genome (config-only, instant)."""
    config = load_config(portfolio_id)
    from dataclasses import asdict
    return {"axes": AXES, "stated": asdict(compute_stated_dna(config))}


@router.get("/dna/cluster")
def get_dna_cluster(
    mode: str = Query(default="stated", description="stated | measured"),
    window: str = Query(default="all"),
):
    """Cross-portfolio 2D PCA scatter. Computes genomes for all active live
    portfolios, projects to 2D, returns labeled points + variance explained.
    """
    from portfolio_registry import list_portfolios

    portfolios = list_portfolios(active_only=True)
    genomes: dict[str, DnaGenome] = {}
    meta: dict[str, dict] = {}

    for p in portfolios:
        try:
            config = load_config(p.id)
        except Exception:
            continue
        if mode == "measured":
            g = compute_measured_dna(p.id, window=window)
        else:
            g = compute_stated_dna(config)
        genomes[p.id] = g
        meta[p.id] = {
            "name": p.name,
            "universe": p.universe,
            "paper_mode": False,  # active list filters paper-only out
        }

    pca = compute_cluster_pca(genomes)

    # Enrich each point with portfolio name + the raw genome for tooltip render
    from dataclasses import asdict
    enriched_points = []
    for pt in pca["portfolios"]:
        pid = pt["id"]
        enriched_points.append({
            **pt,
            "name": meta.get(pid, {}).get("name", pid),
            "genome": asdict(genomes[pid]),
        })

    return {
        "mode": mode,
        "window": window,
        "axes": AXES,
        "portfolios": enriched_points,
        "variance_explained": pca["variance_explained"],
        "axis_loadings": pca["axis_loadings"],
    }
