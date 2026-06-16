#!/usr/bin/env python3
"""
数字影子 - 微博用户数字画像生成工具

用法：
    python main.py <UID或微博主页链接> [选项]

示例：
    python main.py 1749127163 --max-posts 10 --export
    python main.py "https://weibo.com/u/1749127163" --max-posts 30

环境变量（必需）：
    WEIBO_COOKIE       微博 Cookie 字符串
    CLAUDE_API_KEY     模型 API Key
    CLAUDE_BASE_URL    模型 API Base URL（OpenAI 兼容格式）
    CLAUDE_MODEL        模型名称（默认 step-3.7-flash）
"""

import argparse
import os
import sys
import time
from datetime import datetime

# 确保能导入同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import WEIBO_COOKIE
from scrapers import (
    search_weibo_user,
    get_weibo_user_info,
    get_weibo_user_posts,
)
from agent import analyze_weibo


def parse_uid(arg):
    """从命令行参数解析 UID，支持纯数字或微博链接"""
    arg = arg.strip()

    # 纯数字 UID
    if arg.isdigit():
        return arg

    # 尝试从链接中提取 UID
    # 支持格式：https://weibo.com/u/123456 或 https://m.weibo.cn/profile/123456
    import re
    patterns = [
        r"weibo\.com/u/(\d+)",
        r"m\.weibo\.cn/profile/(\d+)",
        r"weibo\.cn/u/(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, arg)
        if m:
            return m.group(1)

    print(f"错误：无法从 '{arg}' 中解析出 UID，请提供纯数字 UID 或微博主页链接。")
    sys.exit(1)


def ensure_export_dir():
    """确保导出目录存在"""
    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
    os.makedirs(export_dir, exist_ok=True)
    return export_dir


def export_report(uid, report_text, user_info):
    """将报告导出到 exports/ 目录"""
    export_dir = ensure_export_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = user_info.get("screen_name", uid)
    # 文件名中去除非法字符
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in name).strip()
    filename = f"{safe_name}_{ts}.txt"
    filepath = os.path.join(export_dir, filename)

    header = (
        f"数字影子报告\n"
        f"{'=' * 50}\n"
        f"用户：{name}（UID: {uid}）\n"
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"{'=' * 50}\n\n"
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(header + report_text)

    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="数字影子 - 微博用户数字画像生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python main.py 1749127163 --max-posts 10 --export\n"
            "  python main.py 'https://weibo.com/u/1749127163' --max-posts 30\n"
        ),
    )
    parser.add_argument(
        "target",
        help="微博 UID（纯数字）或主页链接",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=10,
        help="最多获取多少条微博（默认 10）",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="将报告保存到 exports/ 目录",
    )
    args = parser.parse_args()

    # ---------- 检查环境变量 ----------
    api_key = os.environ.get("CLAUDE_API_KEY", "")
    base_url = os.environ.get("CLAUDE_BASE_URL", "")
    if not api_key or not base_url:
        print("错误：请先设置环境变量 CLAUDE_API_KEY 和 CLAUDE_BASE_URL")
        print("示例：")
        print('  export CLAUDE_API_KEY="sk-xxx"')
        print('  export CLAUDE_BASE_URL="https://api.stepfun.com/step_plan/v1"')
        sys.exit(1)

    # ---------- 解析 UID ----------
    uid = parse_uid(args.target)

    # ---------- 获取用户信息 ----------
    print(f"[1/4] 获取用户信息（UID: {uid}）...")
    try:
        user_info = get_weibo_user_info(uid)
    except RuntimeError as e:
        print(f"错误：{e}")
        sys.exit(1)

    name = user_info.get("screen_name", uid)
    print(f"  → {name}")
    print(f"     粉丝: {user_info.get('followers_count', 0)}  |  "
          f"关注: {user_info.get('follow_count', 0)}  |  "
          f"微博: {user_info.get('statuses_count', 0)}")

    # 如果是通过搜索或链接获取的，从 scrapers 拿不到 name 以外的信息；
    # 但如果 UID 是直接输入的，get_weibo_user_info 已经拿到了全部信息。

    # ---------- 获取微博 ----------
    print(f"\n[2/4] 获取最近微博（最多 {args.max_posts} 条，每次间隔 2 秒）...")
    try:
        posts = get_weibo_user_posts(uid)
    except RuntimeError as e:
        print(f"错误：{e}")
        sys.exit(1)

    posts = posts[: args.max_posts]
    print(f"  → 获取到 {len(posts)} 条微博")

    if posts:
        for i, p in enumerate(posts[:3], 1):
            preview = p.get("clean_text", "")[:60]
            print(f"     {i}. {preview}{'...' if len(preview) >= 60 else ''}")
        if len(posts) > 3:
            print(f"     ... 还有 {len(posts) - 3} 条")

    # ---------- 生成报告 ----------
    print(f"\n[3/4] 正在生成数字影子报告（模型: {os.environ.get('CLAUDE_MODEL', 'step-3.7-flash')}）...")
    start = time.time()
    report = analyze_weibo(user_info, posts)
    elapsed = time.time() - start

    if report.startswith("分析失败"):
        print(f"\n❌ {report}")
        sys.exit(1)

    print(f"  → 报告生成完毕（耗时 {elapsed:.1f} 秒）")

    # ---------- 输出 ----------
    print(f"\n[4/4] 输出结果")
    print("=" * 60)
    print(report)
    print("=" * 60)

    # ---------- 导出 ----------
    if args.export:
        filepath = export_report(uid, report, user_info)
        print(f"\n✅ 报告已导出到: {filepath}")


if __name__ == "__main__":
    main()
