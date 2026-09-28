"""Flask wiring for the city scan, mirroring site_scan.register_site_scan."""
import datetime

from flask import jsonify, request

from models import CityAnalysis, db

from . import grid, pipeline

CACHE_DAYS = 30
# A city scan makes many upstream calls, so it is rate limited harder than a
# site scan and always served from the database when a fresh copy exists.
RATE_LIMIT = "10 per hour"
LAYERS = {
    "population": ("population", "tier"),
    "consumption": ("kwh_day", "residential_kwh_day", "population", "tier"),
    "industry": ("industrial_kwh_day", "industrial_sites", "industrial_sqm"),
    "emissions": ("co2e_t", "emitter_count"),
    "score": ("score", "rank", "kwh_day", "population", "tier"),
}


def _fresh(city_name, cell_size_m):
    cutoff = datetime.datetime.utcnow()
    return (CityAnalysis.query
            .filter(CityAnalysis.name.ilike(city_name),
                    CityAnalysis.cell_size_m == cell_size_m,
                    CityAnalysis.expires_at > cutoff)
            .order_by(CityAnalysis.created_at.desc())
            .first())


def _store(result):
    row = CityAnalysis(
        name=result["city"]["name"],
        display_name=result["city"]["display_name"][:512],
        country_code=(result["city"]["country_code"] or "")[:2],
        lat=result["city"]["lat"], lon=result["city"]["lon"],
        bbox=result["city"]["bbox"],
        cell_size_m=result["cell_size_m"],
        tier=result["tier"],
        status="complete" if not result["failed_layers"] else "partial",
        summary_json=pipeline.summary(result),
        cells_json=result["cells"],
        sources_json=result["sources"],
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(days=CACHE_DAYS),
    )
    db.session.add(row)
    db.session.commit()
    return row


def _row_payload(row, cached):
    return {"id": row.id, "cached": cached, "status": row.status,
            "tier": row.tier, "cell_size_m": row.cell_size_m,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            **row.summary_json}


def register_city_scan(app, cache=None, limiter=None):
    """Attach the /api/city-scan endpoints to an existing Flask app."""

    @app.route("/api/city-scan", methods=["POST"])
    def city_scan_endpoint():
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        lat, lon = body.get("lat"), body.get("lon")
        if not name and (lat is None or lon is None):
            return jsonify({"error": "name, or lat and lon, are required"}), 400
        try:
            cell_m = int(body.get("cell_size_m", 1000))
        except (TypeError, ValueError):
            cell_m = 1000
        cell_m = max(250, min(cell_m, 5000))

        if name and not body.get("refresh"):
            row = _fresh(name, cell_m)
            if row:
                return jsonify(_row_payload(row, cached=True))

        try:
            result = pipeline.analyze_city(name=name or None, lat=lat, lon=lon,
                                           cell_m=cell_m)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 404

        row = _store(result)
        return jsonify(_row_payload(row, cached=False)), 201

    @app.route("/api/city-scan/<int:analysis_id>")
    def city_scan_detail(analysis_id):
        row = db.session.get(CityAnalysis, analysis_id)
        if row is None:
            return jsonify({"error": "Not found"}), 404
        return jsonify(_row_payload(row, cached=True))

    @app.route("/api/city-scan/<int:analysis_id>/layers/<layer>")
    def city_scan_layer(analysis_id, layer):
        """One layer as GeoJSON, for a Leaflet overlay."""
        if layer not in LAYERS:
            return jsonify({"error": f"Unknown layer. Try: {', '.join(LAYERS)}"}), 400
        row = db.session.get(CityAnalysis, analysis_id)
        if row is None:
            return jsonify({"error": "Not found"}), 404

        cells = row.cells_json or []
        if layer == "score":
            # Only the ranked candidates, not every cell.
            ranked = [c for c in cells if c.get("rank")]
            cells = sorted(ranked, key=lambda c: c["rank"])
        elif layer == "industry":
            cells = [c for c in cells if c.get("industrial_sites")]
        elif layer == "emissions":
            cells = [c for c in cells if c.get("emitter_count")]

        payload = grid.to_geojson(cells, LAYERS[layer])
        payload["properties"] = {
            "layer": layer, "tier": row.tier, "cell_size_m": row.cell_size_m,
            "city": row.name,
            "sources": row.sources_json,
        }
        return jsonify(payload)

    @app.route("/api/city-scan/<int:analysis_id>/points/<kind>")
    def city_scan_points(analysis_id, kind):
        """Individual industrial sites or emitting facilities, not grid cells."""
        row = db.session.get(CityAnalysis, analysis_id)
        if row is None:
            return jsonify({"error": "Not found"}), 404
        summary = row.summary_json or {}
        if kind == "industry":
            items = (summary.get("industry") or {}).get("top_sites", [])
        elif kind == "emitters":
            items = (summary.get("emissions") or {}).get("top_sources", [])
        else:
            return jsonify({"error": "Unknown kind. Try: industry, emitters"}), 400
        return jsonify({"kind": kind, "count": len(items), "items": items})

    if limiter is not None:
        limiter.limit(RATE_LIMIT)(city_scan_endpoint)
    return app
