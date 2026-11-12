# -*- coding: utf-8 -*-
"""Bot4 修正版：全分类 App Store 排行榜采集
修正点：GENRES 使用 Apple 当前真实 genre ID（旧映射已失效，标签张冠李戴）。
输出：charts.jsonl, _collect_log.txt
"""
import json, os, re, time, urllib.request, urllib.error
from datetime import datetime, timezone

D = "/Users/maike/Desktop/iOS副业调研_2026-11-09/采集器"
O = os.path.join(D, "out_bot4")
os.makedirs(O, exist_ok=True)
LOG = os.path.join(O, "_collect_log.txt")

# Apple 当前真实 genre ID（2026-11-10 实测：逐个请求 RSS 读 title.label 验证）
GENRES = {
    "6000": "Business",
    "6001": "Weather",
    "6002": "Utilities",
    "6003": "Travel",
    "6004": "Sports",
    "6005": "Social-Networking",
    "6006": "Reference",
    "6007": "Productivity",
    "6008": "Photo-Video",
    "6009": "News",
    "6010": "Navigation",
    "6011": "Music",
    "6012": "Lifestyle",
    "6013": "Health-Fitness",
    "6015": "Finance",
    "6016": "Entertainment",
    "6017": "Education",
    "6018": "Books",
    "6020": "Medical",
    "6021": "Magazines",
    "6023": "Food-Drink",
    "6024": "Shopping",
    "6026": "Developer-Tools",
    "6027": "Graphics-Design",
}
TYPES = ["topfreeapplications", "toppaidapplications", "topgrossingapplications"]
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"}


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def jget(url, timeout=45, retries=3):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def main():
    rows, fails, empties = [], [], []
    for t in TYPES:
        for gid, gname in GENRES.items():
            u = f"https://itunes.apple.com/us/rss/{t}/limit=100/genre={gid}/json"
            try:
                j = jget(u)
                feed = j.get("feed", {})
                title = feed.get("title", {}).get("label", "")
                ents = feed.get("entry", [])
                if not ents:
                    empties.append((t, gname, title))
                    log(f"[榜单] EMPTY {t}/{gname}({gid}) feed_title={title}")
                    continue
                for rank, e in enumerate(ents, 1):
                    idl = e.get("id", {}).get("label", "")
                    m = re.search(r"id(\d+)", idl)
                    rows.append({
                        "chart": t,
                        "chart_name": {"topfreeapplications": "免费榜",
                                       "toppaidapplications": "付费榜",
                                       "topgrossingapplications": "畅销榜"}[t],
                        "genre_id": gid,
                        "genre_name": gname,
                        "rank": rank,
                        "app_id": m.group(1) if m else None,
                        "app_name": e.get("im:name", {}).get("label"),
                        "url": idl,
                        "summary": (e.get("summary", {}).get("label") or "")[:300],
                        "icon": (e.get("im:image") or [{}])[-1].get("label"),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                    })
                log(f"[榜单] {t}/{gname} -> {len(ents)} 条")
            except Exception as e:
                fails.append((t, gname, f"{type(e).__name__}: {str(e)[:80]}"))
                log(f"[榜单] FAIL {t}/{gname}({gid}): {type(e).__name__} {str(e)[:80]}")
            time.sleep(0.6)

    with open(os.path.join(O, "charts.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log(f"写出 charts.jsonl: {len(rows)} 条")
    log(f"FAIL={len(fails)} EMPTY={len(empties)}")
    for x in fails:
        log(f"  FAIL -> {x}")
    for x in empties:
        log(f"  EMPTY -> {x}")
    log("=== 完成 charts(修正版) ===")


if __name__ == "__main__":
    main()
