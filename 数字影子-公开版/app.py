#!/usr/bin/env python3
"""
数字影子 - Streamlit 网页版
用法：streamlit run app.py
"""

import os
import sys
import time
from datetime import datetime

import streamlit as st

# 确保能导入同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import WEIBO_COOKIE
from scrapers import search_weibo_user, get_weibo_user_info, get_weibo_user_posts
from agent import analyze_weibo, continue_analysis

# ── 页面配置 ──────────────────────────────────────────────
st.set_page_config(
    page_title="数字影子",
    page_icon="🕵️",
    layout="centered",
)

st.title("🕵️ 数字影子")
st.caption("基于公开微博数据，生成个人数字画像分析报告")

# ── 侧边栏：环境变量检查 ──────────────────────────────────
with st.sidebar:
    st.header("⚙️ 环境配置")
    api_key = os.environ.get("CLAUDE_API_KEY", "")
    base_url = os.environ.get("CLAUDE_BASE_URL", "")
    model = os.environ.get("CLAUDE_MODEL", "step-3.7-flash")

    if api_key:
        st.success(f"✅ API Key 已配置（前8位: {api_key[:8]}...）")
    else:
        st.error("❌ 未设置 CLAUDE_API_KEY")

    if base_url:
        st.success(f"✅ Base URL: {base_url}")
    else:
        st.error("❌ 未设置 CLAUDE_BASE_URL")

    st.info(f"🤖 模型：`{model}`")

    with st.expander("📋 环境变量设置方法"):
        st.code(
            'export CLAUDE_API_KEY="你的Key"\n'
            'export CLAUDE_BASE_URL="https://api.stepfun.com/step_plan/v1"\n'
            'export CLAUDE_MODEL="step-3.7-flash"\n'
            'streamlit run app.py',
            language="bash",
        )

# ── 主界面 ────────────────────────────────────────────────

# Step 1: 输入 UID 或搜索
st.header("1️⃣ 选择目标用户")

col1, col2 = st.columns([3, 1])
with col1:
    target = st.text_input(
        "输入微博 UID 或主页链接",
        placeholder="例如：1749127163 或 https://weibo.com/u/1749127163",
    )
with col2:
    search_btn = st.button("🔍 搜索", use_container_width=True)

# 搜索结果
users = []
if search_btn and target.strip():
    with st.spinner("搜索中..."):
        try:
            users = search_weibo_user(target.strip())
        except RuntimeError as e:
            st.error(f"搜索失败：{e}")
        except Exception as e:
            st.error(f"搜索出错：{e}")

if users:
    st.subheader(f"找到 {len(users)} 个用户")
    for i, u in enumerate(users):
        with st.container(border=True):
            col_a, col_b = st.columns([4, 1])
            with col_a:
                st.write(f"**{u['screen_name']}** (UID: `{u['uid']}`)")
                st.caption(u.get("description", "")[:60])
                st.caption(
                    f"👥 {u['followers_count']:,} 粉丝 ｜  📝 {u['statuses_count']:,} 微博"
                )
            with col_b:
                if st.button("选择", key=f"sel_{i}"):
                    st.session_state["selected_uid"] = str(u["uid"])
                    st.session_state["selected_name"] = u["screen_name"]
                    st.rerun()

# 如果已选用户或直接输入了 UID
selected_uid = st.session_state.get("selected_uid", "")
if not selected_uid and target.strip().isdigit():
    selected_uid = target.strip()

# Step 2: 配置参数
st.header("2️⃣ 分析参数")
col_a, col_b = st.columns(2)
with col_a:
    max_posts = st.slider("最多获取微博数", 5, 50, 10, 5)
with col_b:
    auto_export = st.checkbox("自动导出报告", value=True)

# Step 3: 开始分析
st.header("3️⃣ 生成报告")

if not selected_uid:
    st.info("👆 请先搜索并选择一个用户，或直接输入纯数字 UID")
else:
    # 显示选中用户
    name = st.session_state.get("selected_name", selected_uid)
    st.write(f"**目标用户**：{name}（UID: `{selected_uid}`）")

    if st.button("🚀 开始分析", type="primary", use_container_width=True):
        # 检查环境变量
        if not api_key or not base_url:
            st.error("请先在终端设置 CLAUDE_API_KEY 和 CLAUDE_BASE_URL 环境变量，然后重启页面。")
            st.stop()

        # 1. 获取用户信息
        progress = st.progress(0, text="正在获取用户信息...")
        try:
            user_info = get_weibo_user_info(selected_uid)
        except RuntimeError as e:
            progress.empty()
            st.error(f"获取用户信息失败：{e}")
            st.stop()
        except Exception as e:
            progress.empty()
            st.error(f"未知错误：{e}")
            st.stop()

        progress.progress(25, text=f"用户：{user_info['screen_name']}，正在获取微博...")

        # 2. 获取微博
        try:
            posts = get_weibo_user_posts(selected_uid)
        except RuntimeError as e:
            progress.empty()
            st.error(f"获取微博失败：{e}")
            st.stop()
        except Exception as e:
            progress.empty()
            st.error(f"未知错误：{e}")
            st.stop()

        posts = posts[:max_posts]
        progress.progress(50, text=f"获取到 {len(posts)} 条微博，正在生成报告...")

        # 3. 显示微博预览
        with st.expander(f"📄 查看 {len(posts)} 条微博原文", expanded=False):
            for i, p in enumerate(posts, 1):
                st.write(
                    f"**[{i}]** {p['created_at']} | 📍 {p['region_name']} | "
                    f"📱 {p['source']}"
                )
                st.caption(
                    f"🔄 {p['reposts_count']} ｜ 💬 {p['comments_count']} ｜ 👍 {p['attitudes_count']}"
                )
                st.write(p["clean_text"])
                st.divider()

        # 4. 生成报告
        start = time.time()
        report = analyze_weibo(user_info, posts)
        elapsed = time.time() - start
        progress.progress(90, text=f"报告生成完毕（{elapsed:.1f}s），渲染中...")

        if report.startswith("分析失败"):
            progress.empty()
            st.error(report)
            st.stop()

        progress.progress(100, text="完成！")
        time.sleep(0.3)
        progress.empty()

        # 5. 显示报告
        st.success(f"✅ 报告生成完毕（耗时 {elapsed:.1f} 秒）")
        st.divider()
        st.markdown(report)
        st.divider()

        # 6. 导出
        if auto_export:
            export_dir = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "exports"
            )
            os.makedirs(export_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(
                c if c.isalnum() or c in "-_ " else "" for c in user_info["screen_name"]
            ).strip()
            filepath = os.path.join(export_dir, f"{safe_name}_{ts}.txt")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report)
            st.download_button(
                "📥 下载报告",
                data=report.encode("utf-8"),
                file_name=f"{safe_name}_{ts}.txt",
                mime="text/plain",
            )

        # 7. 追问功能
        st.divider()
        st.subheader("💬 追问补充")
        with st.form("follow_up_form"):
            new_info = st.text_area(
                "输入补充信息或追问（留空则不追问）",
                placeholder="例如：这个用户是科技创业者，补充一些行业背景...",
                height=80,
            )
            submitted = st.form_submit_button("🔄 继续分析")
            if submitted and new_info.strip():
                with st.spinner("正在补充分析..."):
                    updated = continue_analysis(report, new_info.strip())
                    if updated.startswith("分析失败"):
                        st.error(updated)
                    else:
                        st.markdown(updated)
