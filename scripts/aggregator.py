import feedparser, json, time, hashlib
from urllib.parse import urlparse

# 固定新闻源 RSS
FEEDS = [
    "http://www.bbc.co.uk/zhongwen/simp/index.xml",      # BBC 中文
    "https://rss.dw.com/xml/podcast_radio_chi_all",      # 德国之声中文
    "https://www.voachinese.com/api/zyrmteqkmr"          # VOA 中文要用具体栏目 RSS，这里用新闻总源
]

def normalize_ts(entry):
    if getattr(entry, "published_parsed", None):
        return int(time.mktime(entry.published_parsed))
    if getattr(entry, "updated_parsed", None):
        return int(time.mktime(entry.updated_parsed))
    return int(time.time())

def source_name(link):
    return urlparse(link).netloc.replace("www.", "")

items = []
for url in FEEDS:
    d = feedparser.parse(url)
    for e in d.entries[:30]:
        link = e.link
        title = e.title if hasattr(e, "title") else "(untitled)"
        ts = normalize_ts(e)
        sid = hashlib.sha1(link.encode("utf-8")).hexdigest()[:12]
        items.append({
            "id": sid,
            "title": title,
            "url": link,
            "source": source_name(link),
            "published": ts
        })

# 去重并按时间排序
seen = set()
deduped = []
for it in sorted(items, key=lambda x: x["published"], reverse=True):
    if it["url"] in seen:
        continue
    seen.add(it["url"])
    deduped.append(it)

# 保存 news.json
with open("news.json", "w", encoding="utf-8") as f:
    json.dump({"updated": int(time.time()), "items": deduped[:100]}, f, ensure_ascii=False, indent=2)

print(f"OK: {len(deduped)} items")

