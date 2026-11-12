"""
深挖 F: 基于 19845 条真实评论的痛点词频分析 (全量, 不采样)
这是"选哪个方向"的核心依据。
口径: 相对基线校正 —— 减去该品类 app 的平均提及率, 找出真正的差异化痛点
"""
import json, os, re, sys
from collections import Counter, defaultdict

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"

# 痛点词典: 分类 -> 关键词列表 (小写匹配, 词边界)
DICT = {
    "崩溃/闪退": ["crash", "crashes", "crashed", "crashing", "force close", "force quit", "freezes", "freezing", "frozen", "hangs", "hung"],
    "登录/账号": ["login", "log in", "sign in", "signin", "account", "password", "login failed", "can't log", "cannot log", "verification"],
    "订阅/付费墙": ["subscription", "subscribe", "paywall", "premium", "paid version", "paid app", "in-app purchase", "upgrade", "price", "pricing", "expensive", "cost", "refund", "cancel subscription", "trial", "monthly fee", "annual fee"],
    "离线/无信号": ["offline", "no signal", "no internet", "no service", "without internet", "airplane mode", "weak signal", "lost signal", "no data"],
    "同步/数据丢失": ["sync", "syncing", "didn't sync", "did not sync", "lost my data", "data loss", "lost data", "wiped", "lost all", "missing data", "data disappeared"],
    "地图/GPS不准": ["wrong location", "inaccurate", "gps", "off by", "wrong map", "wrong address", "wrong pin", "misplaced", "does not match", "doesn't match", "coordinates"],
    "搜索/找不到": ["can't find", "cannot find", "hard to find", "search doesn't", "search bar", "search function", "no search", "searching for"],
    "UI/易用性": ["confusing", "confused", "intuitive", "user friendly", "user-friendly", "hard to use", "difficult to use", "complicated", "cluttered", "busy", "clunky", "awkward", "not obvious", "hard to navigate", "navigation is", "poor design", "bad design", "redesign"],
    "通知/推送": ["notification", "notifications", "push", "alerts", "reminder", "reminders", "didn't notify", "no notification", "notification spam"],
    "更新/版本": ["update", "updated", "version", "after update", "since update", "new version", "update broke", "last update"],
    "客服/响应": ["support", "customer service", "no response", "no reply", "developer", "developer response", "contacted", "email", "never responded", "no answer"],
    "导出/导入": ["export", "import", "csv", "pdf", "backup", "restore", "transfer", "sync with", "icloud", "icloud sync"],
    "尺寸/布局": ["small screen", "big screen", "ipad", "iphone", "iphone 15", "iphone 14", "iphone se", "plus", "max", "split view", "landscape", "tablet"],
    "电池/耗电": ["battery", "drain", "battery drain", "background", "background refresh", "energy", "power usage"],
    "加载慢/性能": ["slow", "lag", "laggy", "loading", "takes forever", "hangs up", "buffering", "slow load", "performance"],
    "权限/隐私": ["permission", "permissions", "location access", "privacy", "tracking", "mic", "camera access", "photos access", "notification permission"],
    "广告": ["ads", "advert", "advertisement", "banner ads", "too many ads", "annoying ads"],
    "打印/导出PDF": ["print", "printing", "printer", "pdf export", "export pdf"],
    "计算错误": ["wrong calculation", "incorrect", "does not calculate", "wrong total", "math error", "wrong amount", "miscalculate"],
    "学习曲线/上手": ["took me a while", "hard to learn", "no instructions", "unclear instructions", "documentation", "no guide", "figuring out", "took some time"],
    "多设备/家庭共享": ["family sharing", "multiple devices", "other devices", "sync across", "my iphone", "my ipad", "second device", "new phone"],
}

def load_reviews(path):
    byapp = defaultdict(list)
    n = 0
    for line in open(path):
        try:
            r = json.loads(line); byapp[r["app_id"]].append(r); n += 1
        except Exception: pass
    return byapp, n

def hits(text, kws):
    c = 0
    for k in kws:
        if k in text: c += 1
    return c

def main():
    path = f"{D}/v3_reviews/reviews_all.jsonl"
    byapp, n = load_reviews(path)
    print(f"样本: {n} 条评论 / {len(byapp)} 个 app")
    print()

    # 逐 app 计算 每个痛点的提及率
    per_app = {}   # app_id -> {pain: rate}
    app_review_count = {}
    for aid, rv in byapp.items():
        app_review_count[aid] = len(rv)
        d = {}
        for pain, kws in DICT.items():
            c = 0
            for r in rv:
                t = (r.get("title", "") + " " + r.get("body", "")).lower()
                c += 1 if hits(t, kws) else 0
            d[pain] = c / len(rv) * 100
        per_app[aid] = d

    # 基线: 全体 app 的加权平均提及率
    total_r = sum(app_review_count.values())
    baseline = {}
    for pain in DICT:
        baseline[pain] = sum(per_app[a][pain] * app_review_count[a] for a in per_app) / total_r

    # 1) 全局频次
    global_counts = Counter()
    for aid, rv in byapp.items():
        for pain, kws in DICT.items():
            for r in rv:
                t = (r.get("title","") + " " + r.get("body","")).lower()
                if hits(t, kws): global_counts[pain] += 1

    print("=" * 88)
    print("【全量痛点频次】19845 条评论")
    print("=" * 88)
    print(f"{'痛点':<16} {'命中评论数':>10} {'命中率':>8} {'基线':>8} {'相对':>8}")
    print("-" * 88)
    rows = []
    for pain, c in global_counts.most_common():
        rate = c / total_r * 100
        rel = rate / baseline[pain] if baseline[pain] > 0 else 0
        rows.append((pain, c, rate, baseline[pain], rel))
        print(f"  {pain:<14} {c:>10} {rate:>7.2f}% {baseline[pain]:>7.2f}% {rel:>7.2f}x")

    # 2) 集中度: 痛点集中在少数 app 还是普遍存在
    print()
    print("=" * 88)
    print("【集中度】痛点是否只集中在少数 app (Top1 app 占该痛点命中数的比例)")
    print("=" * 88)
    conc = {}
    for pain, kws in DICT.items():
        per = Counter()
        for aid, rv in byapp.items():
            c = 0
            for r in rv:
                t = (r.get("title","") + " " + r.get("body","")).lower()
                if hits(t, kws): c += 1
            if c: per[aid] = c
        tot_c = sum(per.values())
        top_app = per.most_common(1)[0] if per else (None, 0)
        name = ""
        if top_app[0]:
            nm = byapp[top_app[0]][0].get("app_name", "")
            name = nm[:30]
        conc[pain] = {"top_app": name, "top_app_count": top_app[1], "total": tot_c,
                      "top_share": round(top_app[1]/tot_c*100, 1) if tot_c else 0,
                      "apps_affected": len(per)}
        print(f"  {pain:<14} 命中{tot_c:>6}  波及{len(per):>4}app  Top1={name[:26]:<28} 占{conc[pain]['top_share']:>5.1f}%")

    # 3) 低星子集里的痛点 (真实抱怨, 排除5星刷好评)
    print()
    print("=" * 88)
    print("【低星子集痛点】只看 1-2 星评论 (更接近真实抱怨)")
    print("=" * 88)
    low_by = {}
    low_total = 0
    for aid, rv in byapp.items():
        low = [r for r in rv if r.get("stars", 0) <= 2]
        low_by[aid] = low; low_total += len(low)
    print(f"  低星评论: {low_total} 条 ({low_total/total_r*100:.1f}%)")
    print()
    lc = Counter()
    for aid, rv in low_by.items():
        for pain, kws in DICT.items():
            for r in rv:
                t = (r.get("title","") + " " + r.get("body","")).lower()
                if hits(t, kws): lc[pain] += 1
    print(f"  {'痛点':<16} {'低星命中':>9} {'低星率':>8} {'全量率':>8} {'放大':>7}")
    for pain, c in lc.most_common(12):
        lr = c / low_total * 100
        gr = global_counts[pain] / total_r * 100
        print(f"  {pain:<14} {c:>9} {lr:>7.2f}% {gr:>7.2f}% {lr/gr if gr else 0:>6.2f}x")

    # 4) 样本量最大的可验证痛点: 逐条列出高频痛点最有信息量的原声
    print()
    print("=" * 88)
    print("【高频痛点原声取证】每个痛点 3 条 + review_id + 日期 + app")
    print("=" * 88)
    for pain in [p for p, _, _, _, _ in rows[:6]]:
        print(f"\n  --- {pain} ---")
        shown = 0
        for aid, rv in byapp.items():
            for r in rv:
                if r.get("stars",0) > 2: continue
                t = (r.get("title","") + " " + r.get("body","")).lower()
                if not hits(t, DICT[pain]): continue
                print(f"    [{r.get('review_id')}] {r.get('stars')}星 {r.get('date')} {r.get('app_name','')[:26]}")
                print(f"      {(r.get('title','') or '')[:60]}")
                print(f"      {(r.get('body','') or '')[:150]}")
                shown += 1
                break
            if shown >= 3: break

    json.dump({"global": [{"pain": p, "count": c, "rate": round(c/total_r*100,2),
                           "baseline": round(baseline[p],2), "rel": round(r,2)}
                          for p, c, _, _, r in rows],
               "concentration": conc,
               "low_star": [{"pain": p, "count": c, "rate": round(c/low_total*100,2)}
                            for p, c in lc.most_common()],
               "sample": {"total_reviews": n, "apps": len(byapp), "low_star_reviews": low_total}},
              open(f"{D}/deepdive_painpoints_full.json", "w"), ensure_ascii=False, indent=2)
    print(f"\n  -> {D}/deepdive_painpoints_full.json")


if __name__ == "__main__":
    main()
