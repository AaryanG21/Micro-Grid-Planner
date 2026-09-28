"""Region-specific official data, keyed by country and state.

Global sources give every city an estimate. Official data exists only where a
regulator publishes it, and in a different shape each time, so each region gets
its own module and registers here. Adding MESCOM, or Maharashtra, or Kenya,
means adding a module - never touching the pipeline.
"""
from . import karnataka

# (country ISO2, state or None) -> module exposing official_total(city)
REGISTRY = {
    ("IN", "Karnataka"): karnataka,
}


def lookup(country_code, state=None):
    """The regional module covering this place, or None."""
    return (REGISTRY.get((country_code, state))
            or REGISTRY.get((country_code, None)))
