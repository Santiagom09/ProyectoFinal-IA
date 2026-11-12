"""Métrica Parte 1: nodos expandidos y optimalidad, A* vs Dijkstra vs BFS (todos los pares, 3 perfiles, hora pico y valle)."""

import itertools, sys, os, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.graph import NAMES, MODES
from core.search import astar, bfs, graph

G = graph()
rows = []
M = list(MODES)
for hour in (8, 13):
    for w in [(1, 0.2, 0.2), (0.3, 1, 0.3), (0.3, 0.3, 1)]:
        for o, d in itertools.permutations(NAMES, 2):
            a = astar(G, o, d, hour, w, M)
            u = astar(G, o, d, hour, w, M, use_h=False)
            b = bfs(G, o, d, hour, w, M)
            rows.append(
                dict(
                    astar=a["expanded"],
                    dijkstra=u["expanded"],
                    bfs=b["expanded"],
                    optimal=abs(a["cost"] - u["cost"]) < 1e-9,
                    bfs_gap=b["cost"] / u["cost"] - 1,
                )
            )
df = pd.DataFrame(rows)
print("Nodos expandidos (media):")
print(df[["astar", "dijkstra", "bfs"]].mean().round(2).to_string())
print(
    "A* igual al óptimo de Dijkstra en %.1f%% de %d casos"
    % (100 * df.optimal.mean(), len(df))
)
print("Sobrecosto medio de BFS vs óptimo: %.1f%%" % (100 * df.bfs_gap.mean()))
