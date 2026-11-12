# 采集器代码说明

本目录是本次调研的**全部可复现脚本**，共 66 个 Python 文件（约 540KB）。
采集时间 2026-11-09 ~ 2026-11-11。

---

## 环境准备

```bash
python3 -m venv ~/.venvs/scrapling
source ~/.venvs/scrapling/bin/activate
uv pip install --only-binary=:all: scrapling
```

⚠ **`--only-binary=:all:` 必须加** —— 否则 `cryptography` 会走源码编译，在本机卡死。

---

## 关键约定（踩过坑，别改）

| 约定 | 说明 |
|---|---|
| **必须真实 Chrome** | `StealthyFetcher(fetch_page=True)` + `real_chrome=True`，复用本机已装的 Chrome 指纹。纯 `urllib` 直连 Apple 返回 **403**。 |
| **走代理抓美区** | 直连 `apps.apple.com` 会 302 到中国区首页（HTTP 200 但评论/评分分布解析为空）。抓美区**必须** `export http_proxy=http://127.0.0.1:7897`。 |
| **评分分布在普通页** | 不在 `?see-all=reviews` 页。两页都要抓。 |
| **评论路径** | `data[0].data.shelfMapping.allProductReviews.items[].review` |
| **see-all 内嵌 JSON** | 页面含约 108KB 的 `SeeAllPageIntent`，可从中直接解析。 |
| **Apple 社区标题** | 必须用 `a.thread-title` 精确选择器，泛选会混进回复正文。 |
| **社区站 Cloudflare** | 必须真实 Chrome 渲染。 |
| **评论 RSS 已失效** | 旧路失效，`amp-api` token 也已被 Apple 移除。**不要走老路。** |
| **Apple 从不公开下载量** | 任何输出都不得把代理值写成官方下载量。只能用 `userRatingCount` / 榜单名次 / 评论数 / 版本更新频率，并在输出里标注这是**代理指标**及估算假设。 |
| **输出目录** | 用 `SCR_OUT` 环境变量指定。 |

---

## 主流程

```bash
# 1. 生成采集输入（竞品 / 社区查询 / lookup 查询）
python3 gen_inputs.py
python3 split_and_gen.py          # 切成 4 个 bot 分片

# 2. 采集（核心采集器）
python3 scr_collect.py <input.json> --out <dir>

# 3. 汇总
python3 aggregate.py

# 4. 独立交叉核验 —— 从原始数据重算，不采信采集期写入的统计值
python3 verify.py
python3 cross_verify_v2.py       # 终版：9 项核心指标
```

---

## 脚本分组

### 主流程
`gen_inputs.py` · `split_and_gen.py` · `scr_collect.py` · `aggregate.py` · `verify.py` · `cross_verify_v2.py`

### 竞品池扩展
`gen_competitor_pool.py` · `dev_classify_v2.py` · `deepdive_pool.py`

### 深度下钻
`deepdive_*.py`（时间序列 / 痛点 / 信任 / 赢家 / 僵尸位 / 独立开发者 / 机会挖掘等）

### 社区 / 论坛
`collect_community_v2/v3.py` · `collect_forum_*.py` · `forum_crossref.py` · `final_weighted_pain.py`

### 定价
`build_master_reviews.py` · 定价解析相关脚本

---

## 纪律

1. 采集失败、跳过、抓不到 → **如实报告并给出原因和证据**，禁止编造条数、比例、引用。
2. 每条结论必须能追溯到**具体数据文件**。
3. 核心指标一律**从原始数据独立重算**，不信任采集期写入的统计值 —— 这是 9/9 交叉核验能通过的前提。
4. 交接给下游时必须写清：**来源 URL 模板、采集时间、口径定义、样本量、已知缺口**。
