#!/usr/bin/env python3
"""
数字影子 - Flask 后端 API
提供前端页面和 REST API 接口
"""

import os
import sys
import json
import time
from urllib.parse import quote

from flask import Flask, render_template, request, jsonify, Response, make_response
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import WEIBO_COOKIE
from scrapers import search_weibo_user, get_weibo_user_info, get_weibo_user_posts, extract_mentions, extract_social_links
from agent import analyze_weibo, continue_analysis

app = Flask(__name__, static_folder="static")
CORS(app)

# ── 页面路由 ──────────────────────────────────────────────
@app.route("/")
def index():
    resp = make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


# ── API 路由 ──────────────────────────────────────────────

@app.route("/api/search", methods=["POST"])
def api_search():
    """搜索用户"""
    data = request.get_json() or {}
    keyword = data.get("keyword", "").strip()
    if not keyword:
        return jsonify({"ok": False, "error": "请输入搜索关键词"}), 400
    try:
        users = search_weibo_user(keyword)
        return jsonify({"ok": True, "data": users})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/user_info", methods=["POST"])
def api_user_info():
    """获取用户信息"""
    data = request.get_json() or {}
    uid = data.get("uid", "").strip()
    if not uid:
        return jsonify({"ok": False, "error": "缺少 UID"}), 400
    try:
        info = get_weibo_user_info(uid)
        return jsonify({"ok": True, "data": info})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/posts", methods=["POST"])
def api_posts():
    """获取用户微博"""
    data = request.get_json() or {}
    uid = data.get("uid", "").strip()
    max_posts = data.get("max_posts", 10)
    if not uid:
        return jsonify({"ok": False, "error": "缺少 UID"}), 400
    try:
        posts = get_weibo_user_posts(uid)
        return jsonify({"ok": True, "data": posts[:max_posts], "total": len(posts)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/mentions", methods=["POST"])
def api_mentions():
    """获取用户微博中的 @提及 关系"""
    data = request.get_json() or {}
    uid = data.get("uid", "").strip()
    top_n = data.get("top_n", 10)
    if not uid:
        return jsonify({"ok": False, "error": "缺少 UID"}), 400
    try:
        posts = get_weibo_user_posts(uid)
        mentions = extract_mentions(posts, top_n=top_n)
        return jsonify({"ok": True, "data": mentions, "total": len(mentions)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/social_links", methods=["POST"])
def api_social_links():
    """获取用户微博中的其他平台账号线索"""
    data = request.get_json() or {}
    uid = data.get("uid", "").strip()
    if not uid:
        return jsonify({"ok": False, "error": "缺少 UID"}), 400
    try:
        info = get_weibo_user_info(uid)
        posts = get_weibo_user_posts(uid)
        links = extract_social_links(info, posts)
        return jsonify({"ok": True, "data": links})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """生成分析报告"""
    data = request.get_json() or {}
    user_info = data.get("user_info")
    posts = data.get("posts", [])

    if not user_info:
        return jsonify({"ok": False, "error": "缺少 user_info"}), 400

    try:
        mentions = data.get("mentions")
        social_links = data.get("social_links")
        # 如果前端没传，后端自动提取
        if not mentions or not social_links:
            uid = user_info.get("uid", "")
            if uid:
                try:
                    all_posts = get_weibo_user_posts(uid)
                    if not mentions:
                        mentions = extract_mentions(all_posts, top_n=10)
                    if not social_links:
                        social_links = extract_social_links(user_info if social_links else get_weibo_user_info(uid), all_posts)
                except Exception:
                    pass  # 提取失败不影响主分析
        report = analyze_weibo(user_info, posts, mentions=mentions, social_links=social_links)
        if report.startswith("分析失败"):
            return jsonify({"ok": False, "error": report}), 500
        return jsonify({"ok": True, "data": report})
    except Exception as e:
        return jsonify({"ok": False, "error": f"分析失败：{e}"}), 500


@app.route("/api/continue", methods=["POST"])
def api_continue():
    """追问补充分析"""
    data = request.get_json() or {}
    previous = data.get("previous_report", "")
    new_info = data.get("new_info", "")

    if not previous or not new_info:
        return jsonify({"ok": False, "error": "缺少参数"}), 400

    try:
        updated = continue_analysis(previous, new_info)
        if updated.startswith("分析失败"):
            return jsonify({"ok": False, "error": updated}), 500
        return jsonify({"ok": True, "data": updated})
    except Exception as e:
        return jsonify({"ok": False, "error": f"分析失败：{e}"}), 500


@app.route("/api/export", methods=["POST"])
def api_export():
    """服务端生成报告文件并返回下载"""
    data = request.get_json() or {}
    user_info = data.get("user_info")
    posts = data.get("posts", [])
    report = data.get("report", "")

    if report is None:
        return jsonify({"ok": False, "error": "报告内容为空"}), 400

    # 如果前端没传 report，后端重新生成
    if not report and user_info and posts:
        report = analyze_weibo(user_info, posts, mentions=None, social_links=None)
        if report.startswith("分析失败"):
            return jsonify({"ok": False, "error": report}), 500

    if not report:
        return jsonify({"ok": False, "error": "报告内容为空，请先生成报告"}), 400

    name = user_info.get("screen_name", "unknown") if user_info else "unknown"
    uid = user_info.get("uid", "") if user_info else ""
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in name).strip()
    ts = time.strftime("%Y%m%d_%H%M%S")
    filename = f"数字影子_{safe_name}_{ts}.txt"

    header = (
        f"数字影子报告\n"
        f"{'=' * 50}\n"
        f"用户：{name}（UID: {uid}）\n"
        f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"{'=' * 50}\n\n"
    )
    full_text = header + report

    # 中文文件名需要 RFC 5987 编码
    filename_ascii = f"report_{ts}.txt"
    filename_utf8 = quote(filename)

    return Response(
        full_text,
        mimetype="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename_ascii}; filename*=UTF-8''{filename_utf8}"
        },
    )


if __name__ == "__main__":
    print("=" * 50)
    print("🕵️  数字影子 服务启动中...")
    print(f"   页面地址：http://localhost:8080")
    print("=" * 50)
    app.run(debug=True, host="0.0.0.0", port=8080)
