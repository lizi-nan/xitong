# -*- coding: utf-8 -*-
"""多模态知识图谱系统：展示、问答、词云、用户管理"""
import os
import json
import socket
from pathlib import Path
from flask import Flask, send_from_directory, request, jsonify, render_template, redirect, url_for
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# 数据路径
BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
GRAPH_PATH = DATA_DIR / "knowledge_graph.json"
IMAGE_DATA_PATH = DATA_DIR / "表中存在的图片数据.json"
# 切分图静态目录：优先环境变量 CUT_IMAGE_ROOT，否则 项目/切分图 或 data/切分图
_env_root = os.environ.get("CUT_IMAGE_ROOT")
if _env_root:
    STATIC_IMAGE_BASE = Path(_env_root).resolve()
else:
    STATIC_IMAGE_BASE = BASE / "切分图"
    if not STATIC_IMAGE_BASE.exists():
        STATIC_IMAGE_BASE = DATA_DIR / "切分图"

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "tibetan-kg-secret-key-please-change")

# 简单用户存储（可改为 SQLite）
class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self._password_hash = password_hash
    def get_id(self):
        return str(self.id)
    def check_password(self, password):
        return check_password_hash(self._password_hash, password)

USERS_DB = {}  # id -> User
USERS_FILE = BASE / "data" / "users.json"

def load_users():
    global USERS_DB
    if USERS_FILE.exists():
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for u in data.get("users", []):
                USERS_DB[u["id"]] = User(u["id"], u["username"], u["password_hash"])
        except Exception:
            pass
    if not USERS_DB:
        # 默认管理员
        h = generate_password_hash("admin123")
        USERS_DB["1"] = User("1", "admin", h)
        save_users()

def save_users():
    data = {"users": []}
    for u in USERS_DB.values():
        data["users"].append({"id": u.id, "username": u.username, "password_hash": u._password_hash})
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

load_users()

login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return USERS_DB.get(str(user_id))

# 进入系统需先登录（登录、注册、静态资源除外）
@app.before_request
def require_login():
    if current_user.is_authenticated:
        return None
    if request.endpoint in ("login", "register", "static") or request.path.startswith("/static") or request.path.startswith("/切分图"):
        return None
    # API 请求返回 401 便于前端跳转登录
    if request.path.startswith("/api/"):
        return jsonify({"error": "请先登录", "login": url_for("login")}), 401
    return redirect(url_for("login", next=request.url))

# 占位图：可见的「暂无图片」SVG，图片缺失时显示
_PLACEHOLDER_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="150">'
    b'<rect width="200" height="150" fill="#21262d" stroke="#30363d" stroke-width="1"/>'
    b'<text x="100" y="78" text-anchor="middle" fill="#8b949e" font-size="14" font-family="sans-serif">\xe6\x9a\x82\xe6\x97\xa0\xe5\x9b\xbe\xe7\x89\x87</text>'
    b'</svg>'
)

# 切分图子目录：1juan2juan（第一、二卷）、3-5-6juan（第三、五、六卷）
_IMAGE_SUBDIRS = ["1juan2juan", "3-5-6juan"]

# 3-5-6juan 下实际为「第X卷_N/group_0000/图像_3.jpg」结构，数据里是「第X卷_N_group_0000/entity1_曼唐图像.jpg」
import re
_GROUP_PATTERN = re.compile(r"^(第.卷_\d+)_group_(\d+)/(.+)$")

def _resolve_image_path(base: Path, filename: str):
    """按多种实际目录/文件名尝试解析，返回 (directory, relative_path) 或 None"""
    # 1) 直接在 base 下
    if (base / filename).is_file():
        return (base, filename)
    # 2) 在 1juan2juan、3-5-6juan 下，原样路径
    for sub in _IMAGE_SUBDIRS:
        d = base / sub
        if (d / filename).is_file():
            return (d, filename)
    # 3) 3-5-6juan 下为「第X卷_N/group_0000/」且文件可能为 图像_3.jpg
    m = _GROUP_PATTERN.match(filename)
    if m:
        vol_prefix, group_num, rest = m.group(1), m.group(2), m.group(3)
        # 第X卷_N / group_0000 / 原文件名 或 图像_3.jpg
        alt_dir = f"{vol_prefix}/group_{group_num}"
        for sub in _IMAGE_SUBDIRS:
            d = base / sub
            for name in (rest, "图像_3.jpg"):
                candidate = f"{alt_dir}/{name}"
                if (d / candidate).is_file():
                    return (d, candidate)
    return None

@app.route("/切分图/<path:filename>")
def serve_cut_image(filename):
    base = Path(STATIC_IMAGE_BASE)
    resolved = _resolve_image_path(base, filename)
    if resolved:
        dir_path, rel_path = resolved
        return send_from_directory(dir_path, rel_path)
    from flask import Response
    return Response(_PLACEHOLDER_SVG, mimetype="image/svg+xml")

# 页面路由
@app.route("/")
def index():
    return redirect(url_for("graph_page"))

@app.route("/graph")
def graph_page():
    return render_template("graph.html")

@app.route("/qa")
def qa_page():
    return render_template("qa.html")

@app.route("/wordcloud")
def wordcloud_page():
    return render_template("wordcloud.html")

@app.route("/users")
@login_required
def users_page():
    return render_template("users.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    for u in USERS_DB.values():
        if u.username == username and u.check_password(password):
            login_user(u)
            return redirect(request.args.get("next") or url_for("index"))
    return render_template("login.html", error="用户名或密码错误")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    password2 = request.form.get("password2", "")
    if not username or not password:
        return render_template("register.html", error="请填写用户名和密码")
    if password != password2:
        return render_template("register.html", error="两次密码不一致")
    for u in USERS_DB.values():
        if u.username == username:
            return render_template("register.html", error="用户名已存在")
    new_id = str(max((int(k) for k in USERS_DB.keys() if k.isdigit()), default=0) + 1)
    USERS_DB[new_id] = User(new_id, username, generate_password_hash(password))
    save_users()
    login_user(USERS_DB[new_id])
    return redirect(url_for("index"))

# API（需登录后访问）
def _image_file_exists(image_url: str) -> bool:
    """判断 imageUrl 对应的切分图文件是否真实存在（不存在则返回 False，用于过滤「暂无图片」）"""
    if not image_url or not image_url.strip():
        return False
    path = image_url.strip().lstrip("/")
    if path.startswith("切分图/"):
        path = path[3:].lstrip("/")  # 去掉前缀 切分图/
    return _resolve_image_path(Path(STATIC_IMAGE_BASE), path) is not None

@app.route("/api/graph")
@login_required
def api_graph():
    if not GRAPH_PATH.exists():
        return jsonify({"nodes": [], "edges": []})
    with open(GRAPH_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    # 只保留「有图」的图像节点：imageUrl 对应文件存在的才保留
    valid_image_ids = set()
    for n in nodes:
        if not n.get("imageUrl"):
            continue
        if _image_file_exists(n["imageUrl"]):
            valid_image_ids.add(n["id"])
    # 保留：1) 有图的图像节点  2) 与这些图像有「描述」关系的概念节点
    keep_ids = set(valid_image_ids)
    for e in edges:
        if e.get("relation") == "描述" and (e.get("source") in valid_image_ids or e.get("target") in valid_image_ids):
            keep_ids.add(e.get("source"))
            keep_ids.add(e.get("target"))
    nodes = [n for n in nodes if n["id"] in keep_ids]
    edges = [e for e in edges if e.get("source") in keep_ids and e.get("target") in keep_ids]
    return jsonify({"nodes": nodes, "edges": edges})

@app.route("/api/qa", methods=["GET", "POST"])
@login_required
def api_qa():
    import re
    q = (request.args.get("q") or request.json.get("q") or "").strip()
    if not q:
        return jsonify({"answer": "", "relations": [], "images": [], "message": "请输入问题"})
    with open(GRAPH_PATH, "r", encoding="utf-8") as f:
        graph = json.load(f)
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    edges = graph.get("edges", [])

    # 问答解析：提取“X怎么治 / 如何治疗 / 是什么”中的概念 X
    concept = q
    for pat in [r"(.+?)怎么治", r"(.+?)如何治疗", r"(.+?)怎么治疗", r"(.+?)的治疗", r"(.+?)是什么", r"(.+?)的(?:症状|原因)"]:
        m = re.search(pat, q)
        if m:
            concept = m.group(1).strip()
            break
    # 若整句是概念名也接受
    if not concept:
        concept = q

    # 匹配包含该概念的节点（含部分匹配，如“培根病”匹配“培根病丸剂枝”等）
    matched_ids = set()
    for nid, n in nodes.items():
        lbl = n.get("label") or ""
        if concept in lbl or (concept and lbl in concept):
            matched_ids.add(nid)
    if not matched_ids:
        for nid, n in nodes.items():
            if concept in (n.get("label") or ""):
                matched_ids.add(nid)

    # 收集相关边：治疗/药/方/描述 等
    treatment_keywords = ("治", "疗", "药", "方", "泻", "丸", "散", "饮", "外治", "问诊", "描述", "翻译")
    relations = []
    images = []
    for e in edges:
        if e.get("source") not in matched_ids and e.get("target") not in matched_ids:
            continue
        s = nodes.get(e["source"], {})
        t = nodes.get(e["target"], {})
        rel = e.get("relation", "")
        relations.append({
            "source_label": s.get("label", e["source"]),
            "target_label": t.get("label", e["target"]),
            "relation": rel,
            "target_image": t.get("imageUrl") if _image_file_exists(t.get("imageUrl") or "") else None,
            "source_image": s.get("imageUrl") if _image_file_exists(s.get("imageUrl") or "") else None,
        })
        if t.get("imageUrl") and _image_file_exists(t.get("imageUrl")):
            images.append({"label": s.get("label"), "imageUrl": t.get("imageUrl")})
        if s.get("imageUrl") and _image_file_exists(s.get("imageUrl")):
            images.append({"label": t.get("label"), "imageUrl": s.get("imageUrl")})

    # 去重：同一 imageUrl 只保留一条
    seen_urls = set()
    images_unique = []
    for img in images:
        url = (img.get("imageUrl") or "").strip()
        if url and url not in seen_urls:
            seen_urls.add(url)
            images_unique.append(img)
    images = images_unique

    # 生成自然语言回答
    if "症状" in q:
        # 培根病的症状 -> 只取关系为「症状」的，格式：X的症状包括：A、B、C
        symptom_rels = [r for r in relations if r.get("relation") == "症状"]
        symptom_labels = []
        seen = set()
        for r in symptom_rels:
            t = (r.get("target_label") or "").strip()
            if t and t not in seen:
                symptom_labels.append(t)
                seen.add(t)
        if symptom_labels:
            answer = "「" + concept + "」的症状包括：\n\n" + "、".join(symptom_labels) + "\n"
            if len(symptom_rels) > len(symptom_labels):
                answer += "\n（共 " + str(len(symptom_rels)) + " 条症状关系）"
        else:
            answer = "与「" + concept + "」相关的知识共 " + str(len(relations)) + " 条关系。"
            if relations:
                answer += "\n\n部分关系：\n"
                for r in relations[:15]:
                    answer += "· " + r["source_label"] + " —" + r["relation"] + "— " + r["target_label"] + "\n"
    elif "怎么治" in q or "如何治疗" in q or "怎么治疗" in q or "治疗" in q:
        answer = "根据知识图谱，与「" + concept + "」相关的内容如下：\n\n"
        seen = set()
        for r in relations[:25]:
            key = (r["source_label"], r["relation"], r["target_label"])
            if key in seen:
                continue
            seen.add(key)
            answer += "· " + r["source_label"] + " —" + r["relation"] + "— " + r["target_label"] + "\n"
        if not relations:
            answer = "未在知识图谱中找到与「" + concept + "」直接相关的治疗或描述关系，请尝试其他概念或关键词。"
    else:
        answer = "与「" + concept + "」相关的知识共 " + str(len(relations)) + " 条关系。"
        if relations:
            answer += "\n\n部分关系：\n"
            for r in relations[:15]:
                answer += "· " + r["source_label"] + " —" + r["relation"] + "— " + r["target_label"] + "\n"

    return jsonify({
        "answer": answer,
        "relations": relations[:50],
        "images": images[:30],
        "concept": concept,
    })

@app.route("/api/wordcloud")
@login_required
def api_wordcloud():
    with open(GRAPH_PATH, "r", encoding="utf-8") as f:
        graph = json.load(f)
    words = []
    for n in graph.get("nodes", []):
        label = (n.get("label") or "").strip()
        if not label or n.get("type") == "image":
            continue
        words.append(label)
    from collections import Counter
    cnt = Counter(words)
    wc = [{"name": k, "value": v} for k, v in cnt.most_common(200)]
    return jsonify(wc)

@app.route("/api/users", methods=["GET"])
@login_required
def api_users_list():
    list_users = [{"id": u.id, "username": u.username} for u in USERS_DB.values()]
    return jsonify(list_users)

@app.route("/api/users", methods=["POST"])
@login_required
def api_users_create():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"ok": False, "message": "用户名和密码不能为空"}), 400
    for u in USERS_DB.values():
        if u.username == username:
            return jsonify({"ok": False, "message": "用户名已存在"}), 400
    new_id = str(max((int(k) for k in USERS_DB.keys() if k.isdigit()), default=0) + 1)
    USERS_DB[new_id] = User(new_id, username, generate_password_hash(password))
    save_users()
    return jsonify({"ok": True, "id": new_id})

@app.route("/api/users/<user_id>", methods=["DELETE"])
@login_required
def api_users_delete(user_id):
    if str(user_id) == str(current_user.id):
        return jsonify({"ok": False, "message": "不能删除当前用户"}), 400
    if user_id in USERS_DB:
        del USERS_DB[user_id]
        save_users()
    return jsonify({"ok": True})

def _is_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


if __name__ == "__main__":
    desired_port = int(os.environ.get("PORT", "5000"))
    run_port = desired_port if _is_port_available(desired_port) else 5001
    if run_port != desired_port:
        print(f"[WARN] 端口 {desired_port} 被占用，自动切换到 {run_port}")
    app.run(host="0.0.0.0", port=run_port, debug=True)
