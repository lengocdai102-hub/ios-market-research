"""
深挖 G: 找可防守切口 —— 从 19845 条评论反推
核心问题: 前面发现痛点高度分散(Top1 app 只占6-34%), 说明"改进别人的功能"不可防守。
那什么才可防守?
思路: 找那些【高痛点密度 + 低竞争密度】的细分格
  痛点密度 = 该细分主题的抱怨在评论里的密度
  竞争密度 = 该细分主题下有多少 app 在竞争 + 头部多垄断
输出: 机会格矩阵 (主题 × 痛点 × 竞争)
"""
import json, os, re
from collections import Counter, defaultdict

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"

# 细分主题词典 (多关键词 -> 主题)
THEMES = {
    "RV维护记录/保养台账": ["maintenance log", "maintenance record", "service log", "maintenance schedule", "logbook", "service history", "maintenance tracker", "pm schedule", "maintenance checklist"],
    "RV找平/支撑": ["leveling", "level blocks", "leveling block", "level my rv", "stabilizer", "chock"],
    "RV零部件目录": ["part number", "parts catalog", "part catalog", "replacement part", "oem part", "part number lookup", "part identifier"],
    "RV水/电气系统": ["propane", "generator", "water system", "fresh water", "gray water", "black tank", "waste tank", "pump", "lp tank", "furnace", "hot water"],
    "RV尺寸/规格": ["dimensions", "spec sheet", "specs", "specification", "weight", "payload", "tow weight", "gvwr", "dry weight", "clearance", "hitch height"],
    "RV故障/维修手册": ["repair manual", "service manual", "wiring diagram", "diagram", "troubleshooting", "owner manual", "shop manual", "parts diagram"],
    "RV预订/营地": ["reservation", "booking", "book a site", "campground reservation", "availability", "booked"],
    "RV停车/位置记录": ["where to park", "parking", "parking report", "overnight parking", "parking spot", "spotter", "parking location"],
    "营地/停靠点数据库": ["campground database", "dump station", "potable water", "campground directory", "campground list", "campground map"],
    "GPS/离线地图": ["gps", "offline map", "topo", "offline maps", "no signal", "map accuracy", "wrong location", "offline maps"],
    "路线规划/行程": ["route", "trip planner", "itinerary", "route planning", "trip plan", "waypoint", "itinerary"],
    "油耗/成本统计": ["fuel", "mpg", "gas mileage", "fuel cost", "cost tracking", "expense"],
    "多设备/家庭共享": ["family sharing", "multiple devices", "other devices", "second device", "new phone", "my ipad", "my iphone"],
    "导出/备份/迁移": ["export", "backup", "restore", "csv", "pdf export", "icloud sync", "transfer data"],
    "库存/部件追踪": ["inventory", "stock", "parts inventory", "supply"],
    "检查清单/安全": ["checklist", "inspection", "safety check", "pre trip", "pretrip", "walk around"],
    "天气/潮汐/户外预报": ["weather", "tide", "forecast", "rain", "wind", "forecast"],
    "钓鱼/户外活动": ["fishing", "hunt", "game", "spot", "species", "angler"],
    "记账/费用": ["expense", "receipt", "invoice", "budget", "tax", "payment"],
    "学习/教程/文档": ["manual", "documentation", "instructions", "guide", "tutorial", "how to"],
}

# 抱怨型关键词 (表示不满, 而非普通提及)
COMPLAINT = ["frustrat", "annoying", "hate", "terrible", "awful", "useless", "worst", "ridiculous", "disappointing", "waste", "regret", "unusable", "poorly", "missing", "can't", "cannot", "doesn't", "does not", "won't", "fails", "error", "broken", "wrong", "should have", "so frustrating", "unacceptable", "why would", "need to", "should be"]

def load(path):
    byapp = defaultdict(list)
    for line in open(path):
        try:
            r = json.loads(line); byapp[r["app_id"]].append(r)
        except Exception: pass
    return byapp

def main():
    byapp = load(f"{D}/v3_reviews/reviews_all.jsonl")
    pool = []
    p = f"{BASE}/采集器/inputs/competitor_pool.json"
    if os.path.exists(p):
        pool = json.load(open(p))
    # app -> 主题命中
    app_theme = defaultdict(set)
    # 主题 -> 评论级统计
    ts = {t: {"reviews": 0, "complaints": 0, "apps": set(), "lowstar": 0, "ex": []} for t in THEMES}
    total = 0
    for aid, rv in byapp.items():
        for r in rv:
            total += 1
            text = (r.get("title", "") + " " + r.get("body", "")).lower()
            comp = any(c in text for c in COMPLAINT)
            for t, kws in THEMES.items():
                if any(k in text for k in kws):
                    s = ts[t]
                    s["reviews"] += 1
                    s["apps"].add(aid)
                    if comp: s["complaints"] += 1
                    if r.get("stars", 0) <= 2:
                        s["lowstar"] += 1
                        if len(s["ex"]) < 5 and len(r.get("body","")) > 80:
                            s["ex"].append({"id": r["review_id"], "app": r.get("app_name"), "date": r.get("date"),
                                            "stars": r.get("stars"), "title": r.get("title"), "body": r.get("body")[:260]})
                    app_theme[aid].add(t)

    # 竞争密度: 竞品池里有多少 app 名字/描述命中该主题
    theme_comp = Counter()
    for a in pool:
        blob = ((a.get("app_name") or "") + " " + (a.get("desc") or "") + " " + (a.get("genre") or "")).lower()
        for t, kws in THEMES.items():
            if any(k in blob for k in kws):
                theme_comp[t] += 1
    # 头部垄断度: 主题内 Top1 app 占该主题评论数比例
    theme_top = {}
    for t, kws in THEMES.items():
        per = Counter()
        for aid, rv in byapp.items():
            c = 0
            for r in rv:
                text = (r.get("title","") + " " + r.get("body","")).lower()
                if any(k in text for k in kws): c += 1
            if c: per[aid] = c
        tot = sum(per.values())
        top = per.most_common(1)[0] if per else (None, 0)
        nm = ""
        if top[0]:
            nm = byapp[top[0]][0].get("app_name", "")[:28]
        theme_top[t] = {"top_app": nm, "top_share": round(top[1]/tot*100,1) if tot else 0, "total": tot}

    print("=" * 108)
    print(f"【机会格矩阵】基于 {total} 条评论 + {len(pool)} 个竞品")
    print("=" * 108)
    print(f"{'主题':<22} {'命中评论':>8} {'抱怨率':>7} {'低星':>6} {'波及app':>7} {'竞品数':>6} {'Top1垄断':>8} {'机会分':>7}")
    print("-" * 108)
    rows = []
    for t, s in ts.items():
        if not s["reviews"]: continue
        cr = s["complaints"] / s["reviews"] * 100
        lowr = s["lowstar"] / s["reviews"] * 100
        comp = theme_comp.get(t, 0)
        share = theme_top[t]["top_share"]
        # 机会分: 抱怨率高 + 低星率高 + 竞品少 + 垄断低 = 高
        op = (cr/100) * (lowr/100) * (1 - share/100) * (1 / (1 + comp/50)) * 100
        rows.append((t, s["reviews"], cr, lowr, len(s["apps"]), comp, share, op, s))
    rows.sort(key=lambda x: -x[7])
    for t, rev, cr, lowr, na, comp, share, op, s in rows:
        print(f"  {t:<20} {rev:>8} {cr:>6.1f}% {lowr:>5.1f}% {na:>7} {comp:>6} {share:>7.1f}% {op:>7.2f}")

    print()
    print("=" * 108)
    print("【机会分 TOP5 主题的低星原声取证】")
    print("=" * 108)
    for t, rev, cr, lowr, na, comp, share, op, s in rows[:5]:
        print(f"\n  ===== {t}  (机会分 {op:.2f}, 竞品 {comp} 个, 波及 {na} app) =====")
        for e in s["ex"][:4]:
            print(f"    [{e['id']}] {e['stars']}星 {e['date']} {e['app']}")
            print(f"      {e['title']}")
            print(f"      {e['body'][:200]}")

    json.dump({"sample_reviews": total, "pool_size": len(pool),
               "themes": [{"theme": t, "reviews": rev, "complaint_rate": round(cr,1),
                           "lowstar_rate": round(lowr,1), "apps": na, "pool_apps": comp,
                           "top1_share": share, "opportunity_score": round(op,2),
                           "top_app": theme_top[t]["top_app"], "examples": s["ex"][:4]}
                          for t, rev, cr, lowr, na, comp, share, op, s in rows]},
              open(f"{D}/deepdive_opportunity_matrix.json", "w"), ensure_ascii=False, indent=2)
    print(f"\n  -> {D}/deepdive_opportunity_matrix.json")


if __name__ == "__main__":
    main()
