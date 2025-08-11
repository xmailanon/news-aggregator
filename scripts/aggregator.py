import json, time, hashlib, sys
from urllib.parse import urlparse
import feedparser

REQUEST_HEADERS = {"User-Agent": "DysonxNewsBot/1.0 (+https://dysonx.com)"}

def load_feeds():
    try:
        with open("feeds.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        # 打印错误位置附近的上下文，快速定位逗号/引号问题
        with open("feeds.json", "r", encoding="utf-8") as f2:
            text = f2.read()
        start = max(e.pos - 40, 0)
        end = min(e.pos + 40, len(text))
        context = text[start:end].replace("\n", "\\n")
        print(f"[error] feeds.json 解析失败: {e}. 附近: ...{context}...")
        sys.exit(1)
    feeds = cfg.get("feeds", [])
    max_items = int(cfg.get("max_items", 200))
    if not isinstance(feeds, list) or not feeds:
        print('[error] feeds 字段必须是非空数组，例如 {"feeds":["https://..."]}')
        sys.exit(1)
    return feeds, max_items

def normalize_ts(entry):
    for k in ("published_parsed", "updated_parsed"):
        v = getattr(entry, k, None)
        if v:
            return int(time.mktime(v))
    return int(time.time())

def source_from(link: str) -> str:
    host = urlparse(link).netloc.lower()
    return host.replace("www.", "")

def main():
    feeds, max_items = load_feeds()
    items = []

    for url in feeds:
        try:
            d = feedparser.parse(url, request_headers=REQUEST_HEADERS)
            if d.bozo and getattr(d, "bozo_exception", None):
                print(f"[warn] feed error: {url} -> {d.bozo_exception}")
            for e in d.entries[:50]:
                link = getattr(e, "link", "").strip()
                if not link:
                    continue
                title = getattr(e, "title", "(untitled)").strip()
                ts = normalize_ts(e)
                sid = hashlib.sha1(link.encode("utf-8")).hexdigest()[:12]
                items.append({
                    "id": sid,
                    "title": title,
                    "url": link,
                    "source": source_from(link),
                    "published": ts
                })
        except Exception as ex:
            print(f"[error] {url} -> {ex}")
        time.sleep(0.5)  # 礼貌延时

    # 去重 + 排序
    seen, deduped = set(), []
    for it in sorted(items, key=lambda x: x["published"], reverse=True):
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        deduped.append(it)

    out = {
        "updated": int(time.time()),
        "items": deduped[:max_items],
        "build_id": int(time.time())
    }
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"OK: {len(out['items'])} items from {len(feeds)} feeds")

if __name__ == "__main__":
    main()
