# -*- coding: utf-8 -*-
"""一次性：去掉已生成数据中 概念 字段的标号"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
JSON_PATH = BASE / "表中存在的图片数据.json"
CSV_PATH = BASE / "表中存在的图片数据.csv"

def strip_concept_number(concept):
    if not concept or not isinstance(concept, str):
        return concept
    s = concept.strip()
    while True:
        s2 = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", s)
        if s2 != s:
            s = s2
            continue
        s2 = re.sub(r"^[一二三四五六七八九十百千]+、\s*", "", s)
        if s2 != s:
            s = s2
            continue
        break
    return s.strip()

def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    for item in data.get("表中存在的图片列表", []):
        if "概念" in item:
            item["概念"] = strip_concept_number(item["概念"])
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("已更新 JSON:", JSON_PATH)

    if CSV_PATH.exists():
        import pandas as pd
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
        if "概念" in df.columns:
            df["概念"] = df["概念"].map(lambda x: strip_concept_number(x) if pd.notna(x) and isinstance(x, str) else x)
            df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
        print("已更新 CSV:", CSV_PATH)

if __name__ == "__main__":
    main()
