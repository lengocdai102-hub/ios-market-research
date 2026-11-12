"""
基于 46,142 条 master 评论重跑痛点分析 + 痛点集中度
改进:
  1) 用 reviews_master.jsonl (全局去重)
  2) 痛点集中度: 不只数频次, 算"Top1 app 占该痛点比例"和"有效竞争者数量"
  3) 追加: 按 app 分组的痛点 -> 找真正的"抱怨集中点"
  4) 追加: 负向评论(1-2星)里最常见的具体诉求原声
"""
import json, os, re, statistics
from collections import Counter, defaultdict

D = "/Users/maike/Desktop/iOS副业调研_2026-11-09/采集数据"
MASTER = f"{D}/v3_reviews/reviews_master.jsonl"

# 痛点词典(基于第一轮 160 条人工归纳出的类目, 扩充同义词)
PAIN = {
 "订阅/付费墙": ["subscription","subscribe","paywall","pay wall","premium version","pro version",
   "paywall","locked","trial","trial expired","monthly fee","annual fee","too expensive","price is too",
   "expensive for what","paid version","in app purchase","i already paid","refund","charged me"],
 "登录/账号丢失": ["login","log in","sign in","signin","account","lost my","lost all my","password",
   "can't log","cannot log","logged out","sign out","won't let me","sync failed","data loss",
   "lost my data","lost everything","all my data was gone","wiped"],
 "数据丢失/未保存": ["lost my","lost all","data loss","lost data","wiped","deleted my","missing my",
   "not saved","didn't save","disappeared","vanished","reset","all gone","lost everything"],
 "崩溃/闪退": ["crash","crashes","crashed","crashing","force close","force close","freezes","freezing",
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

revs=[]
with open(MASTER,encoding="utf-8") as f:
    for line in f:
        if line.strip():
            r=json.loads(line); revs.append(r)
print(f"样本: {len(revs):,} 条评论 / {len(set(r['app_id'] for r in revs))} 个 app\n")

def hits(text, kws):
    t = text.lower()
    return [k for k in kws if k in t]

# ---- 全局痛点频次 ----
pain_ct = Counter(); pain_apps = defaultdict(set); pain_examples = defaultdict(list)
app_pain = defaultdict(Counter)
for r in revs:
    text = (r.get("title") or "") + " " + (r.get("body") or "")
    for cat, kws in PAIN.items():
        h = hits(text, kws)
        if h:
            pain_ct[cat]+=1
        if h:
            pain_apps[cat].add(r["app_id"])
            app_pain[r["app_id"]][cat]+=1
            if len(pain_examples[cat])<4:
                pain_examples[cat].append({"app":r.get("app_name"),"stars":r.get("stars"),
                    "text":(r.get("body") or "")[:220]})

print(f"=== 全局痛点频次 ({len(revs):,} 条) ===")
print(f"{'痛点':16s} {'命中数':>8} {'占比':>7} {'涉及app':>8} {'集中度':>8}")
conc = {}
for cat, n in pain_ct.most_common():
    napp = len(pain_apps[cat])
    # 集中度 = 该痛点提及数最多的单个app占比
    # 集中度 = 该痛点里, 提及最多的单个 app 占该痛点总提及的比例
    per_app = {a: app_pain[a][cat] for a in pain_apps[cat]}
    top_app = max(per_app.values(), default=0)
    conc_ratio = top_app/n*100
    conc[cat] = {"mentions":n, "pct":round(n/len(revs)*100,2), "apps":napp, "top_app_pct":round(conc_ratio,1)}
    print(f"{cat:16s} {n:>8,} {n/len(revs)*100:>6.2f}% {napp:>8} {conc_ratio:>7.1f}%")

# ---- 负向评论专属痛点 ----
neg = [r for r in revs if (r.get("stars") or 5) <= 2]
print(f"\n=== 负向评论(1-2星) {len(neg):,} 条 ({len(neg)/len(revs)*100:.1f}%) 的痛点 ===")
neg_ct = Counter()
for r in neg:
    text = (r.get("title") or "") + " " + (r.get("body") or "")
    for cat, kws in PAIN.items():
        if hits(text, kws): neg_ct[cat]+=1
for cat,n in neg_ct.most_common(10):
    print(f"  {cat:16s} {n:>6,} ({n/len(neg)*100:.1f}%)")

# ---- 最有集中度的 app (痛点聚焦 = 产品差评集中点) ----
print("\n=== 痛点最集中的 app (负向评论 ≥20 且痛点单一) ===")
focus=[]
for aid, cnt in app_pain.items():
    negs = sum(1 for r in revs if r["app_id"]==aid and (r.get("stars") or 5)<=2)
    if negs < 20: continue
    top, topn = cnt.most_common(1)[0]
    # 单条评论可能同时命中多类痛点, 故 topn/negs 可 >100%。改为: 该app命中此痛点的评论数 / 该app负向评论数
    ratio = topn/negs*100
    # 另算: 纯度 = 该app命中此痛点的评论占其所有命中数
    purity = topn/sum(cnt.values())*100
    if ratio >= 55:
        nm = next((r.get("app_name") for r in revs if r["app_id"]==aid), aid)
        focus.append((nm, negs, top, round(purity,1), negs, topn))
for nm,negs,top,ratio,_nm2,topn in sorted(focus, key=lambda z:-z[1])[:15]:
    print(f"  {str(nm)[:36]:38s} 负向{negs:>4} 条, 主因「{top}」{topn:>4} 条 ({topn/negs*100:>5.1f}% of 负向)")

# ---- 正向评论的关键价值词 ----
pos = [r for r in revs if (r.get("stars") or 0) >= 4]
POS = ["simple","easy","perfect","great","love","best","useful","handy","accurate","fast","offline",
       "works","saves","convenient","slick","clean","minimal","reliable","worth"]
pos_ct=Counter()
for r in pos:
    t=((r.get("title") or "")+" "+(r.get("body") or "")).lower()
    for w in POS:
        if w in t: pos_ct[w]+=1
print(f"\n=== 正向评论(4-5星) {len(pos):,} 条 的价值词 ===")
for w,n in pos_ct.most_common(12):
    print(f"  {w:12s} {n:>7,} ({n/len(pos)*100:.1f}%)")

json.dump({"sample":len(revs),"apps":len(set(r['app_id'] for r in revs)),
  "pain_global":conc, "pain_negative":{k:v for k,v in neg_ct.items()},
  "negative_total":len(neg), "positive_total":len(pos),
  "focused_apps":[{"app":a,"neg":n,"pain":p,"purity":r,"main_mentions":m,
                   "main_pct_of_neg":round(m/n*100,1) if n else 0} for a,n,p,r,_,m in sorted(focus,key=lambda z:-z[1])[:20]],
  "positive_value_words":{k:v for k,v in pos_ct.items()}},
  open(f"{D}/painpoints_master.json","w"),ensure_ascii=False,indent=1)
print("\n已写入 painpoints_master.json")
