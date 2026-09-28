"""Rank grid cells as microgrid candidates.

A good candidate has demand worth serving, people or industry to serve, roof to
put panels on, and ideally dirty supply to displace. Each input is normalised
to the best cell in this city, so scores compare places within one city and are
not a claim about how one city compares to another.

Weights are visible in the API response, because a ranking whose weights are
hidden is not reviewable.
"""
WEIGHTS = {
    "demand": 0.35,          # kWh/day: the load a microgrid would serve
    "population": 0.20,      # people: social benefit, and demand stability
    "industry": 0.25,        # industrial load: steady daytime demand, good for PV
    "emissions": 0.20,       # CO2e nearby: displacing dirtier supply
}


def _normalise(cells, key):
    top = max((c.get(key, 0.0) or 0.0) for c in cells) if cells else 0.0
    if top <= 0:
        return {c["id"]: 0.0 for c in cells}
    return {c["id"]: (c.get(key, 0.0) or 0.0) / top for c in cells}


def score_cells(cells, weights=None, top_n=20):
    """Add a 0-1 score and a breakdown to every cell; return the best ones."""
    w = {**WEIGHTS, **(weights or {})}
    total_weight = sum(w.values()) or 1.0

    norms = {
        "demand": _normalise(cells, "kwh_day"),
        "population": _normalise(cells, "population"),
        "industry": _normalise(cells, "industrial_kwh_day"),
        "emissions": _normalise(cells, "co2e_t"),
    }

    for cell in cells:
        parts = {k: round(norms[k][cell["id"]], 4) for k in norms}
        cell["score_parts"] = parts
        cell["score"] = round(
            sum(parts[k] * w[k] for k in parts) / total_weight, 4)

    ranked = sorted(cells, key=lambda c: -c["score"])[:top_n]
    for rank, cell in enumerate(ranked, 1):
        cell["rank"] = rank

    return {
        "weights": w,
        "top": [{
            "id": c["id"], "rank": c["rank"], "score": c["score"],
            "lat": c["lat"], "lon": c["lon"],
            "kwh_day": c.get("kwh_day", 0.0),
            "population": c.get("population", 0.0),
            "industrial_kwh_day": c.get("industrial_kwh_day", 0.0),
            "co2e_t": c.get("co2e_t", 0.0),
            "tier": c.get("tier"),
            "score_parts": c["score_parts"],
        } for c in ranked],
        "method": ("each input normalised against the highest cell in this city, "
                   "then weighted. Scores rank places within a city only"),
    }
