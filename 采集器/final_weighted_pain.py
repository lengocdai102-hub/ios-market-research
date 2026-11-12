#!/usr/bin/env python3
"""
最终汇总分析器 —— 对 v3_reviews/reviews_master.jsonl (50,326 条唯一评论 / 440 app) 做
逆概率加权(IPW) 痛点分析, 用 App Store 商品页内嵌 JSON 的权威 ratingCounts 作全量口径。

设计:
  weight_factor(app) = all_low_pct / sample_low_pct
    all_low_pct  = (ratingCounts[3] + ratingCounts[4]) / totalNumberOfRatings   # 权威全量
    sample_low_pct= (样本1星 + 样本2星) / 样本条数                              # RSS 文字评论样本
  若样本无 1-2 星评论 => 系数不可算 => 记为 unweighted, 不参与加权(但保留在 raw 统计)

输出: 采集数据/final_weighted_pain.json
"""
import json, os, re, glob, statistics
from collections import Counter, defaultdict

D = "/Users/maike/Desktop/iOS副业调研_2026-11-09/采集数据"
MASTER = f"{D}/v3_reviews/reviews_master.jsonl"
IAP_HTML = f"{D}/_iap_html"

# ---------- 1. 载入权威评分分布 (ratingCounts) ----------
auth = {}   # app_id -> {counts:[5..1], total, avg}
for p in glob.glob(f"{IAP_HTML}/*.html"):
    aid = os.path.basename(p)[:-5]
    try:
        h = open(p, encoding="utf8", errors="ignore").read()
    except Exception:
        continue
    m = re.search(r'"ratingCounts"\s*:\s*(\[[^\]]*\])', h)
    t = re.search(r'"totalNumberOfRatings"\s*:\s*(\d+)', h)
    if not (m and t):
        continue
    try:
        counts = [int(x) for x in m.group(1).strip("[]").split(",") if x.strip() != ""]
    except Exception:
        continue
    total = int(t.group(1))
    if len(counts) != 5 or total <= 0:
        continue
    auth[aid] = {"counts": counts, "total": total}
print(f"[1a] _iap_html 权威 ratingCounts 可用 app: {len(auth)}")

# ---------- 1b. 补充来源: rating_counts.jsonl (采集器新抓的权威评分分布) ----------
# 该文件 ratingCounts 为 dict {"1":n1,...,"5":n5}, 需转成 counts[5..1] 顺序
_rc = f"{D}/rating_counts.jsonl"
added = 0
if os.path.exists(_rc):
    for line in open(_rc, encoding="utf8", errors="ignore"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("fetch_status") != "ok" or not r.get("ratingCounts"):
            continue
        rc = r["ratingCounts"]
        total = r.get("total") or r.get("ratingCounts_sum") or 0
        try:
            counts = [int(rc["5"]), int(rc["4"]), int(rc["3"]), int(rc["2"]), int(rc["1"])]
        except Exception:
            continue
        if total <= 0 or len(counts) != 5:
            continue
        aid = str(r.get("app_id"))
        if aid not in auth:
            auth[aid] = {"counts": counts, "total": total}
            added += 1
print(f"[1b] rating_counts.jsonl 补充 app: {added}  => 合计 {len(auth)}")

# ---------- 2. 载入 master 评论 ----------
revs = []
with open(MASTER, encoding="utf8") as f:
    for line in f:
        line = line.strip()
        if line:
            try:
                revs.append(json.loads(line))
            except Exception:
                pass
app_of = {}
for r in revs:
    app_of.setdefault(r["app_id"], r.get("app_name"))
print(f"[2] master 评论 {len(revs):,} 条 / {len(app_of)} app")

# ---------- 3. 每 app 样本星级分布 ----------
per_app_star = defaultdict(Counter)
for r in revs:
    s = r.get("stars")
    if s is not None:
        per_app_star[str(r["app_id"])][int(s)] += 1

# ---------- 4. 计算权重 ----------
weights = {}
unweighted = []
bias_rows = []
for aid, cnt in per_app_star.items():
    n = sum(cnt.values())
    if aid not in auth:
        unweighted.append({"app_id": aid, "app_name": app_of.get(aid), "reason": "无权威 ratingCounts",
                           "sample_n": n})
        continue
    a = auth[aid]
    # ratingCounts 在网页 JSON 中顺序为 [1星,2星,3星,4星,5星]? 实测 sample: [1,0,0,0,1] total=2 => 1星1 5星1
    # 而 deepdive_sample_representativeness 用的是 counts_5_to_1 => [5,4,3,2,1]
    # 这里用 counts_5_to_1 语义: 低星 = index3 + index4
    low_all = a["counts"][3] + a["counts"][4]
    all_low_pct = low_all / a["total"] * 100
    low_s = cnt.get(1, 0) + cnt.get(2, 0)
    s_low_pct = low_s / n * 100
    if s_low_pct <= 0:
        unweighted.append({"app_id": aid, "app_name": app_of.get(aid), "reason": "样本无1-2星",
                           "sample_n": n, "all_low_pct": round(all_low_pct, 2)})
        continue
    w = all_low_pct / s_low_pct
    weights[aid] = w
    bias_rows.append({"app_id": aid, "app_name": app_of.get(aid), "total_ratings": a["total"],
                      "sample_n": n, "sample_low_pct": round(s_low_pct, 2),
                      "all_low_pct": round(all_low_pct, 2), "weight_factor": round(w, 4),
                      "bias_ratio": round(s_low_pct / all_low_pct, 2) if all_low_pct > 0 else None})

biased_apps = [b for b in bias_rows if b["bias_ratio"] and b["bias_ratio"] > 1]
print(f"[3] 可算权重 app: {len(weights)} | 样本低星率 > 全量 的 app: {len(biased_apps)}/{len(bias_rows)} "
      f"({100*len(biased_apps)/max(len(bias_rows),1):.1f}%)")
if bias_rows:
    rr = sorted(b["bias_ratio"] for b in bias_rows if b["bias_ratio"])
    print(f"    偏负倍数 中位 {statistics.median(rr):.1f}x  min {min(rr):.2f}x  max {max(rr):.1f}x")
    print(f"    加权系数 中位 {statistics.median(list(weights.values())):.4f}  "
          f"min {min(weights.values()):.4f}  max {max(weights.values()):.4f}")

# ---------- 5. 痛点词典 (与 painpoints_master.py 同源, 保证可比) ----------
PAIN = {
 "订阅/付费墙": ["subscription","subscribe","paywall","pay wall","premium version","pro version",
   "locked","trial","trial expired","monthly fee","annual fee","too expensive","price is too",
   "expensive for what","paid version","in app purchase","i already paid","refund","charged me"],
 "登录/账号丢失": ["login","log in","sign in","signin","account","lost my","lost all my","password",
   "can't log","cannot log","logged out","sign out","won't let me","sync failed","data loss",
   "lost my data","lost everything","all my data was gone","wiped"],
 "数据丢失/未保存": ["lost my","lost all","data loss","lost data","wiped","deleted my","missing my",
   "not saved","didn't save","disappeared","vanished","reset","all gone","lost everything"],
 "崩溃/闪退": ["crash","crashes","crashed","crashing","force close","freezes","freezing",
   "hung","not responding","won't open","wont open","closes immediately","black screen","bug","glitch"],
 "导出/分享失败": ["export","export to","share to","pdf","csv","print","printing","can't share",
   "could not export","failed to export","not export"],
 "云同步不可靠": ["sync","syncing","synced","cloud","icloud","google drive","backup","not backed up"],
 "离线不可用": ["offline","no internet","without internet","no signal","no wifi","airplane mode",
   "needs internet","requires connection","no connection"],
 "UI/易用性差": ["confusing","confused","hard to use","difficult to use","cluttered","not intuitive",
   "user interface","ui is","too many taps","hidden","hard to find","navigate","navigation is",
   "small text","tiny","buttons","awkward","annoying","frustrating","frustrated","useless",
   "unusable","terrible","horrible","worst","stupid","ridiculous","waste of","waste of money",
   "disappointed","disappointing","scam","poorly","bad design","poor design","old school"],
 "功能缺失/不够用": ["wish","would like","need a","needs a","missing","should have","feature request",
   "add support","add option","feature","limited","only supports","doesn't support","no way to",
   "can't do","cannot","not possible","lacking"],
 "不准确/数据错": ["wrong","inaccurate","incorrect","not accurate","wrong data","wrong location",
   "wrong price","wrong time","doesn't match","outdated","stale","missing locations","wrong address"],
 "耗电/发热": ["battery","drain","draining","heat","heating","hot","overheat","battery drain","consumes"],
 "广告过多": ["ads","advertisement","adverts","banner ads","too many ads","annoying ads","ad free",
   "ads everywhere","advert"],
 "缺少平板支持": ["ipad","tablet","iphone only","no ipad","ipad version","landscape"],
 "通知/提醒问题": ["notification","notifications","alert","alerts","reminder","reminders","no notification",
   "didn't notify","not notified","notification sound","too many notifications"],
 "搜索/筛选不好用": ["search","searching","filter","filters","can't find","hard to find","no search",
   "search function","sort"],
 "地图/GPS精度": ["gps","accuracy","inaccurate","wrong location","signal","satellite","position",
   "off by","drift","doesn't work outdoors"],
 "权限/电池优化": ["permission","permissions","battery optimization","background","background refresh",
   "notification permission","location permission","always allow","denied"],
}

def hits(text, kws):
    t = text.lower()
    return [k for k in kws if k in t]

# ---------- 6. raw vs weighted ----------
raw_ct = Counter(); w_ct = Counter()
raw_neg_ct = Counter(); w_neg_ct = Counter()
raw_pos_ct = Counter(); w_pos_ct = Counter()
app_pain = defaultdict(Counter)
raw_wsum = 0.0; w_sum = 0.0
neg_raw = 0; neg_w = 0.0
pos_raw = 0; pos_w = 0.0
for r in revs:
    aid = str(r["app_id"]); w = weights.get(aid)
    text = (r.get("title") or "") + " " + (r.get("body") or "")
    st = int(r.get("stars") or 0)
    for cat, kws in PAIN.items():
        if hits(text, kws):
            raw_ct[cat] += 1
            app_pain[aid][cat] += 1
            if w is not None:
                w_ct[cat] += w
            if st <= 2:
                raw_neg_ct[cat] += 1
                if w is not None:
                    w_neg_ct[cat] += w
            if st >= 4:
                raw_pos_ct[cat] += 1
                if w is not None:
                    w_pos_ct[cat] += w
    if st <= 2:
        neg_raw += 1
    if st >= 4:
        pos_raw += 1
    if w is not None:
        w_sum += w
        if st <= 2:
            neg_w += w
        if st >= 4:
            pos_w += w

n = len(revs)
print(f"[4] 加权覆盖评论 {int(w_sum):,} 条 / {n:,} ({100*w_sum/n:.1f}%)")

# 负向评论口径 (1-2星) 的痛点排名
rows = []
for cat in PAIN:
    rp = raw_neg_ct[cat] / max(neg_raw, 1) * 100
    wp = w_neg_ct[cat] / max(neg_w, 1e-9) * 100
    rows.append({"pain": cat, "raw_n": raw_neg_ct[cat], "raw_pct": round(rp, 2),
                 "weighted_n": round(w_neg_ct[cat], 1), "weighted_pct": round(wp, 2),
                 "change_pct": round((wp / rp - 1) * 100, 1) if rp > 0 else None,
                 "raw_rank": 0, "weighted_rank": 0})
rows.sort(key=lambda x: -x["raw_pct"])
for i, x in enumerate(rows): x["raw_rank"] = i + 1
rows.sort(key=lambda x: -x["weighted_pct"])
for i, x in enumerate(rows): x["weighted_rank"] = i + 1

print("\n=== 负向评论(1-2星)痛点: 原始 vs 逆概率加权 (排名变化) ===")
print(f"{'痛点':18s}{'raw%':>8}{'#':>4}{'wt%':>8}{'#':>4}{'变化%':>9}")
for x in sorted(rows, key=lambda z: z["raw_rank"]):
    mark = " <<< 排序变化" if x["raw_rank"] != x["weighted_rank"] else ""
    print(f"{x['pain']:18s}{x['raw_pct']:>8.2f}{x['raw_rank']:>4}{x['weighted_pct']:>8.2f}"
          f"{x['weighted_rank']:>4}{x['change_pct']:>9.1f}{mark}")

# 全量口径的痛点频次对比
grows = []
for cat in PAIN:
    rp = raw_ct[cat] / n * 100
    wp = w_ct[cat] / w_sum * 100
    grows.append({"pain": cat, "raw_n": raw_ct[cat], "raw_pct": round(rp, 2),
                  "weighted_n": round(w_ct[cat], 1), "weighted_pct": round(wp, 2),
                  "change_pct": round((wp / rp - 1) * 100, 1) if rp > 0 else None})
grows.sort(key=lambda x: -x["raw_pct"])
print("\n=== 全量痛点频次: 原始 vs 加权 ===")
for x in grows:
    print(f"  {x['pain']:18s} raw {x['raw_n']:>6,} ({x['raw_pct']:>5.2f}%)  ->  "
          f"wt {x['weighted_n']:>8.1f} ({x['weighted_pct']:>5.2f}%)  {x['change_pct']:>+7.1f}%")

# 集中度 (加权后)
conc = {}
for cat in PAIN:
    per = {a: c[cat] for a, c in app_pain.items() if c.get(cat)}
    if not per: continue
    top_a = max(per, key=lambda a: per[a])
    wv = weights.get(top_a, 1.0)
    top_w = per[top_a] * wv
    tot_w = w_ct[cat]
    conc[cat] = {"raw_top_app": app_of.get(top_a), "raw_top_n": per[top_a],
                 "raw_top_pct": round(per[top_a] / max(raw_ct[cat], 1) * 100, 2),
                 "wt_top_app": app_of.get(top_a), "wt_top_pct": round(top_w / max(tot_w, 1e-9) * 100, 2),
                 "apps_hit": len(per)}

out = {
    "generated_at": "2026-11-11",
    "method": {
        "sample": "v3_reviews/reviews_master.jsonl",
        "authoritative_rating_dist": "_iap_html/*.html 内嵌 JSON 的 ratingCounts + totalNumberOfRatings",
        "weight_factor": "all_low_pct / sample_low_pct ; all=权威 ratingCounts 低星占比, sample=RSS文字评论1-2星占比",
        "unweighted_apps": "无权威 ratingCounts 或样本无1-2星 => 不参与加权, 保留在 raw",
    },
    "totals": {"reviews": n, "apps": len(app_of),
               "apps_weighted": len(weights), "apps_unweighted": len(unweighted),
               "weighted_reviews_equiv": round(w_sum, 1),
               "coverage_pct": round(100 * w_sum / n, 1),
               "low_star_reviews_raw": neg_raw, "low_star_weighted_equiv": round(neg_w, 1),
               "positive_reviews_raw": pos_raw, "positive_weighted_equiv": round(pos_w, 1)},
    "sample_bias": {
        "apps_measurable": len(bias_rows),
        "apps_sample_more_negative_than_truth": len(biased_apps),
        "pct_more_negative": round(100 * len(biased_apps) / max(len(bias_rows), 1), 1),
        "bias_ratio_median": round(statistics.median([b["bias_ratio"] for b in bias_rows if b["bias_ratio"]]), 2),
        "bias_ratio_min": round(min(b["bias_ratio"] for b in bias_rows if b["bias_ratio"]), 2),
        "bias_ratio_max": round(max(b["bias_ratio"] for b in bias_rows if b["bias_ratio"]), 1),
        "weight_factor_median": round(statistics.median(list(weights.values())), 4),
        "worst_cases": sorted([b for b in bias_rows if b["bias_ratio"]],
                              key=lambda x: -x["bias_ratio"])[:12],
    },
    "pain_negative_raw_vs_weighted": rows,
    "pain_global_raw_vs_weighted": grows,
    "pain_concentration_weighted": conc,
    "unweighted_apps": unweighted[:60],
}
json.dump(out, open(f"{D}/final_weighted_pain.json", "w"), ensure_ascii=False, indent=1)
print(f"\n-> {D}/final_weighted_pain.json")
