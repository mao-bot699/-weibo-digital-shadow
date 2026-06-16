# 数字影子

> 输入一个微博 UID，自动抓取公开微博数据，并用大模型生成一份 11 维度人物画像报告。

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Web-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![LLM](https://img.shields.io/badge/LLM-OpenAI%20Compatible-6C63FF)](数字影子-公开版/docs/USAGE.md)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

![数字影子预览](数字影子-公开版/docs/assets/preview.svg)

**数字影子** 是一个面向公开社交数据分析的 AI Agent 小工具。它可以根据微博 UID 获取公开可见内容，并生成包含性格、兴趣、表达风格、互动关系、多平台线索和内容主题演变的分析报告。

适合用于：

- 自媒体账号研究和竞品内容观察
- 公开人物的内容画像和表达风格分析
- LLM Agent / OSINT / 社交媒体分析项目学习
- Python + Flask + 大模型应用的完整示例

如果这个项目对你有帮助，欢迎点一个 Star，后续会继续补充更多平台和更完整的分析模板。

## 快速开始

```bash
git clone https://github.com/mao-bot699/-weibo-digital-shadow.git
cd -weibo-digital-shadow/数字影子-公开版
pip install flask flask-cors openai requests
cp config.py.example config.py
python3 server.py
```

然后打开 `http://localhost:8080`。

## 项目入口

- [项目源码与完整 README](数字影子-公开版/README.md)
- [详细使用指南](数字影子-公开版/docs/USAGE.md)
- [更新日志](数字影子-公开版/docs/CHANGELOG.md)

## 核心能力

| 能力 | 说明 |
|------|------|
| 人物画像 | 身份标签、性格特征、价值观、生活方式 |
| 主题演变 | 分析内容主题是否随时间发生变化 |
| 互动关系 | 提取高频 @对象，生成社交圈层线索 |
| 多平台线索 | 从 bio 和正文中匹配 X、Instagram、B站、小红书、抖音等账号 |
| 追问补充 | 基于已有报告继续追加上下文和深度分析 |

## Topics 建议

`weibo` `ai-agent` `llm` `osint` `social-media-analysis` `python` `flask` `openai` `chinese`

## License

MIT
