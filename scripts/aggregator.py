import json, time, hashlib, sys, os
from urllib.parse import urlparse
import feedparser

REQUEST_HEADERS = {"User-Agent": "DysonxNewsBot/1.0 (+https://dysonx.com)"}

def load_config():
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
    max_days  = int(cfg.get("max_days", 30))
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

def hash_file(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()

def main():
    feeds, max_items, max_days = load_config()
    now = int(time.time())
    cutoff = now - max_days * 86400

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
        time.sleep(0.3)

    seen, deduped = set(), []
    for it in sorted(items, key=lambda x: x["published"], reverse=True):
        if it["url"] in seen: continue
        seen.add(it["url"]); deduped.append(it)

    out = {
        "updated": now,
        "items": deduped[:max_items],
        "build_id": now
    }

    # ==== 比较变更前后 news.json 哈希 ====
    old_hash = hash_file("news.json")

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    new_hash = hash_file("news.json")

    # ==== 强制写入 .last_run（不影响是否 commit）====
    with open(".last_run", "w", encoding="utf-8") as hb:
        hb.write(str(now))

    # ==== Git 提交控制逻辑 ====
    if old_hash != new_hash:
        print("[info] 内容有更新，执行 git 提交")
        os.system("git config user.name 'bot'")
        os.system("git config user.email 'bot@users.noreply.github.com'")
        os.system("git add news.json .last_run")
        os.system("git commit -m 'auto update news'")
        os.system("git pull --rebase origin main || true")
        os.system("git push origin main || echo 'push failed'")
    else:
        print("[info] 内容无变化，跳过 git 提交")

    print(f"[info] 输出 {len(out['items'])} 条（原始 {len(items)} 条）")

if __name__ == "__main__":
    main()