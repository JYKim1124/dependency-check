import sys
import os
import re
import subprocess
import argparse
import pandas as pd

def build_graph_structure(input_file):
    graph = {}
    dot_pattern = re.compile(r'\s*(S\d+)\s*->\s*(S\d+).*?ref\s*(\d+)->(\d+)')
    try:
        with open(input_file, 'r') as f:
            for line in f:
                match = dot_pattern.search(line)
                if match:
                    src_stmt, tgt_stmt, src_ref, tgt_ref = match.groups()
                    source_node = f"{src_stmt}_{src_ref}"
                    target_node = f"{tgt_stmt}_{tgt_ref}"
                    if source_node not in graph: graph[source_node] = []
                    if target_node not in graph: graph[target_node] = []
                    if target_node not in graph[source_node]:
                        graph[source_node].append(target_node)
    except FileNotFoundError:
        print(f">> 에러: '{input_file}' 파일을 찾을 수 없습니다!")
        return None
    return graph

def tarjan_scc(graph):
    sys.setrecursionlimit(10_000) 
    index, lowlink, stack, onstack, result = {}, {}, [], set(), []
    cur_index = 0

    def dfs(v):
        nonlocal cur_index
        index[v] = lowlink[v] = cur_index
        cur_index += 1
        stack.append(v)
        onstack.add(v)

        for w in graph.get(v, []):
            if w not in index:
                dfs(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in onstack:
                lowlink[v] = min(lowlink[v], index[w])
    
        if lowlink[v] == index[v]:
            comp = set()
            while True:
                w = stack.pop()
                onstack.remove(w)
                comp.add(w)
                if w == v: break
            result.append(comp)

    for node in graph:
        if node not in index:
            dfs(node)
    return result

def analyze_and_print_results(graph):
    sccs = tarjan_scc(graph)
    
    node_to_stmt = { node: node.split('_')[0] for node in graph }
    statements = sorted(set(node_to_stmt.values()), key=lambda s: int(s[1:]))
    m = len(statements)
    idx = { stmt:i for i,stmt in enumerate(statements) }
    stmt_cycle_mat = [ [0]*m for _ in range(m) ]
    cycles_found = []

    for comp in sccs:
        # 컴포넌트의 크기가 1이고 자기 자신으로의 엣지가 없는 경우는 사이클이 아님
        is_self_loop = len(comp) == 1 and list(comp)[0] in graph.get(list(comp)[0], [])
        if len(comp) > 1 or is_self_loop:
             stmts_in_comp = sorted(list(set(node_to_stmt[n] for n in comp)), key=lambda s: int(s[1:]))
             cycles_found.append(stmts_in_comp)
             for s1 in stmts_in_comp:
                for s2 in stmts_in_comp:
                    # SCC 내의 모든 노드 쌍은 서로에게 도달 가능하므로 사이클 관계
                    i, j = idx[s1], idx[s2]
                    stmt_cycle_mat[i][j] = 1

    if cycles_found:
        print("\n탐지된 사이클 그룹:")
        for i, cycle_group in enumerate(cycles_found, 1):
            print(f"사이클 그룹 #{i}: {', '.join(cycle_group)}")
    else:
        print("\n탐지된 사이클이 없습니다.")

    df = pd.DataFrame(stmt_cycle_mat, index=statements, columns=statements)
    print("\nCycle Matrix:")
    print(df)



def main(input_file):
    """주어진 소스 파일에 대해 clan -> candl -> cycle 분석 파이프라인을 실행합니다."""
    
    if not os.path.exists(input_file):
        print(f"에러: 입력 파일 '{input_file}'을 찾을 수 없습니다.")
        sys.exit(1)

    base_name = input_file
    scop_file = base_name + ".scop"
    candl_file = base_name + ".candl"
    
    try:
        print(f"[1/3] clan 실행 중: {input_file} -> {scop_file}")
        clan_command = ["clan", input_file, "-o", scop_file]
        subprocess.run(clan_command, check=True, capture_output=True, text=True)
        print(" -> clan 실행 성공!")
    except FileNotFoundError:
        print("에러: 'clan' 명령을 찾을 수 없습니다.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"에러: clan 실행 실패.\n{e.stderr}")
        sys.exit(1)

    try:
        print(f"[2/3] candl 실행 중: {scop_file} -> {candl_file}")
        candl_command = ["candl", scop_file]
        with open(candl_file, "w") as f_out:
            subprocess.run(candl_command, check=True, stdout=f_out, stderr=subprocess.PIPE, text=True)
        print(" -> candl 실행 성공!")
    except FileNotFoundError:
        print("에러: 'candl' 명령을 찾을 수 없습니다. PATH에 설치되어 있는지 확인하세요.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"에러: candl 실행 실패.\n{e.stderr}")
        sys.exit(1)

    print(f"[3/3] 사이클 분석 중: {candl_file}")
    dependency_graph = build_graph_structure(candl_file)
    analyze_and_print_results(dependency_graph)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="cycle 탐지기"
    )
    parser.add_argument("source_file")
    
    args = parser.parse_args()
    
    main(args.source_file)

