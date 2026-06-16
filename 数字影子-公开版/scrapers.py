"""
微博爬虫 + 数据清洗模块
角色 B 负责：搜索用户、获取用户信息、获取用户微博、清洗 HTML 文本

使用微博桌面端 Ajax API（m.weibo.cn 有反爬限制，桌面端更稳定）。
"""

import time
import re
import json
import requests
from urllib.parse import quote

from config import WEIBO_COOKIE

# 通用请求头 - 模拟桌面浏览器
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Cookie": WEIBO_COOKIE,
    "Referer": "https://weibo.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 桌面端 API 基础 URL
_BASE = "https://weibo.com/ajax"


def _get(url, params=None):
    """
    内部方法：统一发 GET 请求，自动间隔 2 秒防限流。
    如果 Cookie 过期（返回 HTML 或错误），主动抛出明确错误。
    """
    time.sleep(2)
    resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    if "text/html" in content_type or resp.text.strip().lower().startswith(("<!doctype", "<html")):
        raise RuntimeError(
            "微博 Cookie 已过期！请重新从浏览器获取 Cookie 并更新 WEIBO_COOKIE。"
        )

    data = resp.json()
    if isinstance(data, dict) and data.get("ok") == 0:
        msg = data.get("message", "未知错误")
        if "登录" in msg or "login" in msg.lower():
            raise RuntimeError("微博 Cookie 已过期！请重新获取。")
        raise RuntimeError(f"微博 API 返回错误：{msg}")

    return data


def _desktop_headers():
    """返回带 Referer 的请求头（桌面端需要 Referer）"""
    return HEADERS


def _get_mobile(url, params=None):
    """
    移动端搜索专用请求（不检查 Cookie 过期，因为移动端有反爬）。
    返回 JSON 数据，如果被反爬则返回空结果而非抛异常。
    """
    time.sleep(2)
    mobile_headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)",
        "Cookie": WEIBO_COOKIE,
        "Referer": "https://m.weibo.cn/",
    }
    resp = requests.get(url, headers=mobile_headers, params=params, timeout=10)
    resp.raise_for_status()

    # 如果被反爬返回 HTML，静默返回空列表
    content_type = resp.headers.get("Content-Type", "")
    if "text/html" in content_type or resp.text.strip().lower().startswith(("<!doctype", "<html")):
        return {"data": {"cards": []}}

    try:
        return resp.json()
    except Exception:
        return {"data": {"cards": []}}


# ============================================================
#  函数 1：搜索微博用户
# ============================================================
def search_weibo_user(keyword):
    """
    搜索微博用户，返回匹配的用户列表。

    参数:
        keyword (str): 搜索关键词，如 "雷军"

    返回:
        list[dict]: 每个元素包含 uid, screen_name, description,
                    followers_count, follow_count, statuses_count
    """
    # 使用移动端搜索 API（桌面端无搜索接口），用独立请求避免反爬误报 Cookie 过期
    url = "https://m.weibo.cn/api/container/getIndex"
    params = {"containerid": "100103type=3", "q": quote(keyword), "page_type": "searchall"}

    data = _get_mobile(url, params=params)
    cards = data.get("data", {}).get("cards", [])
    users = []

    for card in cards:
        card_group = card.get("card_group", [])
        for item in card_group:
            user = item.get("user")
            if user:
                users.append({
                    "uid": user.get("id", 0),
                    "screen_name": user.get("screen_name", ""),
                    "description": user.get("description", ""),
                    "followers_count": user.get("followers_count", 0),
                    "follow_count": user.get("follow_count", 0),
                    "statuses_count": user.get("statuses_count", 0),
                })

    return users


# ============================================================
#  函数 2：获取用户详细信息
# ============================================================
def get_weibo_user_info(uid):
    """
    获取指定用户的详细信息（使用桌面端 Ajax API）。

    参数:
        uid (str | int): 用户 ID，如 "1749127163"

    返回:
        dict: 包含 screen_name, description, followers_count, follow_count,
              statuses_count, verified, verified_reason, gender, city

    异常:
        RuntimeError: 用户不存在或 Cookie 过期时抛出
    """
    url = f"{_BASE}/profile/info"
    data = _get(url, params={"uid": uid})
    user = data.get("data", {}).get("user")

    if not user:
        raise RuntimeError(f"用户 ID {uid} 不存在或无法访问，请检查 ID 是否正确。")

    # 性别转换：API 返回 "m"/"f"
    gender_raw = user.get("gender", "")
    gender_map = {"m": "男", "f": "女"}
    gender = gender_map.get(gender_raw, "")

    # 地区：取 location 字段（如 "北京 海淀区"）
    location = user.get("location", "") or ""

    return {
        "screen_name": user.get("screen_name", ""),
        "description": user.get("description", ""),
        "followers_count": user.get("followers_count", 0),
        "follow_count": user.get("friends_count", 0),
        "statuses_count": user.get("statuses_count", 0),
        "verified": user.get("verified", False),
        "verified_reason": user.get("verified_reason", ""),
        "gender": gender,
        "city": location,
    }


# ============================================================
#  函数 3：获取用户最近微博
# ============================================================
def get_weibo_user_posts(uid, max_posts=None):
    """
    获取指定用户最近的微博列表（使用桌面端 Ajax API）。
    桌面端 API 的 text_raw 字段已经是纯文本，无需 HTML 清洗。
    支持翻页获取更多微博。

    参数:
        uid (str | int): 用户 ID
        max_posts (int | None): 最多获取多少条，None 表示取全部可用

    返回:
        list[dict]: 微博列表
    """
    url = f"{_BASE}/statuses/mymblog"

    posts = []
    page = 1
    max_pages = 10  # 最多翻 10 页（每页约 20 条，最多约 200 条）

    while page <= max_pages:
        data = _get(url, params={"uid": uid, "page": page, "feature": 0})
        cards = data.get("data", {}).get("list", [])

        if not cards:
            break

        for card in cards:
            raw_text = card.get("text_raw", "") or ""
            clean = clean_weibo_text(raw_text)

            region = card.get("region_name", "") or ""
            if region.startswith("发布于 "):
                region = region[len("发布于 "):]

            posts.append({
                "text": raw_text,
                "clean_text": clean,
                "created_at": card.get("created_at", ""),
                "source": card.get("source", ""),
                "region_name": region,
                "reposts_count": card.get("reposts_count", 0),
                "comments_count": card.get("comments_count", 0),
                "attitudes_count": card.get("attitudes_count", 0),
            })

        if max_posts and len(posts) >= max_posts:
            break

        # 检查是否还有下一页
        since_id = data.get("data", {}).get("since_id")
        if not since_id:
            break

        page += 1

    if max_posts:
        posts = posts[:max_posts]

    return posts


# ============================================================
#  内部方法：清洗文本（去掉 @用户 和 #话题#）
# ============================================================
def clean_weibo_text(text):
    """
    清洗微博文本：去掉 HTML 标签、@用户提及 和 #话题# 标签，压缩空白。
    """
    if not text:
        return ""
    # 去掉 HTML 标签
    text = re.sub(r"<[^>]+>", "", text)
    # 去掉 @用户提及
    text = re.sub(r"@[^\s@]+", "", text)
    # 去掉 #话题# 标签
    text = re.sub(r"#[^#]*#", "", text)
    # 压缩空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ============================================================
#  功能：提取 @提及 关系
# ============================================================
def extract_mentions(posts, top_n=10):
    """
    从微博列表中提取 @提及 的高频用户。

    参数:
        posts (list[dict]): 微博列表
        top_n (int): 返回前 N 个最常被提及的用户

    返回:
        list[dict]: [{screen_name, count}, ...]
    """
    mention_count = {}
    for p in posts:
        text = p.get("text", "") or p.get("clean_text", "")
        for m in re.finditer(r"@([^\s@<>【】\[\]{}|\\/:：，,。.！!？?；;、\"'\n]{1,20})", text):
            name = m.group(1).strip()
            if name and len(name) >= 1:
                mention_count[name] = mention_count.get(name, 0) + 1

    sorted_mentions = sorted(mention_count.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [{"screen_name": name, "count": count} for name, count in sorted_mentions]


# ============================================================
#  功能：提取多平台账号线索
# ============================================================
def extract_social_links(user_info, posts):
    """
    从用户简介和微博正文中提取其他社交平台账号线索。

    匹配规则:
        Twitter/X: @username 或 twitter.com/xxx
        Instagram: @username 或 instagram.com/xxx
        B站: UID 或 bilibili.com/xxx
        小红书: 小红书号 xxx 或 xiaohongshu.com/xxx
        抖音: 抖音号 xxx 或 douyin.com/xxx

    参数:
        user_info (dict): 用户信息
        posts (list[dict]): 微博列表

    返回:
        dict: {platform: [candidates]}
    """
    results = {"twitter": [], "instagram": [], "bilibili": [], "xiaohongshu": [], "douyin": []}

    # 收集所有文本
    texts = [user_info.get("description", "") or ""]
    for p in posts:
        texts.append(p.get("text", "") or p.get("clean_text", ""))
    combined = " ".join(texts)

    # Twitter/X: @username (不在微博上下文中的独立账号)
    for m in re.finditer(r"(?:twitter|x)\.com/([A-Za-z0-9_]{1,15})", combined, re.IGNORECASE):
        results["twitter"].append(m.group(1))
    # Twitter/X 纯文本模式：@xxx 后面有 twitter/x 关键词
    for m in re.finditer(r"(?:Twitter|X|推特)[\s:：]*@?([A-Za-z0-9_]{1,15})", combined):
        results["twitter"].append(m.group(1))

    # Instagram: @username 或 instagram.com/xxx
    for m in re.finditer(r"instagram\.com/([A-Za-z0-9_.]{1,30})", combined, re.IGNORECASE):
        results["instagram"].append(m.group(1))
    for m in re.finditer(r"(?:Instagram|INS|ins)[\s:：]*@?([A-Za-z0-9_.]{1,30})", combined, re.IGNORECASE):
        results["instagram"].append(m.group(1))

    # B站: 匹配用户主页 space.bilibili.com 或 bilibili.com 上的用户标识
    for m in re.finditer(r"space\.bilibili\.com/(\d+)", combined, re.IGNORECASE):
        results["bilibili"].append(m.group(1))
    for m in re.finditer(r"(?:B站|哔哩哔哩|bilibili)[\s:：]*@?([A-Za-z0-9_]{5,15})\b", combined, re.IGNORECASE):
        results["bilibili"].append(m.group(1))

    # 小红书: 小红书号 xxx 或 xiaohongshu.com/xxx
    for m in re.finditer(r"xiaohongshu\.com/user/profile/([A-Za-z0-9]+)", combined, re.IGNORECASE):
        results["xiaohongshu"].append(m.group(1))
    for m in re.finditer(r"小红书号[\s:：]*([A-Za-z0-9]{5,20})", combined):
        results["xiaohongshu"].append(m.group(1))

    # 抖音: 抖音号 xxx 或 douyin.com/xxx
    for m in re.finditer(r"douyin\.com/([A-Za-z0-9]+)", combined, re.IGNORECASE):
        results["douyin"].append(m.group(1))
    for m in re.finditer(r"抖音号[\s:：]*([A-Za-z0-9]{5,20})", combined):
        results["douyin"].append(m.group(1))

    # 去重，保留顺序
    for platform in results:
        seen = set()
        deduped = []
        for item in results[platform]:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        results[platform] = deduped

    return results
