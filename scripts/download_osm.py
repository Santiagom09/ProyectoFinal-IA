"""Descarga la red vial del Valle de Aburrá (puede tardar varios minutos y requiere internet)."""

import os, osmnx as ox

west, south, east, north = -75.66, 6.10, -75.50, 6.40
G = ox.graph_from_bbox((west, south, east, north), network_type="drive")
out = os.path.join(os.path.dirname(__file__), "..", "data", "valle_drive.graphml")
ox.save_graphml(G, out)
print("Guardado en", out, "-", len(G.nodes), "nodos")
