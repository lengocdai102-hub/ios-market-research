"""
数据来源账本 (Source Ledger)
汇总本次调研用到的每一个公开数据源: URL / HTTP状态 / 条数 / 字段 / 口径 / 已知偏差
这是"数据采集切实可行"的核心证据。
"""
import json, os, glob, hashlib, time
from collections import Counter

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"

def count_lines(p):
    try:
        return sum(1 for _ in open(p, encoding="utf-8"))
    except Exception:
        return 0

def jl_stats(p):
    n = 0; apps = set(); stars = Counter(); keys = set(); nonempty = 0
    for line in open(p, encoding="utf-8"):
        try:
            r = json.loads(line); n += 1
            keys |= set(r.keys())
            for k in ("app_id", "appid", "appId"):
                if k in r: apps.add(str(r[k]))
            s = r.get("stars") or r.get("rating") or r.get("star")
            if s is not None:
                try: stars[int(s)] += 1
                except Exception: pass
            b = r.get("body") or r.get("content") or r.get("contents") or r.get("text")
            if b and len(str(b).strip()) > 0: nonempty += 1
        except Exception:
            pass
    return {"rows": n, "apps": len(apps), "fields": len(keys), "nonempty_body": nonempty,
            "stars": dict(sorted(stars.items()))}

print("=" * 104)
print("【数据来源账本】iOS 副业调研 · 全部公开数据源")
print(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 104)

LEDGER = []

def add(cat, name, url, method, status, rows, unit, fields, caliber, bias, path=""):
    LEDGER.append({"category": cat, "name": name, "url": url, "method": method,
                   "http_status": status, "rows": rows, "unit": unit, "fields": fields,
                   "caliber": caliber, "known_bias": bias, "local_path": path})

# 1) App Store 评论 (RSS 分页)
p = f"{D}/v3_reviews/reviews_all.jsonl"
if os.path.exists(p):
    st = jl_stats(p)
    add("App Store 口碑", "Apple customerreviews RSS 分页",
        "https://itunes.apple.com/us/rss/customerreviews/page={1..10}/id={appid}/sortby=mostrecent/json",
        "HTTPS GET + JSON", "200 OK", st["rows"], "条评论", st["fields"],
        "全量文字评论(非抽样)。严格日期倒序。每页50条, page11起返回400为Apple硬上限(500条/app)。",
        "★选择性样本: 写字率中位4.5%, 星级分布比权威ratingCounts偏负向中位5.9倍(区间0.3~63x)。★正文内容有效, 星级不可代表全量口碑。",
        "采集数据/v3_reviews/reviews_all.jsonl")
    print(f"\n[1] App Store 评论 (RSS): {st['rows']} 条 / {st['apps']} app / {st['fields']} 字段")
    print(f"    正文非空率: {st['nonempty_body']/max(st['rows'],1)*100:.1f}%   星级分布: {st['stars']}")

# 2) App Store 竞品元数据
for fn, name, url, cal, bias in [
    ("dataset_competitors.json", "iTunes Lookup API (原始113竞品)", "https://itunes.apple.com/lookup?id={ids}&country=us",
     "Apple 官方元数据: 评分数/均分/版本/上架日/开发者/价格/分类", "userRatingCount 含所有打分(含未写评论), 是下载量的唯一合法代理。"),
    ("_expanded_competitors.json", "iTunes Lookup + Search 扩展池(895)", "https://itunes.apple.com/lookup?id={ids}&country=us",
     "同上, 池子扩至895个app", "搜索关键词决定覆盖面, 可能漏掉长尾。"),
    ("iap_prices_expanded.json", "IAP 内购价格 (809 app / 444 有IAP)", "https://apps.apple.com/us/app/id{id}",
     "商品页内嵌 JSON Annotation.textPair, 提取 IAP 名称+价格", "★只覆盖美区, 且部分app无IAP区块。"),
]:
    p = f"{D}/{fn}"
    if os.path.exists(p):
        d = json.load(open(p))
        n = len(d.get("_apps", d)) if isinstance(d, dict) else len(d)
        add("App Store 行情", name, url, "HTTPS GET + JSON", "200 OK", n, "个 app", "-", cal, bias, f"采集数据/{fn}")
        print(f"    {name}: {n} 个 app")

# 3) 榜单
p = f"{D}/dataset_charts.json"
if os.path.exists(p):
    d = json.load(open(p))
    n = len(d) if isinstance(d, list) else len(d.get("rows", d))
    add("App Store 行情", "iTunes RSS 排行榜(多类型多分类)",
        "https://itunes.apple.com/us/rss/topfreeapplications 等",
        "HTTPS GET + XML", "200 OK", n, "条榜位", "-",
        "每榜约50条, 覆盖免费/付费/畅销榜 × 多分类 × 地区",
        "★快照, 无历史序列。Apple 已于2024年公开弃用RSS榜但端点仍可用。",
        "采集数据/dataset_charts.json")
    print(f"    榜单: {n} 条")

# 4) 社区
for fn, name, url, cal, bias in [
    ("dataset_community.json", "Apple Community 讨论帖", "https://discussions.apple.com/",
     "真实浏览器(绕过Cloudflare), 标题选择器 a.thread-title[href*='/thread/']", "只抓标题+URL+板块, 未抓正文。"),
    ("forum/gnews.jsonl", "Google News RSS 行业舆情", "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en",
     "新闻标题+来源+时间+链接", "★新闻报道非用户UGC, 反映的是媒体关注而非用户原声。"),
    ("forum/hn.jsonl", "Hacker News Algolia API", "https://hn.algolia.com/api/v1/search?query={q}",
     "开发者讨论帖 title/story_text/url/points/created_at", "★偏技术开发者, 非目标用户群。"),
    ("forum/github.jsonl", "GitHub Issues 搜索 API", "https://api.github.com/search/issues?q={q}",
     "真实开发者抱怨 issue title/body/url", "样本量小(15条), in:title 检索过窄。"),
    ("forum/stackexchange.jsonl", "StackExchange API", "https://api.stackexchange.com/2.3/search/advanced",
     "技术问答", "★0条: API 持续429限流, 配额耗尽。"),
]:
    p = f"{D}/{fn}"
    if os.path.exists(p):
        st = jl_stats(p) if fn.endswith(".jsonl") else {"rows": (len(json.load(open(p))) if isinstance(json.load(open(p)), list) else len(json.load(open(p)))), "apps": 0, "fields": 0}
        add("社区/论坛 UGC", name, url, "HTTPS GET", "200 OK" if st["rows"] else "429/空",
            st["rows"], "条", st.get("fields", "-"), cal, bias, f"采集数据/{fn}")
        print(f"    {name}: {st['rows']} 条")

# 5) 失败源 (诚实记录)
for fn, name, url, why in [
    ("", "Reddit (old/new)", "https://www.reddit.com/r/RV/top.json", "硬登录墙, 匿名请求返回登录页; 本机代理出口IP同样被403封禁"),
    ("", "StackExchange", "https://api.stackexchange.com/2.3/", "HTTP 429 持续限流, 退避到15秒仍失败"),
    ("", "App Store 评论翻页(page>1 via 网页)", "https://apps.apple.com/us/app/id{id}?see-all=reviews&page=2", "Apple 不接受额外URL参数, 全部返回404"),
]:
    add("失败源", name, url, "HTTPS GET", "失败", 0, "条", "-", "—", why, "")


# ---- 增量更新: 用最新数据覆盖 rows, 并补充新源 ----
def rowcount(path):
    n=0
    if os.path.exists(path):
        for line in open(path,encoding="utf-8"):
            if line.strip(): n+=1
    return n

master = f"{D}/v3_reviews/reviews_master.jsonl"
CREATORS = f"{D}/v3_reviews/reviews_creators.jsonl"
WINNERS = f"{D}/v3_reviews/reviews_winners.jsonl"

for e in LEDGER:
    nm = e.get("name","")
    if "customerreviews RSS" in nm:
        e["rows"] = rowcount(master)
        e["local_path"] = "采集数据/v3_reviews/reviews_master.jsonl"
        e["known_bias"] = ("★选择性样本: 写字率中位4.5%, 星级分布比权威ratingCounts偏负向中位5.9倍(区间0.3~63x)。"
                           "★正文内容有效, 星级不可代表全量口碑。★全库按review_id全局去重, 跨文件重复已消除。")
    elif "扩展池(895)" in nm:
        e["name"] = "iTunes Lookup 扩展池 (10,312)"
        e["rows"] = 10312
        e["caliber"] = "98个关键词Search API发现候选 + 批量lookup补全元数据"
        e["known_bias"] = ("★搜索关键词决定覆盖面, 长尾仍有遗漏。"
                           "★仅661个含releaseDate, 时间序列样本偏小。")

LEDGER.append({
  "category": "App Store 口碑",
  "name": "评论跨文件全局去重 (reviews_master)",
  "url": "(本地合并)",
  "method": "按 review_id 全局主键合并, 同 id 取字段最全的一条",
  "http_status": "N/A",
  "rows": rowcount(master),
  "unit": "条唯一评论",
  "fields": 14,
  "caliber": "4个采集任务合并后的唯一集合, 消除跨文件重复",
  "known_bias": "★合并后覆盖371个app, 中位每app 43条, 53个app采满500条(Apple上限)",
  "local_path": "采集数据/v3_reviews/reviews_master.jsonl"})
LEDGER.append({
  "category": "App Store 行情",
  "name": "开发者主体分类 (公司/个人/未知)",
  "url": "(本地规则)",
  "method": "seller 名称规则: 法律后缀+机构词+已知大厂名单 -> 公司; 2-4段纯人名 -> 个人; 其余未知",
  "http_status": "N/A",
  "rows": 10312,
  "unit": "个 app",
  "fields": 3,
  "caliber": "公司5,771(56.0%) / 个人824(8.0%) / 未知3,717(36.0%)",
  "known_bias": "★未知组36%主要为品牌单名(Waze/Tripadvisor/Mosaic S.r.l.)无法用规则判定。★保守策略: 宁可判未知, 不把公司误判成个人。",
  "local_path": "采集数据/dev_classification_v2.json"})
LEDGER.append({
  "category": "App Store 口碑",
  "name": "连续创业者 app 评论补采",
  "url": "https://itunes.apple.com/us/rss/customerreviews/page={N}/id={id}/sortby=mostrecent/json",
  "method": "HTTPS GET + JSON",
  "http_status": "200 OK",
  "rows": rowcount(CREATORS),
  "unit": "条评论",
  "fields": 9,
  "caliber": "15位拥有3+app的个人开发者旗下全部app的评论, 用于验证'可复制模式'",
  "known_bias": "★以评论到达时间判定活跃度, 比'版本更新时间'可靠",
  "local_path": "采集数据/v3_reviews/reviews_creators.jsonl"})
LEDGER.append({
  "category": "App Store 口碑",
  "name": "赢家 app 评论补采",
  "url": "https://itunes.apple.com/us/rss/customerreviews/page={N}/id={id}/sortby=mostrecent/json",
  "method": "HTTPS GET + JSON",
  "http_status": "200 OK",
  "rows": rowcount(WINNERS),
  "unit": "条评论",
  "fields": 12,
  "caliber": "13位个人开发者赢家的评论, 每app最多500条, 用于存活性复核",
  "known_bias": "★仅覆盖13个app, 是定向复核样本, 不是随机抽样",
  "local_path": "采集数据/v3_reviews/reviews_winners.jsonl"})

json.dump(LEDGER, open(f"{D}/source_ledger.json", "w"), ensure_ascii=False, indent=2)


print()
print("=" * 104)
print("【账本汇总】")
print("=" * 104)
tot = sum(e["rows"] for e in LEDGER)
bycat = {}
for e in LEDGER:
    bycat[e["category"]] = bycat.get(e["category"], 0) + e["rows"]
print(f"  总记录数: {tot:,}")
for c, n in sorted(bycat.items(), key=lambda x: -x[1]):
    print(f"    {c:<16} {n:>8,}")
ok = sum(1 for e in LEDGER if e["http_status"] == "200 OK")
print(f"\n  可用源: {ok}/{len(LEDGER)}   失败源: {len(LEDGER)-ok}")
print(f"  数据类型覆盖: 竞品元数据 / 用户评论 / 排行榜 / 社区讨论 / 新闻舆情 / 开发者抱怨 / IAP定价 / 论坛UGC")
print(f"\n  -> {D}/source_ledger.json")
