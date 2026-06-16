"""
测试 scrapers.py —— 按新任务文档规范验证
"""
import json
from scrapers import (
    search_weibo_user,
    get_weibo_user_info,
    get_weibo_user_posts,
    clean_weibo_text,
)

print("=" * 60)
print("测试 1：search_weibo_user('雷军')")
print("=" * 60)
try:
    users = search_weibo_user("雷军")
    print(f"找到 {len(users)} 个用户")
    if users:
        u = users[0]
        required = ["uid", "screen_name", "description", "followers_count", "follow_count", "statuses_count"]
        missing = [k for k in required if k not in u]
        if missing:
            print(f"❌ 缺失字段: {missing}")
        else:
            print("✅ 字段齐全")
            print(json.dumps(u, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"❌ 出错：{e}")

print()
print("=" * 60)
print("测试 2：get_weibo_user_info(uid)")
print("=" * 60)
try:
    info = get_weibo_user_info("1749127163")
    required = ["screen_name", "description", "followers_count", "follow_count", "statuses_count", "verified", "verified_reason", "gender", "city"]
    missing = [k for k in required if k not in info]
    if missing:
        print(f"❌ 缺失字段: {missing}")
    else:
        print("✅ 字段齐全")
        print(json.dumps(info, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"❌ 出错：{e}")

print()
print("=" * 60)
print("测试 3：get_weibo_user_posts(uid)")
print("=" * 60)
try:
    posts = get_weibo_user_posts("1749127163")
    print(f"获取到 {len(posts)} 条微博")
    if posts:
        p = posts[0]
        required = ["text", "clean_text", "created_at", "source", "region_name", "reposts_count", "comments_count", "attitudes_count"]
        missing = [k for k in required if k not in p]
        if missing:
            print(f"❌ 缺失字段: {missing}")
        else:
            print("✅ 字段齐全")
            print(f"  text (原始HTML): {p['text'][:60]}...")
            print(f"  clean_text: {p['clean_text'][:60]}...")
            print(f"  created_at: {p['created_at']}")
            print(f"  source: {p['source']}")
            print(f"  region_name: {p['region_name']}")
            print(f"  reposts: {p['reposts_count']}  comments: {p['comments_count']}  attitudes: {p['attitudes_count']}")
            # 检查 clean_text 是否干净
            has_html = "<" in p["clean_text"] and ">" in p["clean_text"]
            has_at = bool(__import__('re').search(r'@\S+', p["clean_text"]))
            has_topic = bool(__import__('re').search(r'#.*?#', p["clean_text"]))
            if has_html:
                print("❌ clean_text 里还有 HTML 标签！")
            elif has_at:
                print("❌ clean_text 里还有 @用户！")
            elif has_topic:
                print("❌ clean_text 里还有话题标签！")
            else:
                print("✅ clean_text 是干净的纯文本")
except Exception as e:
    print(f"❌ 出错：{e}")

print()
print("=" * 60)
print("测试 4：clean_weibo_text(html)")
print("=" * 60)
test_cases = [
    '<p>今天天气真好！@张三 一起去爬山吧 #户外运动# <a>链接</a></p>',
    '<p>感谢 @ElonMusk @spacex_official 的分享 #科技# #创新# 太棒了</p>',
    "",
    None,
]
for html in test_cases:
    result = clean_weibo_text(html or "")
    has_html = "<" in result and ">" in result
    status = "❌" if has_html else "✅"
    print(f"  {status} 输入: {repr(html)[:50]} → 输出: {repr(result[:50])}")

print()
print("=" * 60)
print("全部测试完成！")
print("=" * 60)
