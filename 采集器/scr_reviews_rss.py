"""
深挖 C 成功: 老 RSS customerreviews 分页接口仍可用
  https://itunes.apple.com/us/rss/customerreviews/page={N}/id={appid}/sortby=mostrecent/json
优点:
  - 每页 50 条 (内嵌 JSON 方案只有 10 条)
  - sortby=mostrecent -> 无 helpfulReview 负向偏置
  - page10 只剩 13 条 -> 每 app 最多约 463 条
验证: 字段完整性/去重/星级分布/正文长度
"""
import json, re, urllib.request, urllib.error, time, os
from collections import Counter

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
OUT = "/Users/maike/Desktop/iOS副业调研_2026-11-09/采集数据/v3_reviews"

def get(u, tries=3):
    for i in range(tries):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(u, headers={"User-Agent": UA}), timeout=40
            ).read().decode("utf-8", "ignore")
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(1.5 * (i + 1))

def rss_reviews(appid, page):
    u = f"https://itunes.apple.com/us/rss/customerreviews/page={page}/id={appid}/sortby=mostrecent/json"
    h = get(u)
    try:
        b = json.loads(h)
    except Exception:
        return []
    feed = b.get("feed", {})
    entries = feed.get("entry", [])
    out = []
    if isinstance(entries, dict): entries = [entries]
    for e in entries:
        # 第一个 entry 常常是 app 本身(没有 im:rating)
        if "im:rating" not in e: continue
        a = e.get("author", {}).get("name", {})
        aname = a.get("label") if isinstance(a, dict) else str(a)
        out.append({
            "review_id": e.get("id", {}).get("label", "") if isinstance(e.get("id"), dict) else "",
            "title": (e.get("title", {}) or {}).get("label", "") if isinstance(e.get("title"), dict) else "",
            "body": (e.get("content", {}) or {}).get("label", "") if isinstance(e.get("content"), dict) else "",
            "stars": int(e.get("im:rating", {}).get("label", 0)) if isinstance(e.get("im:rating"), dict) else 0,
            "version": (e.get("im:version", {}) or {}).get("label", "") if isinstance(e.get("im:version"), dict) else "",
            "author": aname or "",
            "url": (e.get("link", {}) or {}).get("attributes", {}).get("href", "") if isinstance(e.get("link"), dict) else "",
            "page": page,
        })
    return out

if __name__ == "__main__":
    import sys
    aid = sys.argv[1] if len(sys.argv) > 1 else "1443835927"
    print("=" * 78)
    print(f"深挖C验证: RSS 分页 (app id={aid})")
    print("=" * 78)
    allrows, seen = [], set()
    for pg in range(1, 12):
        try:
            rows = rss_reviews(aid, pg)
        except Exception as e:
            print(f"  page{pg}: ERR {str(e)[:50]}")
            break
        new = [r for r in rows if r["review_id"] not in seen]
        for r in new: seen.add(r["review_id"])
        allrows.extend(new)
        print(f"  page{pg:>2}: 取到 {len(rows):>2} 条, 去重新增 {len(new):>2} 条, 累计 {len(allrows)}")
        if len(rows) < 20:
            print("   -> 到达末尾")
            break
        time.sleep(0.6)

    print(f"\n唯一评论总数: {len(allrows)}")
    if allrows:
        st = Counter(r["stars"] for r in allrows)
        tot = sum(st.values())
        print(f"星级分布: " + "  ".join(f"{k}星={st[k]}({st[k]/tot*100:.1f}%)" for k in sorted(st, reverse=True)))
        print(f"低星(1-2星)占比: {(st[1]+st[2])/tot*100:.1f}%")
        lens = sorted(len(r["body"]) for r in allrows)
        print(f"正文长度: 中位 {lens[len(lens)//2]}  最大 {lens[-1]}  最小 {lens[0]}")
        trunc = sum(1 for r in allrows if len(r["body"]) >= 1400)
        print(f"疑似截断(>=1400字符): {trunc}/{len(allrows)} ({trunc/len(allrows)*100:.1f}%)")
        dates = sorted(r["date"] for r in allrows if r.get("date"))
        print(f"带日期字段: {len(dates)}/{len(allrows)}")
        print(f"\n首条样例: {allrows[0]['stars']}星 | {allrows[0]['title'][:40]} | {allrows[0]['body'][:120]}")
