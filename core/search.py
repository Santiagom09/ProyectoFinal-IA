"""A*, Dijkstra y BFS implementados desde cero. Reportan nodos expandidos."""

import heapq, itertools, collections
from .graph import build_graph, edge_metrics, scalar_cost, haversine, MODES


def _result(found, goal, parent, expanded, w):
    if not found:
        return {"found": False, "expanded": expanded, "cost": float("inf")}
    edges = []
    n = goal
    while parent[n] is not None:
        p, mode, met, rt = parent[n]
        edges.append((p, n, mode, met, rt))
        n = p
    edges.reverse()
    tot = {k: sum(e[3][k] for e in edges) for k in ("min", "cop", "co2", "km")}
    return {
        "found": True,
        "expanded": expanded,
        "edges": edges,
        "totals": tot,
        "cost": scalar_cost(tot, w),
        "path": ([edges[0][0]] + [e[1] for e in edges]) if edges else [goal],
    }


def astar(adj, start, goal, hour, w, modes, use_h=True):
    """use_h=False equivale a Dijkstra/UCS. h admisible y consistente:
    tiempo mínimo en línea recta a la velocidad máxima libre (w_time * d / v_max)."""
    vmax = max(MODES[m]["speed"] for m in modes)
    h = (lambda n: w[0] * haversine(n, goal) / vmax * 60) if use_h else (lambda n: 0)
    cnt = itertools.count()
    g = {start: 0}
    parent = {start: None}
    closed = set()
    expanded = 0
    pq = [(h(start), next(cnt), start)]
    while pq:
        _, _, n = heapq.heappop(pq)
        if n in closed:
            continue
        closed.add(n)
        expanded += 1
        if n == goal:
            return _result(True, goal, parent, expanded, w)
        for nb, mode, d, rt in adj[n]:
            if mode not in modes:
                continue
            ng = g[n] + scalar_cost(edge_metrics(mode, d, hour), w)
            if ng < g.get(nb, float("inf")):
                g[nb] = ng
                parent[nb] = (n, mode, edge_metrics(mode, d, hour), rt)
                heapq.heappush(pq, (ng + h(nb), next(cnt), nb))
    return _result(False, goal, parent, expanded, w)


def bfs(adj, start, goal, hour, w, modes):
    """Minimiza número de tramos (ignora costos); luego se evalúa su costo real."""
    q = collections.deque([start])
    parent = {start: None}
    expanded = 0
    while q:
        n = q.popleft()
        expanded += 1
        if n == goal:
            return _result(True, goal, parent, expanded, w)
        for nb, mode, d, rt in adj[n]:
            if mode in modes and nb not in parent:
                parent[nb] = (n, mode, edge_metrics(mode, d, hour), rt)
                q.append(nb)
    return _result(False, goal, parent, expanded, w)


_G = build_graph()


def graph():
    return _G


def legs(edges):
    """Agrupa tramos consecutivos con el mismo modo y ruta: [{mode, route, stops, min, cop, co2, km}]."""
    out = []
    for a, b, mode, met, rt in edges:
        if out and out[-1]["mode"] == mode and out[-1]["route"] == rt:
            L = out[-1]
            L["stops"].append(b)
            for k in ("min", "cop", "co2", "km"):
                L[k] += met[k]
        else:
            out.append(
                {
                    "mode": mode,
                    "route": rt,
                    "stops": [a, b],
                    **{k: met[k] for k in ("min", "cop", "co2", "km")},
                }
            )
    return out
