import json, time, hashlib, sys
from urllib.parse import urlparse
import feedparser

REQUEST_HEADERS = {"User-Agent": "DysonxNewsBot/1.0 (+https://dysonx.com)"}

def load_config():
    try:
        with open("feeds.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        with open("feeds.json", "r", encoding="utf-8") as f2:
            text = f2.read()
        start = max(e.pos - 40, 0); end = min(e.pos + 40, len(text))
        context = text[start:end].replace("\n", "\\n")
        print(f"[error] feeds.json 解析失败: {e}. 附近: ...{context}...")
        sys.exit(1)

    feeds = cfg.get("feeds", [])
    if not isinstance(feeds, list) or not feeds:
        print('[error] feeds 必须是非空数组，例如 {"feeds":["https://..."]}')
        sys.exit(1)

    max_items = int(cfg.get("max_items", 200))
    max_days  = int(cfg.get("max_days", 30))  # 只要最近 N 天
    return feeds, max_items, max_days

def normalize_ts(entry):
    # 尽量拿发布时间；没有就用更新时间；都没有就返回当前时间
    for k in ("published_parsed", "updated_parsed"):
        v = getattr(entry, k, None)
        if v:
            return int(time.mktime(v))
    return int(time.time())

def host_of(link: str) -> str:
    host = urlparse(link).netloc.lower()
    return host.replace("www.", "")

def main():
    feeds, max_items, max_days = load_config()
    now = int(time.time())
    cutoff = now - max_days * 86400  # UTC 截止时间
    print(f"[info] 抓取 {len(feeds)} 源；时间窗口：最近 {max_days} 天，cutoff={cutoff}")

    items = []
    for url in feeds:
        try:
            d = feedparser.parse(url, request_headers=REQUEST_HEADERS)
            if d.bozo and getattr(d, "bozo_exception", None):
                print(f"[warn] feed 解析告警: {url} -> {d.bozo_exception}")
            for e in d.entries[:100]:
                link = getattr(e, "link", "").strip()
                if not link:
                    continue
                ts = normalize_ts(e)

                # 时间过滤：早于 cutoff 的一律丢弃；未来时间（服务器时钟问题）也丢弃
                if ts < cutoff or ts > now + 3600:
                    continue

                title = getattr(e, "title", "(untitled)").strip()
                sid = hashlib.sha1(link.encode("utf-8")).hexdigest()[:12]
                items.append({
                    "id": sid,
                    "title": title,
                    "url": link,
                    "source": host_of(link),
                    "published": ts
                })
        except Exception as ex:
            print(f"[error] 抓取失败 {url} -> {ex}")
        time.sleep(0.4)  # 轻微间隔，礼貌抓取

    # 去重 + 按时间倒序
    seen, deduped = set(), []
    for it in sorted(items, key=lambda x: x["published"], reverse=True):
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        deduped.append(it)

    out = {
        "updated": now,
        "items": deduped[:max_items],
        "build_id": now
    }
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"[info] 输出 {len(out['items'])} 条（原始 {len(items)} 条，窗口 {max_days} 天）")

if __name__ == "__main__":
    main()
