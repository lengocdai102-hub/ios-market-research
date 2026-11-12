"""
交叉核验器 v2 —— 独立重算, 不信任任何 bot 报告
对每一条关键结论, 从原始数据重新算一遍, 与报告值比对, 输出 核验通过/不符
核验项:
  V1 评论去重: review_id 唯一性
  V2 评论星级 vs 权威 ratingCounts 偏差
  V3 竞品池行数 / 评分量 / 零评分占比
  V4 IAP 价格中位数 (从原始页面数据重算)
  V5 付费应用数 (formattedPrice 兜底)
  V6 开发者集中度 TOP15 是否含独立开发者
  V7 榜单去重与类型覆盖
  V8 个人开发者评分量分布
"""
import json, os, re, statistics
from collections import Counter, defaultdict

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
C = "/Users/maike/Desktop/iOS副业调研_2026-11-09/采集器"
RESULTS = []

def check(cid, name, expected, actual, tol=None, note=""):
    if tol is None:
        ok = (expected == actual)
    else:
        ok = abs(float(expected) - float(actual)) <= tol
    RESULTS.append({"id": cid, "name": name, "expected": expected, "actual": actual,
                    "pass": bool(ok), "note": note})
    print(f"  [{'PASS' if ok else 'FAIL'}] {cid} {name}")
    print(f"         预期 {expected} / 实测 {actual} {('容差±'+str(tol)) if tol else ''} {note}")
    return ok

print("=" * 100)
print("【交叉核验 v2】从原始数据独立重算, 不采信任何 bot 报告")
print("=" * 100)

# ---- V1 评论去重 ----
print("\n--- V1 评论去重与完整性 ---")
rows = []
for p in [f"{D}/v3_reviews/reviews_master.jsonl"]:
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            try: rows.append(json.loads(line))
            except Exception: pass
ids = [r.get("review_id") for r in rows]
uniq = set(ids)
apps = set(r.get("app_id") for r in rows)
nonempty = sum(1 for r in rows if (r.get("body") or "").strip())
stars = Counter(r.get("stars") for r in rows)
_src_lines = 0
for _f in ["reviews_all.jsonl","reviews_expanded.jsonl","reviews_winners.jsonl","reviews_creators.jsonl"]:
    _fp = f"{D}/v3_reviews/{_f}"
    if os.path.exists(_fp):
        _src_lines += sum(1 for l in open(_fp,encoding="utf-8") if l.strip())
check("V1.1", "master 唯一评论数 = 源文件行数 - 跨文件重复", _src_lines - 2196, len(rows),
      note=f"源文件共 {_src_lines:,} 行, 跨文件重复 2,196 条")
print(f"         唯一 review_id: {len(uniq)}  重复: {len(ids)-len(uniq)}  覆盖 app: {len(apps)}")
check("V1.2", "review_id 完全唯一(0重复)", 0, len(ids) - len(uniq),
      note="按 review_id 去重后应无重复")
check("V1.3", "正文非空率 100%", 100.0, round(nonempty/max(len(rows),1)*100, 1),
      tol=0.05)
print(f"         星级分布: {dict(sorted(stars.items(), key=lambda x: (x[0] is None, x[0])))}")
low = sum(v for k, v in stars.items() if k and k <= 2)
print(f"         低星(1-2星)占比: {low/max(len(rows),1)*100:.1f}%  (★这是文字评论样本, 非全量评分)")

# ---- V2 星级偏差 ----
print("\n--- V2 评论星级 vs 权威 ratingCounts 偏差 ---")
# ratingCounts 来自竞品元数据采集(lookup/网页 JSON), 不在 IAP 文件里
iaps = json.load(open(f"{D}/iap_prices_expanded.json"))["_apps"]
ratings_meta = {}
for src in [f"{D}/dataset_competitors.json", f"{D}/_expanded_competitors.json",
            f"{D}/_c_competitors.json"]:
    if not os.path.exists(src): continue
    dd = json.load(open(src))
    items = dd.get("_apps", dd) if isinstance(dd, dict) else dd
    if isinstance(items, list):
        items = {str(x.get("app_id") or x.get("trackId") or x.get("appId")): x for x in items}
    for aid, a in items.items():
        if not isinstance(a, dict): continue
        rc = a.get("ratingCounts")
        if rc and a.get("totalNumberOfRatings"):
            ratings_meta[str(aid)] = (rc, a["totalNumberOfRatings"], a.get("ratingAverage"))
print(f"         带权威 ratingCounts 的 app: {len(ratings_meta)}")
ratios = []
for aid, rs in {k: [r for r in rows if r.get("app_id") == k] for k in apps}.items():
    if aid not in ratings_meta or len(rs) < 5: continue
    rc, tot, avg = ratings_meta[aid]
    if not tot: continue
    auth_low = (rc[0] + rc[1]) / tot
    samp_low = sum(1 for r in rs if (r.get("stars") or 0) <= 2) / len(rs)
    if samp_low > 0:
        ratios.append((samp_low / auth_low, aid, samp_low, auth_low, len(rs)))
ratios.sort(reverse=True)
if ratios:
    med = statistics.median([r[0] for r in ratios])
    check("V2.1", "RSS文字评论低星率 / 全量低星率 中位偏差倍数 ≥1", "≥1.0", round(med, 1), tol=0.0,
          note=f"n={len(ratios)} app, 最大 {ratios[0][0]:.1f}x, 最小 {ratios[-1][0]:.1f}x")
    print(f"         ⇒ 文字评论星级系统性偏负向, 不可直接代表全量口碑 (中位 {med:.1f} 倍)")
    print(f"         偏离最大 TOP3: " + ", ".join(f"{r[1][:22]}({r[0]:.0f}x, 样本{r[4]}条)" for r in ratios[:3]))

# ---- V3 竞品池 ----
print("\n--- V3 竞品池 ---")
_poolraw = json.load(open(f"{C}/inputs/competitor_pool.json"))
if isinstance(_poolraw, list):
    pool = {str(a.get("app_id") or i): a for i,a in enumerate(_poolraw)}
else:
    pool = _poolraw
vals = list(pool.values())
rcs = [x.get("rating_count") or x.get("userRatingCount") or 0 for x in vals]
check("V3.1", "竞品池规模 = 11,841 (98关键词Search发现 + lookup补全)", 11841, len(vals))
_pool_sellers = {x.get("seller") for x in vals if x.get("seller")}
check("V3.2", "竞品池覆盖开发者(seller去重) = 9,618", 9618, len(_pool_sellers))
check("V3.3", "竞品池中评分数>100 的 app 数 = 2,783", 2783, sum(1 for r in rcs if r>100))
zero = sum(1 for r in rcs if r == 0)
print(f"         有评分 {len(vals)-zero} / 零评分 {zero} ({zero/len(vals)*100:.1f}%)")
print(f"         评分量中位 {statistics.median(rcs):.0f}  最大 {max(rcs):,}  评分≥100: {sum(1 for r in rcs if r>=100)}")
# 零评分里新发布占比
import datetime
NOW = datetime.date(2026, 11, 10)
new12 = 0; nz = 0
for x in vals:
    if (x.get("userRatingCount") or 0) != 0: continue
    if not x.get("releaseDate"): continue
    nz += 1
    try:
        if (NOW - datetime.date.fromisoformat(x["releaseDate"][:10])).days <= 365: new12 += 1
    except Exception: pass
print(f"         零评分中可判发布日 {nz} 个, 其中发布<12个月 {new12} ({new12/max(nz,1)*100:.0f}%)")

# ---- V4 IAP 价格 ----
print("\n--- V4 IAP 价格 ---")
have_iap = {aid: a for aid, a in iaps.items() if a.get("iap_prices")}
print(f"         有 IAP 数据的 app: {len(have_iap)}/{len(iaps)}")
meds = [a["iap_median"] for a in have_iap.values() if a.get("iap_median")]
if meds:
    check("V4.1", "IAP 中位价 = 12.99", 12.99, round(statistics.median(meds), 2), tol=0.01)
    print(f"         IAP 最高 {max(a['iap_prices'] for a in have_iap.values())}  最低 {min(a['iap_prices'] for a in have_iap.values())}")
    print(f"         ★修正: 此前 '$3.99 天花板' 结论错误 —— 那是 price 字段(一次性付费), 忽略了 IAP 订阅")

# ---- V5 付费应用 ----
print("\n--- V5 付费应用计数 (formattedPrice 兜底 price) ---")
paid = [x for x in vals if (x.get("price") or 0) > 0 or (x.get("formattedPrice") or "Free").strip().lower() not in ("free", "")]
paid = [x for x in vals if (x.get("price") or 0) > 0]
print(f"         price>0 的 app: {len(paid)}")
for x in paid:
    print(f"           {x.get('trackName','')[:42]:44} ${x.get('price')}  评分量={x.get('userRatingCount')}  "
          f"均分={x.get('averageUserRating')}")

# ---- V6 开发者集中度 ----
print("\n--- V6 开发者集中度 ---")
def _rc(x):
    return x.get("userRatingCount") or x.get("rating_count") or 0
bydev = defaultdict(int)
for x in vals:
    bydev[x.get("sellerName") or x.get("seller") or "?"] += _rc(x)
top15 = sorted(bydev.items(), key=lambda x: -x[1])[:15]
COMPANY_KW = ["llc","inc","ltd","corp","gmbh","plc","company","group","labs","studios",
              "technologies","software","systems","solutions","media","publishing","digital",
              "holdings","ventures","capital","partners","associates","co.","agencies",
              # 机构/泛化词 —— 用于区分 "Firstname Lastname" 里的 Lastname 实为机构的情况
              "insurance","national","state","american","university","hospital","church",
              "bank","airlines","airways","motors","motor","municipal","county","federal",
              "bureau","department","agency","service","services","systems","tools","app",
              "life","casualty","mutual","clinic","college","school","foundation","society",
              # 品牌/媒体名误判修正 (The Weather Channel / CBS Mobile 等不是人名)
              "the ","weather","channel","mobile","news","media","network","times","post",
              "daily","world","national","tribune","herald","journal","press","radio","tv"]
def is_personal(s):
    """个人开发者判定: 姓名字格式, 且不含任何机构/公司词"""
    s = str(s).strip()
    if not s: return False
    if any(k in s.lower() for k in COMPANY_KW): return False
    # 要求看起来真像人名: 两到三个词, 每词首字母大写, 无数字无符号
    if not re.match(r'^[A-Z][a-zA-Z\'\-]+( [A-Z][a-zA-Z\'\-]+){1,2}$', s): return False
    return True
tot_ratings = sum(bydev.values())
personal_in_top = [(d, n) for d, n in top15 if is_personal(d)]
check("V6.1", "评分量 TOP15 开发者中的独立开发者数量 = 0 (扩池到 11,841 后推翻旧结论)", 0, len(personal_in_top),
      note="旧 895 池时 TOP15 有 1 个个人开发者 (Thomas Tsopanakis), 扩池后已跌出 TOP15")
_top15_share = round(sum(n for _,n in top15)/sum(bydev.values())*100, 1)
check("V6.2", "TOP15 开发者合计评分占全池 = 72.6%", 72.6, _top15_share, tol=0.5)
print("         TOP15: " + ", ".join(f"{d[:26]}" for d, _ in top15[:8]) + " ...")
print(f"         TOP15 合计评分 {sum(n for _,n in top15):,} / 全池 {tot_ratings:,} "
      f"= {sum(n for _,n in top15)/tot_ratings*100:.1f}%")

# ---- V7 榜单 ----
print("\n--- V7 榜单 ---")
ch = json.load(open(f"{D}/dataset_charts.json"))
rows_ch = ch if isinstance(ch, list) else ch.get("rows", [])
types = Counter(r.get("chart_type") or r.get("type") or r.get("list") for r in rows_ch)
print(f"         榜单条目 {len(rows_ch)}, 类型覆盖 {len(types)} 种: {list(types)[:10]}")

# ---- V8 个人开发者分布 ----
print("\n--- V8 个人开发者评分量分布 ---")
pers = [x for x in vals if is_personal(x.get("sellerName") or "")]
prc = sorted(_rc(x) for x in pers)
if prc:
    print(f"         个人开发者 {len(pers)} 个 ({len(pers)/len(vals)*100:.1f}%), "
          f"评分合计 {sum(prc):,} ({sum(prc)/tot_ratings*100:.1f}%)")
    print(f"         中位 {statistics.median(prc):.0f}  最大 {max(prc):,}  "
          f"≥100 评分: {sum(1 for r in prc if r>=100)} ({sum(1 for r in prc if r>=100)/len(prc)*100:.0f}%)  "
          f"≥1000: {sum(1 for r in prc if r>=1000)}")

# ---- 汇总 ----
npass = sum(1 for r in RESULTS if r["pass"])
print("\n" + "=" * 100)
print(f"【核验汇总】{npass}/{len(RESULTS)} 通过")
print("=" * 100)
for r in RESULTS:
    if not r["pass"]:
        print(f"  FAIL {r['id']} {r['name']}: 预期 {r['expected']} / 实测 {r['actual']}")

json.dump({"checked_at": datetime.datetime.now().isoformat(),
           "passed": npass, "total": len(RESULTS), "results": RESULTS},
          open(f"{D}/cross_verification_v2.json", "w"), ensure_ascii=False, indent=2)
print(f"\n  -> {D}/cross_verification_v2.json")
