import sys
import os
import re
import subprocess
import argparse
import pandas as pd

def build_var_graphs(input_file):
    pattern = re.compile(
        r'\s*(S\d+)\s*->\s*(S\d+)'      
        r'.*?ref\s*(\d+)->(\d+)'        
        r'.*?var\s*(\w+)->\w+'           
    )

    var_graphs = {}

    try:
        with open(input_file, 'r') as f:
            for line in f:
                m = pattern.search(line)
                if not m:
                    continue

                src_stmt, tgt_stmt, src_ref, tgt_ref, var = m.groups()

                src_node = f"{src_stmt}_r{src_ref}_{var}"
                tgt_node = f"{tgt_stmt}_r{tgt_ref}_{var}"

                if var not in var_graphs:
                    var_graphs[var] = {}
                g = var_graphs[var]
                if src_node not in g:
                    g[src_node] = []
                if tgt_node not in g:
                    g[tgt_node] = []

                if tgt_node not in g[src_node]:
                    g[src_node].append(tgt_node)

    except FileNotFoundError:
        print(f">> 에러: '{input_file}' 파일을 찾을 수 없습니다!")
        return None

    return var_graphs


def main(input_file):
    if not os.path.exists(input_file):
        print(f"에러: 입력 파일 '{input_file}'을 찾을 수 없습니다.")
        sys.exit(1)

    base_name = input_file 
    scop_file = base_name + ".scop"
    candl_file = base_name + ".candl"
    
    try:
        print(f"[1/3] clan 실행: {input_file} -> {scop_file}")
        clan_command = ["../clan/clan", input_file, "-o", scop_file]
        print(*clan_command)
        subprocess.run(clan_command, check=True, capture_output=True, text=True)
        print(" -> clan 실행 성공!")
    except FileNotFoundError:
        print("에러: 'clan' 명령을 찾을 수 없습니다.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"에러: clan 실행 실패.\n{e.stderr}")
        sys.exit(1)

    try:
        print(f"[2/3] candl 실행: {input_file} -> {scop_file}")
        candl_command = ["../candl/candl", scop_file, "-o", candl_file]
        subprocess.run(candl_command, check=True, capture_output=True, text=True)
        print(" -> candl 실행 성공!")
    except FileNotFoundError:
        print("에러: 'candl' 명령을 찾을 수 없습니다.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"에러: candl 실행 실패.\n{e.stderr}")

    print(f"[3/3] 사이클 분석 중: {candl_file}")
    dependency_graph = build_var_graphs(candl_file)
    for x in dependency_graph:
        print(x, dependency_graph[x])


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="cycle 탐지기"
    )
    parser.add_argument("source_file")
    
    args = parser.parse_args()
    
    main(args.source_file)

