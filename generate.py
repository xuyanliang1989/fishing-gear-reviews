#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钓鱼装备评测站 · 每日自动发文脚本
由 GitHub Actions 调用，每天选下一个未写的题目，调用 LLM 生成英文评测文章，
写入 _posts/ 并提交。首页 index.md 用 Jekyll Liquid 自动列出所有文章，无需手动改。
依赖：仅标准库（urllib / json / os / glob / re / datetime / sys）。

变现说明（重要）：本站的 {{PRODUCT_LINK}} 占位符将来优先替换成
钓鱼专属高佣联盟（Bass Pro/Cabela's 5%、Tackle Warehouse 5-7%、Karl's 8%、
Simms 7-10%、Piscifun 10%+、Mustad/West Marine 15-20%），而非只靠亚马逊 3%。
这样同等流量下收益是纯亚马逊的 2-6 倍。
"""

import os
import glob
import json
import sys
import datetime
import re
import urllib.request

# ===== 第一批 30 个钓鱼装备题目（按顺序，写完一个跳下一个）=====
TOPICS = [
    "Best Spinning Reels Under $100",
    "Best Spinning Reels Under $200",
    "Best Baitcasting Reels Under $100",
    "Best Fishing Rods for Beginners in 2026",
    "Best Ultralight Spinning Reels for Trout",
    "Best Bass Fishing Rods Under $150",
    "Best Fish Finders Under $300",
    "Best Fish Finders Under $500",
    "Best Fish Finder GPS Combo for Kayak Fishing",
    "Best Fishing Kayaks Under $500",
    "Best Fishing Kayaks Under $1000",
    "Best Tackle Boxes for Bass Fishing",
    "Best Fishing Pliers and Line Cutters",
    "Best Fishing Line for Spinning Reels",
    "Best Braided Fishing Line for Bass",
    "Best Bass Lures for Beginners",
    "Best Crankbaits for Spring Bass",
    "Best Soft Plastic Baits for Bass",
    "Best Fly Fishing Rods Under $300",
    "Best Fly Fishing Reels for Beginners",
    "Best Waders for Fly Fishing",
    "Best Ice Fishing Rods and Combos",
    "Best Ice Fishing Augers (Manual vs Power)",
    "Best Saltwater Spinning Reels Under $200",
    "Best Surf Fishing Rods for the Beach",
    "Best Catfish Rods and Reel Combos",
    "Best Crappie Rods for Panfish",
    "Best Landing Nets for Bass and Kayak Fishing",
    "Best Fishing Sunglasses for Glare Reduction",
    "Bank Fishing Essentials: Complete Gear Checklist for Shore Anglers",
]


def slugify(s: str) -> str:
    s = s.lower().replace("$", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def bootstrap():
    """首次运行时，若仓库里没有 _config.yml / index.md，自动补上。"""
    if not os.path.exists("_config.yml"):
        with open("_config.yml", "w", encoding="utf-8") as f:
            f.write("title: Fishing Gear Reviews\n")
    if not os.path.exists("index.md"):
        idx = (
            "---\n"
            "title: Fishing Gear Reviews\n"
            "---\n\n"
            "# Fishing Gear Reviews\n\n"
            "No-nonsense fishing gear reviews for US anglers. "
            "We compare real rods, reels, fish finders and tackle so you can buy with confidence.\n\n"
            "## Latest Reviews\n\n"
            "<ul>\n"
            "{% for post in site.posts %}\n"
            '  <li><a href="{{ post.url | relative_url }}">{{ post.title }}</a></li>\n'
            "{% endfor %}\n"
            "</ul>\n"
        )
        with open("index.md", "w", encoding="utf-8") as f:
            f.write(idx)


def next_topic():
    os.makedirs("_posts", exist_ok=True)
    existing = [os.path.basename(f) for f in glob.glob("_posts/*.md")]
    for t in TOPICS:
        sl = slugify(t)
        if any(f.endswith("-{}.md".format(sl)) for f in existing):
            continue
        return t, sl
    return None, None


SYSTEM = """You are a senior fishing gear reviewer writing buying-guide articles for US anglers. Write in fluent, natural, conversational American English.

Voice: like a knowledgeable friend giving honest advice — never salesy, never ad-like. Avoid hype words like "revolutionary" or "game-changing".

For every article you write, follow these HARD rules:
1. Use REAL, currently available fishing products with REAL prices in USD. Never invent fake brand names, model numbers, or products. Cover real brands anglers actually use (Shimano, Daiwa, Penn, Abu Garcia, Lew's, Pflueger, Garmin, Humminbird, Lowrance, Bass Pro Shops, Yeti, etc.).
2. If you are unsure about a specific spec or price, write [需核实] (needs verification) instead of guessing. Never fabricate data.
3. Exact structure, in order:
   - H1 title = the topic itself, verbatim.
   - ~100-word opening that drops the reader into a real pain-point scenario (e.g., a reel that freezes up mid-fight, line snapping on a trophy bass, or getting skunked because of the wrong lure).
   - A short "What to look for" buying-guide section (~100-150 words, 3-4 bullet points of the key criteria that actually matter) right after the opening and before the product reviews.
   - 5 to 7 product reviews. For EACH: product name, price range, exactly 3 pros (each 1-2 full sentences), exactly 1 con (1-2 full sentences), a 2-3 sentence real-world use scenario, and a "Best for:" line saying who should buy it.
   - A comparison table in MARKDOWN PIPE SYNTAX — mandatory. It must include a header row like `| Product | Price | Best For | Key Strength |` and a separator row `|---|---|---|---|`, then one row per product. Do NOT use any other table style.
   - A section with the EXACT heading `## Final Verdict` giving a clear top pick and a budget pick.
   - A section with the EXACT heading `## FAQ` containing exactly 5 FAQs with 2-3 sentence answers each.
   - The comparison table, the `## Final Verdict` heading, and the `## FAQ` heading are ALL mandatory and must appear in every article. Never omit them.
4. After EVERY product name, insert the exact placeholder {{PRODUCT_LINK}} (keep the curly braces, do not replace or explain it).
6. Editorial quality rules (mandatory — these come from a real audit of already-published articles):
   - The H1 title appears EXACTLY ONCE, at the very top. Never repeat the topic title as a section heading. Each product gets its own descriptive H2 heading (e.g., `## Shimano Sedona FJ`), never the article title.
   - NEVER add meta-commentary about your own list items (no "yes, a third one", no "one more", no "last but not least"). List the pros and cons plainly.
   - First-person voice is fine for GENERALIZED experience ("in my experience, reels in this size handle..."). NEVER fabricate specific verifiable personal stories — no exact trip dates, no exact locations, no exact catch counts like "hundreds of bass". For specific claims write "anglers report", "owners commonly find", or cite the spec.
   - Rotate your product lineup across articles: do not lean on the same 2-3 famous defaults every time. Let a different product take the top pick when it honestly deserves it, so each article feels like a fresh roundup.
   - FAQ questions must be specific to THIS topic and answer real buyer questions — no generic filler like "is this worth it".
   - Never fabricate awards, star ratings, review counts, or quotes from named publications.
7. Length: write AT LEAST 2200 words, target 2200-2600. This is a HARD requirement — never stop before 2200 words. If you are running short, add more detail to each product description and expand the FAQs until you reach the minimum.
8. Output ONLY the markdown article. Start with the H1 title. No preamble, no "Here is your article"."""


def call_llm(topic: str, today: str) -> str:
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        print("ERROR: LLM_API_KEY secret is not set.")
        sys.exit(1)
    # 默认走 DeepSeek（api.deepseek.com，国产、国内可直连；充 ¥1 起即可，约 ¥0.01/篇，30篇≈¥0.3）。
    # 注意用 `or` 兜底：GitHub Actions 对"未创建的密钥"会传空字符串（不是不存在），
    # os.environ.get(key, 默认值) 遇到空串不会用默认值 → URL 变空 → 秒崩。用 or 同时防"没设置"和"设为空串"。
    base = (os.environ.get("LLM_BASE_URL") or "https://api.deepseek.com").rstrip("/")
    model = os.environ.get("LLM_MODEL") or "deepseek-chat"

    user = (
        "Write the full article for this exact topic:\n\n"
        + topic
        + "\n\nToday is "
        + today
        + "."
    )
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
            "max_tokens": 5000,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        base + "/chat/completions",
        data=payload,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=150) as r:
            data = json.loads(r.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("API ERROR:", e)
        sys.exit(1)

    # 去掉可能的代码围栏
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    return text


def qa_ok(text: str) -> bool:
    words = len(text.split())
    if words < 1800:
        print("QA FAIL: article too short ({} words). Not publishing.".format(words))
        return False
    if "Final Verdict" not in text or "FAQ" not in text or "|" not in text:
        print("QA FAIL: missing required section or comparison table.")
        return False
    low = text.lower()
    for w in ["as an ai", "i cannot", "i can't", "i am unable", "i'm unable"]:
        if w in low:
            print("QA FAIL: model refused or gave meta-response.")
            return False
    return True


def main():
    bootstrap()
    topic, sl = next_topic()
    if not topic:
        print("ALL 30 TOPICS DONE — nothing to publish today.")
        sys.exit(0)

    today = datetime.date.today().strftime("%Y-%m-%d")
    article = call_llm(topic, today)
    if not qa_ok(article):
        sys.exit(1)

    # 用 Jekyll {% raw %} 包裹正文，保留 {{PRODUCT_LINK}} 占位符不被 Liquid 解析
    fname = "_posts/{}-{}.md".format(today, sl)
    content = (
        "---\ntitle: \"" + topic + "\"\n---\n\n{% raw %}\n"
        + article
        + "\n{% endraw %}\n"
    )
    with open(fname, "w", encoding="utf-8") as f:
        f.write(content)

    words = len(article.split())
    print("PUBLISHED: " + topic)
    print("FILE: " + fname)
    print("WORDS: " + str(words))
    print("URL: /{}/{}/{}/{}.html".format(today[:4], today[5:7], today[8:10], sl))


# 直接调用（不用 if __name__ == "__main__" 判断：那个写法在复制粘贴时
# 极易混入零宽空格导致静默失败——任务显示绿勾但啥也不干）。
main()
