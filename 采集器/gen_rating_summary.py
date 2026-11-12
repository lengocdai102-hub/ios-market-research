#!/usr/bin/env python3
"""生成 rating_counts_summary.md: 覆盖率、校验通过率、评分分布反算表"""
import json, os, statistics, collections

BASE = "/Users/maike/Desktop/iOS副业调研_2026-11-09"
D = f"{BASE}/采集数据"
RC = f"{D}/rating_counts.jsonl"
TG = f"{D}/rating_targets.json"
OUT = f"{D}/rating_counts_summary.md"

rows = []
for line in open(RC, encoding="utf-8"):
    line = line.strip()
    if line:
        rows.append(json.loads(line))
targets = json.load(open(TG))
tmap = {str(t["app_id"]): t for t in targets}

ok = [r for r in rows if r.get("fetch_status") == "ok"]
fail = [r for r in rows if r.get("fetch_status") != "ok"]
sum_ok = [r for r in ok if r.get("sum_matches_total")]
avg_ok = [r for r in ok if r.get("avg_consistent")]
avg_ok_strict = [r for r in ok if r.get("avg_consistent_strict")]

# 按星级汇总
agg = collections.Counter()
for r in ok:
    for k, v in (r.get("ratingCounts") or {}).items():
        agg[k] += v
tot_all = sum(agg.values())

# 覆盖的 app 总评分数分布
totals = sorted((r.get("total") or 0) for r in ok)

L = []
L.append("# App Store 权威评分分布 (ratingCounts) 采集汇总\n")
L.append(f"- 生成时间: {__import__('datetime').datetime.now().isoformat(timespec='seconds')}")
L.append(f"- 数据文件: `采集数据/rating_counts.jsonl`")
L.append(f"- 目标清单: `采集数据/rating_targets.json` ({len(targets)} 个 app)")
L.append(f"- 采集脚本: `采集器/scr_rating_counts.py`\n")

L.append("## 一、覆盖率\n")
L.append("| 指标 | 数值 |")
L.append("|---|---|")
L.append(f"| 目标 app 总数 | {len(targets)} |")
L.append(f"| 已产出记录 | {len(rows)} |")
L.append(f"| 成功 (fetch_status=ok) | {len(ok)} ({len(ok)/max(len(targets),1)*100:.1f}% of 目标) |")
L.append(f"| 失败 | {len(fail)} ({len(fail)/max(len(targets),1)*100:.1f}%) |")
L.append(f"| 采集来源 | master TOP300 (440 app 中出现最多) + _expanded_competitors.json 895 池，合并去重 |")
L.append("")

# 失败原因分布
if fail:
    L.append("### 失败原因分布\n")
    rc = collections.Counter()
    for r in fail:
        st = r.get("http_status")
        rc[f"http_{st}" if st else str(r.get("error", "unknown"))[:40]] += 1
    L.append("| 原因 | 条数 |")
    L.append("|---|---|")
    for k, v in rc.most_common():
        L.append(f"| {k} | {v} |")
    L.append("")

L.append("## 二、数据校验\n")
L.append("| 校验项 | 口径 | 通过 | 通过率 |")
L.append("|---|---|---|---|")
L.append(f"| ratingCounts 之和 == totalNumberOfRatings | 精确相等 | {len(sum_ok)}/{len(ok)} | "
         f"{len(sum_ok)/max(len(ok),1)*100:.1f}% |")
L.append(f"| 反算加权平均分 == ratingAverage | 舍入 1 位小数后差 <0.05 | {len(avg_ok)}/{len(ok)} | "
         f"{len(avg_ok)/max(len(ok),1)*100:.1f}% |")
L.append(f"| 同上（严格口径） | 原始差 <0.02 | {len(avg_ok_strict)}/{len(ok)} | "
         f"{len(avg_ok_strict)/max(len(ok),1)*100:.1f}% |")
L.append("")
L.append("> 说明：Apple 商品页的 `ratingAverage` 只保留 1 位小数，因此严格 <0.02 的口径会"
         "对大量自洽数据判为不一致（例：反算 4.7496 vs 页面 4.7）。主口径按舍入后比较。\n")

L.append("## 三、评分分布反算（全样本汇总）\n")
L.append(f"成功 app {len(ok)} 个，覆盖总评分数 {tot_all:,} 条。\n")
L.append("| 星级 | 评分数 | 占比 |")
L.append("|---|---|---|")
for k in ("5", "4", "3", "2", "1"):
    v = agg[k]
    L.append(f"| {k} 星 | {v:,} | {v/max(tot_all,1)*100:.2f}% |")
L.append(f"| **合计** | **{tot_all:,}** | 100% |")
wavg = sum(int(k) * v for k, v in agg.items()) / max(tot_all, 1)
L.append(f"\n全样本加权平均分: **{wavg:.4f}**\n")
L.append(f"全样本低星率 (1-2 星): **{(agg['1']+agg['2'])/max(tot_all,1)*100:.2f}%**\n")

L.append("## 四、单 app 总评分数分布\n")
if totals:
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append(f"| 中位 | {int(statistics.median(totals)):,} |")
    L.append(f"| 均值 | {sum(totals)/len(totals):,.0f} |")
    L.append(f"| 最大 | {max(totals):,} |")
    L.append(f"| 最小 | {min(totals):,} |")
    L.append(f"| 零评分 app | {sum(1 for t in totals if t == 0)} |")
    L.append(f"| 评分 ≥100 的 app | {sum(1 for t in totals if t >= 100)} "
             f"({sum(1 for t in totals if t >= 100)/len(totals)*100:.1f}%) |")
    L.append(f"| 评分 ≥1000 的 app | {sum(1 for t in totals if t >= 1000)} "
             f"({sum(1 for t in totals if t >= 1000)/len(totals)*100:.1f}%) |")
    L.append("")

L.append("## 五、星级占比分布（按 app 统计）\n")
pcts = {k: [] for k in ("1", "2", "3", "4", "5")}
for r in ok:
    t = r.get("total") or 0
    if not t:
        continue
    for k in pcts:
        pcts[k].append((r["ratingCounts"].get(k) or 0) / t * 100)
L.append("| 星级 | 中位占比 | 均值占比 | 最小 | 最大 |")
L.append("|---|---|---|---|---|")
for k in ("5", "4", "3", "2", "1"):
    v = pcts[k]
    L.append(f"| {k} 星 | {statistics.median(v):.2f}% | {sum(v)/len(v):.2f}% | "
             f"{min(v):.2f}% | {max(v):.2f}% |")
L.append("")

L.append("## 六、抽样核对（TOP 3 + 底部 3）\n")
L.append("| app_id | app_name | ratingCounts (5→1) | sum | total | 页面均分 | 反算均分 | 一致 |")
L.append("|---|---|---|---|---|---|---|---|")
sample = sorted(ok, key=lambda r: -(r.get("total") or 0))[:3] + \
         sorted(ok, key=lambda r: (r.get("total") or 0))[:3]
for r in sample:
    c = r.get("ratingCounts") or {}
    vec = f"[{c.get('5')}, {c.get('4')}, {c.get('3')}, {c.get('2')}, {c.get('1')}]"
    L.append(f"| {r['app_id']} | {str(r.get('app_name'))[:30]} | {vec} | "
             f"{r.get('ratingCounts_sum')} | {r.get('total')} | {r.get('rating_avg')} | "
             f"{r.get('rating_avg_from_counts')} | "
             f"{'✅' if r.get('avg_consistent') else '❌'} |")
L.append("")

L.append("## 七、可直接用于加权口径的字段\n")
L.append("`ratingCounts` 的顺序为 **5星→1星**，因此：\n")
L.append("- 全量低星率 = `(ratingCounts['1'] + ratingCounts['2']) / total`")
L.append("- 全量中位星级分界 = 4星及以上占比")
L.append("- 样本加权系数 = 全量低星率 / 样本低星率\n")
L.append("本文件所有数字均来自实测抓取（`采集数据/rating_counts.jsonl`），无估算。")

open(OUT, "w", encoding="utf-8").write("\n".join(L))
print(f"-> {OUT}")
print(f"  ok={len(ok)} fail={len(fail)} 总评分数={tot_all:,} 加权均分={wavg:.4f}")
