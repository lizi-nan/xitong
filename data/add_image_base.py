# -*- coding: utf-8 -*-
"""一次性：为 图片路径 加上 切分图 前缀"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
IMAGE_BASE = "切分图"
JSON_PATH = BASE / "表中存在的图片数据.json"
CSV_PATH = BASE / "表中存在的图片数据.csv"

def add_base(path_str):
    if not path_str or path_str.startswith(IMAGE_BASE):
        return path_str
    return (IMAGE_BASE + "/" + path_str.lstrip("/")).replace("//", "/")

def main():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    for item in data.get("表中存在的图片列表", []):
        if "图片路径" in item:
            item["图片路径"] = add_base(item["图片路径"])
    data["表中存在的图片路径(去重)"] = [add_base(p) for p in data.get("表中存在的图片路径(去重)", [])]
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("已更新 JSON:", JSON_PATH)

    if CSV_PATH.exists():
        import pandas as pd
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
        if "图片路径" in df.columns:
            df["图片路径"] = df["图片路径"].map(add_base)
            df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")
        print("已更新 CSV:", CSV_PATH)

if __name__ == "__main__":
    main()
