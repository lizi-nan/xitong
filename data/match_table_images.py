# -*- coding: utf-8 -*-
"""从实体关系表中找出各卷映射里存在的图片数据"""
import pandas as pd
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
EXCEL_PATH = BASE / "藏医系统与概念关系表.xlsx"
MAPPING_FILES = [
    "1juan_chinese_mapping.json", "1juan_tibetan_mapping.json",
    "2juan_chinese_mapping.json", "2juan_tibetan_mapping.json",
    "3juan_chinese_mapping.json", "3juan_tibetan_mapping.json",
    "5juan_chinese_mapping.json", "5juan_tibetan_mapping.json",
    "6juan_chinese_mapping.json", "6juan_tibetan_mapping.json",
]
OUTPUT_PATH = BASE / "表中存在的图片数据.json"
OUTPUT_CSV = BASE / "表中存在的图片数据.csv"
# 图片所在根目录，所有图片路径均相对于此
IMAGE_BASE = "切分图"

def load_excel_cell_values(path):
    """读取 Excel 所有单元格中的非空字符串，用于匹配"""
    xl = pd.ExcelFile(path)
    all_values = set()
    for sheet in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet, header=None)
        for _, row in df.iterrows():
            for v in row:
                if pd.notna(v) and isinstance(v, str) and v.strip():
                    all_values.add(v.strip())
                    # 也保留去除首尾空格后的多种规范化形式
                    all_values.add(v.strip().replace(" ", "").replace("　", ""))
    return all_values

def normalize_for_match(s):
    """规范化字符串便于匹配：去首尾空格、合并多余空格"""
    if not s or not isinstance(s, str):
        return ""
    return " ".join(s.split()).strip()

def strip_concept_number(concept):
    """去掉概念前的标号，如 5.1.1 、一、、2. 等"""
    if not concept or not isinstance(concept, str):
        return concept
    s = concept.strip()
    while True:
        # 去掉数字标号：5.1.1 、8.14 、6. 等
        s2 = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", s)
        if s2 != s:
            s = s2
            continue
        # 去掉中文序号：一、、二、、十一、 等
        s2 = re.sub(r"^[一二三四五六七八九十百千]+、\s*", "", s)
        if s2 != s:
            s = s2
            continue
        break
    return s.strip()

def load_all_mappings():
    """加载所有 JSON 映射 { 概念名: 图片路径 }"""
    mappings = {}
    for fname in MAPPING_FILES:
        path = BASE / fname
        if not path.exists():
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        mappings[fname] = data
    return mappings

def main():
    print("正在读取 Excel...")
    table_values = load_excel_cell_values(EXCEL_PATH)
    # 再建一个“规范化”集合：去掉所有空格后用于包含匹配
    table_normalized = {normalize_for_match(v): v for v in table_values}
    table_nospace = set()
    for v in table_values:
        n = v.replace(" ", "").replace("　", "")
        if n:
            table_nospace.add(n)

    print("正在加载各卷映射...")
    all_mappings = load_all_mappings()

    results = []  # list of { 卷/文件, 概念名, 图片路径, 匹配方式 }
    stats = {"by_file": {}, "total_matched": 0, "total_images": 0}

    for fname, mapping in all_mappings.items():
        matched = []
        for concept, img_path in mapping.items():
            stats["total_images"] += 1
            cn = normalize_for_match(concept)
            cn_nospace = concept.replace(" ", "").replace("　", "")
            found = False
            how = ""
            if concept in table_values or cn in table_values:
                found = True
                how = "exact"
            elif cn_nospace in table_nospace:
                found = True
                how = "exact_nospace"
            else:
                for tv in table_values:
                    if tv in concept or concept in tv:
                        found = True
                        how = "contains"
                        break
                    if cn_nospace and (cn_nospace in tv.replace(" ", "").replace("　", "") or tv.replace(" ", "").replace("　", "") in cn_nospace):
                        found = True
                        how = "contains_nospace"
                        break
            if found:
                concept_clean = strip_concept_number(concept)
                path_full = (IMAGE_BASE + "/" + img_path.lstrip("/")).replace("//", "/")
                matched.append({"概念": concept_clean, "图片路径": path_full, "匹配方式": how})
                results.append({"文件": fname, "概念": concept_clean, "图片路径": path_full, "匹配方式": how})
        stats["by_file"][fname] = len(matched)
        stats["total_matched"] += len(matched)

    # 去重后的图片路径列表
    unique_images = list({r["图片路径"] for r in results})
    out_data = {
        "统计": stats,
        "去重后图片数量": len(unique_images),
        "表中存在的图片列表": results,
        "表中存在的图片路径(去重)": sorted(unique_images),
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)

    # 输出 CSV 便于查看
    if results:
        df_out = pd.DataFrame(results)
        df_out.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print("统计:", json.dumps(stats, ensure_ascii=False, indent=2))
    print("去重后图片数:", len(unique_images))
    print("结果已写入:", OUTPUT_PATH, "和", OUTPUT_CSV)
    return out_data

if __name__ == "__main__":
    main()
