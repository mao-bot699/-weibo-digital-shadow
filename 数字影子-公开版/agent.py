"""
LLM 分析模块
负责将爬取的微博数据交给大模型生成数字影子报告。

环境变量：
    CLAUDE_API_KEY     模型 API Key
    CLAUDE_BASE_URL    模型 API Base URL（兼容 OpenAI 格式）
    CLAUDE_MODEL       模型名称
"""

import os
import sys
import re
from datetime import datetime, timezone, timedelta

from openai import OpenAI


def _get_client():
    """根据环境变量创建 OpenAI 兼容客户端"""
    api_key = os.environ.get("CLAUDE_API_KEY", "")
    base_url = os.environ.get("CLAUDE_BASE_URL", "")
    model = os.environ.get("CLAUDE_MODEL", "step-3.7-flash")

    if not api_key or not base_url:
        return None, "分析失败：请设置环境变量 CLAUDE_API_KEY 和 CLAUDE_BASE_URL"

    return OpenAI(api_key=api_key, base_url=base_url), model


def _call_llm(client, model, system_prompt, user_prompt):
    """统一调用 LLM，返回回复文本"""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=16000,
    )
    return resp.choices[0].message.content.strip()


def _parse_time_stats(posts):
    """从微博时间戳中提取时间规律"""
    time_patterns = {
        "hourly_posts": {},      # 每小时发帖数
        "weekday_posts": {},     # 星期几发帖数
        "late_night": 0,         # 深夜(0-5点)发帖数
        "early_morning": 0,      # 清晨(5-8点)发帖数
        "morning": 0,            # 上午(8-12点)
        "afternoon": 0,          # 下午(12-18点)
        "evening": 0,            # 晚上(18-23点)
        "total_with_time": 0,    # 能解析出时间的微博数
    }

    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    for p in posts:
        raw = p.get("created_at", "")
        dt = _parse_weibo_time(raw)
        if dt:
            time_patterns["total_with_time"] += 1
            hour = dt.hour
            wd = dt.weekday()  # 0=Mon, 6=Sun

            time_patterns["hourly_posts"][hour] = time_patterns["hourly_posts"].get(hour, 0) + 1
            time_patterns["weekday_posts"][weekdays[wd]] = time_patterns["weekday_posts"].get(weekdays[wd], 0) + 1

            if 0 <= hour < 5:
                time_patterns["late_night"] += 1
            elif 5 <= hour < 8:
                time_patterns["early_morning"] += 1
            elif 8 <= hour < 12:
                time_patterns["morning"] += 1
            elif 12 <= hour < 18:
                time_patterns["afternoon"] += 1
            else:
                time_patterns["evening"] += 1

    return time_patterns


def _parse_weibo_time(time_str):
    """解析微博时间字符串为 datetime 对象"""
    if not time_str:
        return None

    try:
        # 格式: "Sun Jun 14 20:31:35 +0800 2026"
        dt = datetime.strptime(time_str, "%a %b %d %H:%M:%S %z %Y")
        # 转为北京时间
        beijing = dt.astimezone(timezone(timedelta(hours=8)))
        return beijing
    except Exception:
        pass

    try:
        # 格式: "06-15" 或 "2026-06-15"
        now = datetime.now()
        if len(time_str) == 5:
            dt = datetime.strptime(f"{now.year}-{time_str}", "%Y-%m-%d")
        else:
            dt = datetime.strptime(time_str, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone(timedelta(hours=8)))
    except Exception:
        return None


def _format_time_stats(stats):
    """格式化时间统计为可读文本"""
    lines = []
    total = stats["total_with_time"]
    if total == 0:
        return "无法获取时间信息"

    lines.append(f"（基于 {total} 条有时间戳的微博统计）")

    # 时段分布
    lines.append("时段分布：")
    period_names = [("深夜(0-5点)", stats["late_night"]), ("清晨(5-8点)", stats["early_morning"]),
                    ("上午(8-12点)", stats["morning"]), ("下午(12-18点)", stats["afternoon"]),
                    ("晚上(18-23点)", stats["evening"])]
    for name, count in period_names:
        pct = count / total * 100
        if count > 0:
            lines.append(f"  - {name}：{count} 条 ({pct:.0f}%)")

    # 最活跃时段
    hourly = stats["hourly_posts"]
    if hourly:
        top_hours = sorted(hourly.items(), key=lambda x: x[1], reverse=True)[:3]
        hours_str = "、".join([f"{h}时" for h, _ in top_hours])
        lines.append(f"最活跃时段：{hours_str}")

    # 星期分布
    wd_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    wd_vals = [stats["weekday_posts"].get(d, 0) for d in wd_names]
    if sum(wd_vals) > 0:
        top_wd_idx = wd_vals.index(max(wd_vals))
        lines.append(f"最活跃日：{wd_names[top_wd_idx]}")

    return "\n".join(lines)


def _extract_keywords(posts, top_n=30):
    """从微博内容中提取高频关键词（简单词频统计）"""
    stopwords = set("的了是在我有和人这中大为上个国到以说们出就也你他她它那些什"
                    "么都还而让被从给比把对及其与或且但如所以如果虽然因为于是"
                    "不没之乎者也矣哉吗吧呢啊哦嗯呀哦哈嘿嗯哼"
                    "the a an is are was were be been being have has had do does did"
                    "will would shall should may might can could"
                    "to of in for on with at by from up about into through"
                    "and but or if so that this these those what which who"
                    "i me my we us our you your he him his she her it its"
                    "they them their not no yes just also very much more most"
                    "com http https www")

    word_count = {}
    for p in posts:
        text = p.get("clean_text", "")
        # 中文：按字符和词语
        # 简单分词：去掉停用词，保留 2-8 字的中文词和英文单词
        words = re.findall(r'[一-鿿]{2,8}|[a-zA-Z]{3,15}', text)
        for w in words:
            w = w.lower()
            if w not in stopwords and len(w.strip()) > 1:
                word_count[w] = word_count.get(w, 0) + 1

    sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return sorted_words


def _analyze_topic_evolution(posts, max_periods=5):
    """
    按时间段分组微博，提取每个时期的关键词，分析主题演变趋势。

    参数:
        posts (list[dict]): 微博列表（需按时间排序）
        max_periods (int): 最多分几个时间段

    返回:
        str: 格式化后的时间段主题分析文本
    """
    if not posts:
        return "（无微博数据）"

    # 按时间排序（旧→新）
    sorted_posts = sorted(posts, key=lambda p: p.get("created_at", ""))
    total = len(sorted_posts)
    period_size = max(1, total // max_periods)

    periods = []
    for i in range(0, total, period_size):
        chunk = sorted_posts[i:i + period_size]
        if not chunk:
            continue
        # 取时间范围
        start_time = chunk[0].get("created_at", "")[:10]
        end_time = chunk[-1].get("created_at", "")[:10]
        # 取该段关键词
        keywords = _extract_keywords(chunk, top_n=10)
        kw_text = "、".join([f"{w}({c})" for w, c in keywords]) if keywords else "（无显著关键词）"
        # 取该段内容摘要（第一条微博的前80字）
        summary = chunk[0].get("clean_text", "")[:80]
        periods.append({
            "time": f"{start_time} ~ {end_time}" if start_time != end_time else start_time,
            "keywords": kw_text,
            "summary": summary,
            "count": len(chunk),
        })

    # 格式化输出
    lines = []
    for i, p in enumerate(periods, 1):
        lines.append(f"【时期 {i}】{p['time']}（{p['count']} 条微博）")
        lines.append(f"  高频词：{p['keywords']}")
        lines.append(f"  内容摘要：{p['summary']}...")

    return "\n".join(lines)


def analyze_weibo(user_info, posts, mentions=None, social_links=None):
    """
    分析微博用户数据，生成深度数字影子报告。

    参数:
        user_info (dict): 用户信息（来自 get_weibo_user_info）
        posts (list[dict]): 微博列表（来自 get_weibo_user_posts）
        mentions (list[dict] | None): @提及 统计（来自 extract_mentions）
        social_links (dict | None): 多平台线索（来自 extract_social_links）

    返回:
        str: 分析报告文本，失败时以"分析失败："开头
    """
    client, model = _get_client()
    if client is None:
        return model

    # ── 1. 微博内容统计 ──
    post_lines = []
    for i, p in enumerate(posts, 1):
        post_lines.append(
            f"[{i}] 时间:{p.get('created_at','')} | 来源:{p.get('source','')} | "
            f"地区:{p.get('region_name','')} | "
            f"转:{p.get('reposts_count',0)} 评:{p.get('comments_count',0)} 赞:{p.get('attitudes_count',0)}\n"
            f"    内容:{p.get('clean_text','')}"
        )

    posts_text = "\n\n".join(post_lines) if post_lines else "（该用户近期无公开微博）"

    # ── 2. 时间规律分析 ──
    time_stats = _parse_time_stats(posts)
    time_analysis = _format_time_stats(time_stats)

    # ── 3. 关键词提取 ──
    keywords = _extract_keywords(posts, top_n=40)
    keywords_text = "、".join([f"{w}({c}次)" for w, c in keywords]) if keywords else "（数据不足）"

    # ── 4. 主题演变分析 ──
    topic_evolution_text = _analyze_topic_evolution(posts, max_periods=5)

    # ── 5. 互动分析 ──
    total_reposts = sum(p.get("reposts_count", 0) for p in posts)
    total_comments = sum(p.get("comments_count", 0) for p in posts)
    total_attitudes = sum(p.get("attitudes_count", 0) for p in posts)
    avg_reposts = total_reposts / len(posts) if posts else 0
    avg_comments = total_comments / len(posts) if posts else 0
    avg_attitudes = total_attitudes / len(posts) if posts else 0

    # 互动最高的微博
    top_post = max(posts, key=lambda p: p.get("attitudes_count", 0) + p.get("reposts_count", 0) * 10, default=None)
    top_post_text = ""
    if top_post:
        top_post_text = f"互动最高微博（赞{top_post.get('attitudes_count',0)} 转{top_post.get('reposts_count',0)}）：{top_post.get('clean_text','')[:100]}"

    # ── 5. 设备来源分析 ──
    sources = {}
    for p in posts:
        src = p.get("source", "") or "未知"
        sources[src] = sources.get(src, 0) + 1
    sources_text = "、".join([f"{s}({c}条)" for s, c in sorted(sources.items(), key=lambda x: x[1], reverse=True)])

    # ── 6. 地区分布 ──
    regions = {}
    for p in posts:
        r = p.get("region_name", "") or "未知"
        regions[r] = regions.get(r, 0) + 1
    regions_text = "、".join([f"{r}({c}条)" for r, c in sorted(regions.items(), key=lambda x: x[1], reverse=True)])

    # ── 7. @提及 分析 ──
    mentions_text = ""
    if mentions:
        mentions_list = [f"@{m['screen_name']}（{m['count']}次）" for m in mentions[:10]]
        mentions_text = "、".join(mentions_list) if mentions_list else "（无@提及记录）"
    else:
        mentions_text = "（未提取）"

    # ── 8. 多平台线索 ──
    social_links_text = ""
    if social_links:
        parts = []
        platform_names = {
            "twitter": "Twitter/X",
            "instagram": "Instagram",
            "bilibili": "B站",
            "xiaohongshu": "小红书",
            "douyin": "抖音",
        }
        for key, name in platform_names.items():
            items = social_links.get(key, [])
            if items:
                parts.append(f"{name}: {', '.join(items[:5])}")
        social_links_text = "\n".join(parts) if parts else "（未发现其他平台账号线索）"
    else:
        social_links_text = "（未提取）"

    # ── 9. 构建详细 prompt ──
    user_prompt = f"""你是一位顶级的数字人类学家和行为分析师。请根据以下微博用户的全部公开数据，生成一份极为详尽深入的「数字影子」个人画像报告。

⚠️ 分析要求：深度优先，宁多勿少。每个维度都要尽可能挖掘细节。数据不足的地方明确标注「基于现有数据无法确定」，但不要因为数据不足就省略分析维度。

══════════════════════════════════════════════
一、基础档案
══════════════════════════════════════════════
- 昵称：{user_info.get('screen_name', '')}
- 简介：{user_info.get('description', '')}
- 粉丝数：{user_info.get('followers_count', 0):,}
- 关注数：{user_info.get('follow_count', 0):,}
- 微博总数：{user_info.get('statuses_count', 0):,}
- 认证：{'是（' + user_info.get('verified_reason', '') + '）' if user_info.get('verified') else '否'}
- 性别：{user_info.get('gender', '')}
- 常驻地区：{user_info.get('city', '')}

══════════════════════════════════════════════
二、发博时间规律分析（关键！）
══════════════════════════════════════════════
{time_analysis}

请根据以上时间分布，推断：
1. 大致起床时间（最早发帖时间附近）
2. 大致睡觉时间（最晚发帖时间附近）
3. 工作日的作息规律
4. 是否经常深夜发帖
5. 发帖习惯是碎片化还是集中发布

══════════════════════════════════════════════
三、发布设备与地点分析
══════════════════════════════════════════════
设备来源分布：{sources_text}
发布地区分布：{regions_text}

请推断：用户的设备偏好（是否忠实于某个品牌）、移动端还是桌面端为主、
是否经常出差/旅行（地区是否分散）。

══════════════════════════════════════════════
五、主题演变分析
══════════════════════════════════════════════
以下按时间段分组，展示每个时期的高频关键词和内容摘要：

{topic_evolution_text}

请分析：
1. 用户的内容主题是否随时间发生变化（例如从科技转向生活、从工作转向兴趣）
2. 是否存在明显的"阶段转换"（如入职新公司、人生重大事件后的内容变化）
3. 发博频率的变化趋势（越来越活跃 / 逐渐沉默 / 周期性波动）
4. 话题的广度变化（早期专注单一领域 → 后期涉及多个领域）

══════════════════════════════════════════════
六、互动关系分析
══════════════════════════════════════════════
@提及 高频用户（按被提及次数排序）：
{mentions_text}

请分析：
1. 互动最多的对象是谁，可能是什么关系（同事、朋友、家人、偶像等）
2. 社交圈层的核心特征（是否集中在某个行业/圈子）
3. 是否存在"大V互动"模式（主动@名人/机构 vs 被普通人@）

══════════════════════════════════════════════
五、多平台账号线索
══════════════════════════════════════════════
从微博简介和正文中提取的其他平台账号：
{social_links_text}

⚠️ 注意：以上线索仅为从微博内容中匹配到的候选账号，不一定属于该用户本人。
请标注哪些线索可信度较高，哪些可能是误匹配或引用他人账号。

══════════════════════════════════════════════
六、多平台账号线索
══════════════════════════════════════════════
从微博简介和正文中提取的其他平台账号：
{social_links_text}

⚠️ 注意：以上线索仅为从微博内容中匹配到的候选账号，不一定属于该用户本人。
请标注哪些线索可信度较高，哪些可能是误匹配或引用他人账号。

══════════════════════════════════════════════
七、全部微博内容（共 {len(posts)} 条，逐条分析）
══════════════════════════════════════════════
{posts_text}

{top_post_text}

══════════════════════════════════════════════
五、高频关键词
══════════════════════════════════════════════
{keywords_text}

══════════════════════════════════════════════

📋 请生成以下结构化的深度分析报告（markdown 格式）：

# 🕵️ 「数字影子」深度画像报告：{user_info.get('screen_name', '')}

---

## 一、人物总画像
- 身份标签（职业、社会角色、行业地位）
- 公开形象 vs 可能的内在性格差异
- 人生阶段判断

## 二、性格与心理特征（重点！）
- 从语言风格推断性格（外向/内向、理性/感性、严谨/随性）
- 情绪管理能力（发帖内容是否稳定、是否有情绪波动）
- 价值观取向（从话题选择和表达方式中提炼）
- 人际交往模式（是否热衷社交、回复风格、互动频率）
- 可能的 MBTI 类型猜测（基于内容分析）

## 三、生活方式与日常规律（重点！）
- 作息时间推断（几点起床、几点睡觉、是否熬夜）
- 工作日 vs 周末的行为差异
- 通勤/出差频率（从发博地点推断）
- 饮食偏好（从内容中提到的食物推断）
- 运动习惯
- 消费偏好（提到品牌、产品时的态度）
- 休闲娱乐方式

## 四、兴趣爱好与关注领域
- 核心兴趣领域（从高频关键词归纳）
- 是否关注特定行业/圈子
- 是否有收藏、旅行、阅读等爱好
- 追星/追剧/追综艺/追体育等娱乐偏好
- 对科技、时尚、美食等领域的关注度

## 五、主题演变分析
- 按时间段展示内容主题变化趋势
- 是否存在明显的阶段转换（如职业变动、人生事件）
- 发博频率和话题广度的变化

## 六、社交网络特征
- 粉丝互动模式（发什么内容互动最高）
- 转发 vs 原创比例
- 是否积极参与讨论还是单向输出
- 影响力层级评估

## 七、互动关系图谱
- 互动最频繁的 Top 5 对象及关系推断
- 社交圈层特征（行业集中度、是否存在跨圈互动）
- @提及模式分析（主动出击型 vs 被动互动型）

## 八、多平台线索分析
- 从微博中发现的其他平台账号线索
- 各线索可信度评估
- 跨平台账号是否能拼凑出更完整的用户画像

## 九、语言与表达特征
- 常用语言风格（正式/口语化/幽默/严肃）
- 是否使用网络流行语
- 标点符号使用习惯
- emoji 使用频率
- 排版习惯（长文/短句/分点）

## 十、数据时间线
- 以时间线形式，展示 {len(posts)} 条微博的发博规律
- 标注出特别活跃或特别安静的时期
- 内容主题随时间的变化趋势

## 十一、综合总结
- 用 100 字以内总结这个人的核心特征
- 如果要用三个关键词形容，是哪三个
- 一个有趣的、出人意料的发现

---

⚠️ 要求：
1. 每一项都要有具体的数据支撑，引用微博原文或数据
2. 不要空洞的形容词堆砌，要给出分析依据
3. 标注不确定的地方，不要过度推断
4. 如果某个维度数据不足，坦诚说明但尽量给出有限信息下的推断
5. 字数不少于 2000 字"""

    system_prompt = (
        "你是一位顶级的数字人类学家、行为心理学家和社交媒体分析师。"
        "你擅长从社交媒体公开数据中深度挖掘用户的性格特征、生活方式、"
        "作息规律、兴趣爱好和价值观。你的分析细致入微、有理有据、洞察力强，"
        "同时保持客观严谨，不做无端揣测，不确定之处明确标注。"
        "你的报告应当详尽、有深度、让人读后有'原来如此'的收获感。"
    )

    try:
        return _call_llm(client, model, system_prompt, user_prompt)
    except Exception as e:
        return f"分析失败：模型调用出错 - {e}"


def continue_analysis(previous_report, new_info):
    """
    基于已有报告和新信息，继续深入分析。

    参数:
        previous_report (str): 之前的分析报告
        new_info (str): 用户补充的新信息或追问

    返回:
        str: 更新后的分析报告，失败时以"分析失败："开头
    """
    client, model = _get_client()
    if client is None:
        return model

    system_prompt = (
        "你是一位顶级的数字人类学家和行为分析师。"
        "你正在延续之前的一份深度分析报告，"
        "根据用户提供的新信息或追问，在原有报告基础上进行补充或调整。"
    )

    user_prompt = f"""以下是之前的深度分析报告：

---

{previous_report}

---

以下是用户的新信息或追问：

{new_info}

请基于以上内容，给出深入的分析补充或回答追问。如果新的信息纠正了之前的判断，请明确说明修正之处。保持报告的详细风格。"""

    try:
        return _call_llm(client, model, system_prompt, user_prompt)
    except Exception as e:
        return f"分析失败：模型调用出错 - {e}"
