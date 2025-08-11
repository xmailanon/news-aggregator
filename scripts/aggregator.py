# scripts/aggregator.py  —— 兼容字符串/对象两种 feeds，含时间过滤
import json, time, hashlib, sys
from urllib.parse import urlparse
import feedparser

REQUEST_HEADERS = {"User-Agent": "DysonxNewsBot/1.0 (+https://dysonx.com)"}

def load_config():
    """读取 feeds.json，兼容:
       ["url1","url2", ...] 以及
       [{"url":"..."}, {"group":"xx","url":"..."} , ...] 混用。"""
    try:
        with open("feeds.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        with open("feeds.json", "r", encoding="utf-8") as f2:
            txt = f2.read()
        start = max(e.pos - 40, 0); end = min(e.pos + 40, len(txt))
        ctx = txt[start:end].replace("\n", "\\n")
        print(f"[error] feeds.json 解析失败: {e}. 附近: ...{ctx}...")
        sys.exit(1)

    raw = cfg.get("feeds", [])
    if not isinstance(raw, list) or not raw:
        print("[error] feeds 必须是非空列表")
        sys.exit(1)

    feeds = []
    for entry in raw:
        if isinstance(entry, str):
            url = entry.strip()
        elif isinstance(entry, dict):
            url = str(entry.get("url", "")).strip()
        else:
            url = ""
        if url:
            feeds.append(url)

    if not feeds:
        print("[error] 未解析到任何有效的 feed URL")
        sys.exit(1)

    max_items = int(cfg.get("max_items", 200))
    max_days  = int(cfg.get("max_days", 30))  # 只收最近 N 天
    return feeds, max_items, max_days

def normalize_ts(entry):
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
    cutoff = now - max_days * 86400
    print(f"[info] 源数量: {len(feeds)} · 时间窗口: {max_days}天 · cutoff={cutoff}")

    items = []
    for url in feeds:
        try:
            d = feedparser.parse(url, request_headers=REQUEST_HEADERS)
            if d.bozo and getattr(d, "bozo_exception", None):
                print(f"[warn] 解析告警: {url} -> {d.bozo_exception}")
            for e in d.entries[:100]:
                link = getattr(e, "link", "").strip()
                if not link:
                    continue
                ts = normalize_ts(e)
                # 时间过滤（丢弃过旧/未来）
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
        time.sleep(0.3)  # 轻微间隔

    # 去重 + 时间倒序
    seen, deduped = set(), []
    for it in sorted(items, key=lambda x: x["published"], reverse=True):
        if it["url"] in seen: continue
        seen.add(it["url"]); deduped.append(it)

    out = {
        "updated": now,
        "items": deduped[:max_items],
        "build_id": now
    }
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    import time

    with open(".last_run", "w", encoding="utf-8") as f:
    f.write(str(int(time.time())))


    print(f"[info] 输出 {len(out['items'])} 条（原始 {len(items)} 条，窗口 {max_days}天，max_items={max_items}）")

if __name__ == "__main__":
    main()
