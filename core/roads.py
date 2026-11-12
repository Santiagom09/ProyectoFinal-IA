"""Geometría real de calles (opcional). Si no hay grafo OSM descargado u osmnx no está instalado,
cae a línea recta. Para activarlo: pip install -r requirements-osm.txt && python scripts/download_osm.py
"""

import os
from functools import lru_cache

try:
    import osmnx as ox, networkx as nx
except Exception:
    ox = None
PATH = os.path.join(os.path.dirname(__file__), "..", "data", "valle_drive.graphml")
_G = None


def available():
    return ox is not None and os.path.exists(PATH)


@lru_cache(maxsize=4096)
def segment(a, b):
    """a, b = (lat, lon). Devuelve lista de (lat, lon) siguiendo las calles; línea recta si no hay datos."""
    global _G
    if not available():
        return [a, b]
    try:
        if _G is None:
            _G = ox.load_graphml(PATH)
        u, v = ox.distance.nearest_nodes(_G, [a[1], b[1]], [a[0], b[0]])
        path = nx.shortest_path(_G, u, v, weight="length")
        return [a] + [(_G.nodes[n]["y"], _G.nodes[n]["x"]) for n in path] + [b]
    except Exception:
        return [a, b]
