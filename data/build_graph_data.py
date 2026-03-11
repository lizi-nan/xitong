# -*- coding: utf-8 -*-
"""构建知识图谱数据：节点与边（含描述、翻译、Excel关系）"""
import pandas as pd
import json
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent
EXCEL_PATH = BASE / "藏医系统与概念关系表.xlsx"
IMAGE_DATA_PATH = BASE / "表中存在的图片数据.json"
OUTPUT_PATH = BASE / "knowledge_graph.json"

def normalize_id(s):
    if not s or (isinstance(s, float) and pd.isna(s)):
        return None
    return str(s).strip()

def build_graph():
    # 1. 读取 Excel 实体关系（列顺序：实体1, 藏文实体1, 实体1标签, 藏文1标签, 关系类型, 藏文关系, 实体2, 藏文实体2, 实体2标签, 藏文2标签）
    df = pd.read_excel(EXCEL_PATH, sheet_name=0, header=0)
    cols = list(df.columns)
    e1 = cols[0] if len(cols) > 0 else None
    tib1 = cols[1] if len(cols) > 1 else None
    rel_col = cols[4] if len(cols) > 4 else None
    e2 = cols[6] if len(cols) > 6 else None
    tib2 = cols[7] if len(cols) > 7 else None

    nodes_set = {}   # id -> { id, label, type, imageUrl? }
    edges_list = []  # [ { source, target, relation }, ... ]

    def add_node(nid, label, ntype="concept_ch", image_url=None):
        if not nid:
            return
        nid = str(nid)
        if nid not in nodes_set:
            node = {"id": nid, "label": label or nid, "type": ntype}
            if image_url:
                node["imageUrl"] = image_url
            nodes_set[nid] = node

    for _, row in df.iterrows():
        ent1 = normalize_id(row.get(e1))
        ent2 = normalize_id(row.get(e2))
        rel = normalize_id(row.get(rel_col)) or "相关"
        if ent1:
            add_node(ent1, ent1, "concept_ch")
        if ent2:
            add_node(ent2, ent2, "concept_ch")
        if tib1 is not None:
            t1 = normalize_id(row.get(tib1))
            if t1:
                add_node("tib_" + t1, t1, "concept_tib")
                if ent1:
                    edges_list.append({"source": ent1, "target": "tib_" + t1, "relation": "翻译"})
        if tib2 is not None:
            t2 = normalize_id(row.get(tib2))
            if t2:
                add_node("tib_" + t2, t2, "concept_tib")
                if ent2:
                    edges_list.append({"source": ent2, "target": "tib_" + t2, "relation": "翻译"})
        if ent1 and ent2:
            edges_list.append({"source": ent1, "target": ent2, "relation": rel})

    # 2. 读取图片数据：概念-图片 描述关系，以及同图汉藏翻译对
    with open(IMAGE_DATA_PATH, "r", encoding="utf-8") as f:
        img_data = json.load(f)
    list_items = img_data.get("表中存在的图片列表", [])

    # 按图片路径分组，得到同一图下的汉/藏概念
    by_image = defaultdict(list)  # image_path -> [ {概念, 文件} ]
    for item in list_items:
        concept = (item.get("概念") or "").strip()
        path = (item.get("图片路径") or "").strip()
        fname = item.get("文件", "")
        if not concept or not path:
            continue
        is_tibetan = "tibetan" in fname.lower()
        by_image[path].append({"concept": concept, "file": fname, "tibetan": is_tibetan})

    for path, items in by_image.items():
        img_id = "img_" + path.replace("/", "_").replace(" ", "_")
        add_node(img_id, path.split("/")[-1][:20], "image", image_url="/" + path)
        concepts_ch = [x["concept"] for x in items if not x["tibetan"]]
        concepts_tib = [x["concept"] for x in items if x["tibetan"]]
        for c in concepts_ch:
            add_node(c, c, "concept_ch")
            edges_list.append({"source": c, "target": img_id, "relation": "描述"})
        for c in concepts_tib:
            tid = "tib_" + c
            add_node(tid, c, "concept_tib")
            edges_list.append({"source": tid, "target": img_id, "relation": "描述"})
        # 汉-藏 翻译：同图下的汉语概念与藏语概念两两翻译（简化：取第一个汉、第一个藏）
        if concepts_ch and concepts_tib:
            for ch in concepts_ch[:3]:  # 限制边数量
                for tib in concepts_tib[:3]:
                    add_node(ch, ch, "concept_ch")
                    add_node("tib_" + tib, tib, "concept_tib")
                    edges_list.append({"source": ch, "target": "tib_" + tib, "relation": "翻译"})

    nodes_list = list(nodes_set.values())
    # 去重边
    seen_edges = set()
    unique_edges = []
    for e in edges_list:
        key = (e["source"], e["target"], e["relation"])
        if key not in seen_edges:
            seen_edges.add(key)
            unique_edges.append(e)

    graph = {"nodes": nodes_list, "edges": unique_edges}
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    print("节点数:", len(nodes_list), "边数:", len(unique_edges))
    print("已写入:", OUTPUT_PATH)
    return graph

if __name__ == "__main__":
    build_graph()
