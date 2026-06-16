# 更新日志

## git1 (2026-06-16)

### 新增功能
- **互动关系图谱**：新增 `extract_mentions()` 函数和 `/api/mentions` 接口，从微博中提取 @提及 的高频用户，前端新增「互动关系图谱」卡片展示 Top 10 互动对象
- **多平台线索提取**：新增 `extract_social_links()` 函数和 `/api/social_links` 接口，从 bio 和正文中匹配 Twitter/X、Instagram、B站、小红书、抖音的账号线索，前端新增「多平台线索」卡片
- **分析报告扩展**：agent.py prompt 新增「互动关系分析」和「多平台线索分析」两个章节，报告结构从 8 章扩展为 10 章

### Bug 修复
- 修复 `follow_count` 前端未传递导致报告关注数显示为 0
- 删除不可用的搜索功能（移动端 API 反爬），界面保留 UID 直接输入
- 修复 `renderSearchResults` 模板字符串语法错误
- `clean_weibo_text` 公开化（`_clean_text` → `clean_weibo_text`），增加 HTML 标签去除
- 修复下载失败：`downloadReport()` 现在携带 posts 数据请求，后端加固空数据判断
- 修复 @提及 正则贪婪匹配导致的截断问题（如 `@卢伟冰:` 被截断为 `@卢伟冰`）

### 优化
- `max_tokens` 从 8000 提升到 16000，避免报告被截断
- `/api/analyze` 后端自动提取 mentions 和 social_links（前端不传时）
- `localStorage` 新增 `last_posts` 存储，支持下载时携带帖子数据
- 测试文件 `test_scrapers.py` 全部用例通过
