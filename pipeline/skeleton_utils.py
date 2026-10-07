"""Общие функции упрощения 3D-скелетов нейронов для веб-визуализации."""
import numpy as np

MIN_STEP_UM = 7.0     # узлы не ближе 7 мкм друг к другу
MIN_TWIG_UM = 25.0    # веточки короче 25 мкм отрезаются


def simplify_tree(xyz: np.ndarray, par: np.ndarray, min_step: float = MIN_STEP_UM, min_twig: float = MIN_TWIG_UM):
    """xyz (n,3) в мкм, par (n,) индекс родителя или -1. Возвращает упрощённые (xyz, par)."""
    n = len(xyz)
    children = [[] for _ in range(n)]
    for i, p in enumerate(par):
        if p >= 0:
            children[p].append(i)
    order = []
    stack = [i for i in range(n) if par[i] < 0]
    while stack:
        i = stack.pop(); order.append(i); stack.extend(children[i])
    seg = np.zeros(n)
    has = par >= 0
    seg[has] = np.linalg.norm(xyz[has] - xyz[par[has]], axis=1)
    cable = seg.copy()                       # длина кабеля поддерева
    for i in reversed(order):
        if par[i] >= 0:
            cable[par[i]] += cable[i]
    keep_node = (cable >= min_twig) | (par < 0)
    new_idx = -np.ones(n, int)
    out_xyz, out_par = [], []
    for i in order:
        if not keep_node[i]:
            continue
        p = par[i]
        while p >= 0 and new_idx[p] < 0:     # ближайший сохранённый предок
            p = par[p]
        kp = new_idx[p] if p >= 0 else -1
        branch = len([c for c in children[i] if keep_node[c]]) != 1
        far = kp < 0 or np.linalg.norm(xyz[i] - out_xyz[kp]) >= min_step
        if branch or far:
            new_idx[i] = len(out_xyz); out_xyz.append(xyz[i]); out_par.append(kp)
    return np.array(out_xyz, np.float32).reshape(-1, 3), np.array(out_par, np.int32)


def tree_from_edges(nv: int, edges: np.ndarray, root: int = 0) -> np.ndarray:
    """Неориентированные рёбра скелета -> массив родителей (обход в ширину от корня)."""
    adj = [[] for _ in range(nv)]
    for a, b in edges:
        adj[a].append(b); adj[b].append(a)
    par = np.full(nv, -2, np.int64)
    for start in [root] + list(range(nv)):     # несвязные куски получают собственные корни
        if par[start] != -2:
            continue
        par[start] = -1
        queue = [start]
        while queue:
            nxt = []
            for u in queue:
                for v in adj[u]:
                    if par[v] == -2:
                        par[v] = u; nxt.append(v)
            queue = nxt
    return par
