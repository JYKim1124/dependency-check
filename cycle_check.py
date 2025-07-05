import sys
from pathlib import Path
import re
import subprocess
import argparse
import logging
from typing import Dict, List, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# Patterns
STMT_INFO_HEADER = re.compile(r"^# Statement information")
STMT_INFO_PATTERN = re.compile(
    r"(S\d+)\s*\[\s*depth\s*=\s*(\d+)\s*,\s*iterators\s*=\s*\"([^\"]*)\"\s*\]"
)
EDGE_PATTERN = re.compile(
    r"\s*(S\d+)\s*->\s*(S\d+)"      
    r".*?ref\s*(\d+)->(\d+)"        
    r".*?var\s*(\w+)->\w+"           
)

def parse_statement_info(file: Path) -> Tuple[Dict[str, int], Dict[str, List[str]]]:
    stmt_depth: Dict[str, int] = {}
    stmt_iters: Dict[str, List[str]] = {}
    in_block = False

    with file.open() as fp:
        for line in fp:
            line = line.strip()
            if not in_block:
                if STMT_INFO_HEADER.match(line):
                    in_block = True
                continue
            if not line or line.startswith("#"):
                break
            m = STMT_INFO_PATTERN.match(line)
            if m:
                stmt, depth, iters = m.groups()
                stmt_depth[stmt] = int(depth)
                stmt_iters[stmt] = [it.strip() for it in iters.split(',')] if iters else []
    return stmt_depth, stmt_iters


def build_var_graphs(file: Path) -> Dict[str, Dict[str, List[str]]]:
    graphs: Dict[str, Dict[str, List[str]]] = {}
    with file.open() as fp:
        for line in fp:
            m = EDGE_PATTERN.search(line)

            if not m:
                continue

            src_stmt, tgt_stmt, src_ref, tgt_ref, var = m.groups()
            src = f"{src_stmt}_r{src_ref}_{var}"
            tgt = f"{tgt_stmt}_r{tgt_ref}_{var}"

            if var not in graphs:
                graphs[var] = {}

            g = graphs[var]
            g.setdefault(src, [])
            g.setdefault(tgt, [])

            if tgt not in g[src]:
                g[src].append(tgt)

    return graphs


def tarjans_scc(graph: Dict[str, List[str]]) -> List[List[str]]:
    index = 0
    stack: List[str] = []
    on_stack: set = set()
    indices: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    sccs: List[List[str]] = []

    def dfs(v: str):
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)

        for w in graph[v]:
            if w not in indices:
                dfs(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])

        if lowlink[v] == indices[v]:
            comp: List[str] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(comp)

    for node in graph:
        if node not in indices:
            dfs(node)
    return sccs


def build_cycle_matrix(
    graph: Dict[str, List[str]],
    stmt_depth: Dict[str, int],
    stmt_iters: Dict[str, List[str]],
) -> Tuple[np.ndarray, List[str]]:
    
    sccs = [c for c in tarjans_scc(graph) if len(c) > 1]
    nodes = sorted(graph.keys())
    n = len(nodes)
    M = np.full((n, n), fill_value=0, dtype=object)

    for comp in sccs:
        for u in comp:
            for v in comp:
                if u == v:
                    continue
                i, j = nodes.index(u), nodes.index(v)
                iters_u = set(stmt_iters.get(u.split('_')[0], []))
                iters_v = set(stmt_iters.get(v.split('_')[0], []))
                common = sorted(iters_u & iters_v)
                M[i, j] = ','.join(common) if common else '-'
    
    for i, u in enumerate(nodes):
        for j, v in enumerate(nodes):
            u_stmt = u.split('_')[0]
            v_stmt = v.split('_')[0]
            if i == j or stmt_depth.get(u_stmt) == stmt_depth.get(v_stmt):
                M[i, j] = -1


    return M, nodes


def run_command(cmd: List[str], description: str) -> None:
    logger.info("%s: %s", description, ' '.join(cmd))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info("-> %s 성공!", description)
    except FileNotFoundError:
        logger.error("에러: '%s' 명령을 찾을 수 없습니다.", cmd[0])
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logger.error("에러: %s 실패.\n%s", description, e.stderr.strip())
        sys.exit(1)


def main(source: Path) -> None:
    if not source.exists():
        logger.error("입력 파일 '%s'을 찾을 수 없습니다.", source)
        sys.exit(1)

    scop = source.with_suffix(source.suffix + ".scop")
    candl = source.with_suffix(source.suffix + ".candl")

    run_command(["../clan/clan", str(source), "-o", str(scop)], "Clan 실행")
    run_command(["../candl/candl", str(scop), "-o", str(candl)], "Candl 실행")

    var_graphs = build_var_graphs(candl)
    stmt_depth, stmt_iters = parse_statement_info(candl)

    for var, graph in var_graphs.items():
        M, nodes = build_cycle_matrix(graph, stmt_depth, stmt_iters)
        print(f"\n--- Variable '{var}' ---")
        header = "      " + " ".join(f"{node:>10}" for node in nodes)
        print(header)
        for i, row in enumerate(M):
            row_str = " ".join(f"{str(cell):>10}" for cell in row)
            print(f"{nodes[i]:>6} {row_str}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cycle dependency checker")
    parser.add_argument("source_file", type=Path, help="소스 파일 경로")
    args = parser.parse_args()
    main(args.source_file)
