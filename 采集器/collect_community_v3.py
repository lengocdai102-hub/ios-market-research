"""
Apple Community 扩量采集器 v3
- 板块页 /community/<board>?page=N 深翻页 + ?sortBy=recent / sortBy=votes 变体
- 每帖字段：标题、正文摘要、板块、回复数、点赞数、日期、参与人数、是否有官方回复、来源URL、采集时间
- 支持增量续跑（读已有 jsonl 去重）
"""
import json, os, re, sys, time, argparse
from datetime import datetime, timezone
from patchright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
BASE = "https://discussions.apple.com"

BOARDS = [
    "iphone", "ipad", "macos", "mac", "watch", "airpods", "accessories",
    "tv-and-home", "apple-intelligence", "apple-vision-pro", "icloud",
    "music", "applications-services", "apple-account", "stores",
    "using_apple_support_communities", "macos-tv-home-theater",
    "wallet/other-apple-wallet",
]

DATE_RE = re.compile(r"Posted on ([A-Z][a-z]{2} \d{1,2}, \d{4} \d{1,2}:\d{2} [AP]M)")


def log(m):
    print(m, flush=True)


class Collector:
    def __init__(self, delay=1.5, pages=12, out=None):
        self.delay = delay
        self.pages = pages
        self.out = out
        self.seen = set()
        self.listed = set()

    def load_existing(self, path):
        if path and os.path.exists(path):
            n = 0
            for line in open(path, encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                tid = r.get("thread_id") or r.get("url")
                if tid:
                    self.seen.add(str(tid))
                    n += 1
            log(f"[init] 载入已有 {n} 条")

    # ---------- 列表页 ----------
    def scrape_list(self, pg, url, retries=4):
        last = None
        for att in range(retries):
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(900)
                els = pg.query_selector_all(
                    "a.content-post-title[href*='/thread/'], a.thread-title[href*='/thread/']")
                out = []
                for e in els:
                    href = e.get_attribute("href") or ""
                    if not re.match(r"^/thread/\d+", href):
                        continue
                    t = re.sub(r"\s+", " ", (e.inner_text() or "").strip())
                    if t:
                        out.append((href, t))
                if out:
                    return out
                last = "no items"
            except Exception as e:
                last = f"{type(e).__name__} {str(e)[:70]}"
            time.sleep(3.0 + att * 2)
        log(f"  ! list fail {url}: {last}")
        return []

    # ---------- 详情页 ----------
    def scrape_detail(self, pg, href, title, board):
        url = BASE + href
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(1000)
        except Exception as e:
            return None
        try:
            return pg.evaluate("""() => {
              const txt = s => { const e=document.querySelector(s); return e? e.innerText.trim():null; };
              const bodyEl = document.querySelector('.post-body') || document.querySelector('.post-content');
              const body = bodyEl ? bodyEl.innerText.replace(/\\s+/g,' ').trim() : '';
              const posts = document.querySelectorAll('.content-post');
              const answers = document.querySelectorAll('.content-post.answer');
              const authors = Array.from(document.querySelectorAll('.post-author-name'))
                                     .map(e=>e.innerText.trim());
              const uniqAuthors = Array.from(new Set(authors.filter(Boolean)));
              // 点赞：优先 aria-label / title 含 like/upvote 的元素
              let likes = 0;
              const lk = document.querySelector('[class*="like"], [class*="vote"], [aria-label*="like" i]');
              if (lk) { const t=lk.innerText||''; const m=t.match(/\\d+/); if(m) likes=parseInt(m[0]); }
              // 官方回复：作者名含 Apple/Moderator/Community
              const official = authors.some(a=>/apple|moderator|community/i.test(a));
              const h1 = txt('h1') || txt('.thread-title') || '';
              // 日期
              let date=null;
              const full = document.body.innerText;
              const m = full.match(/Posted on [A-Z][a-z]{2} \\d{1,2}, \\d{4} \\d{1,2}:\\d{2} [AP]M/);
              if (m) date = m[0].replace('Posted on ','');
              return {body: body.slice(0,600), bodyLen: body.length, h1: h1.slice(0,300),
                      replies: answers.length, participants: uniqAuthors.length,
                      likes: likes, official: official, date: date,
                      hasAccepted: !!document.querySelector('.top-post-indicator, [class*="accepted"]')};
            }""")
        except Exception:
            return None

    def run(self, boards, mode="boards", queries=None, max_details=0):
        os.makedirs(os.path.dirname(self.out) or ".", exist_ok=True)
        fh = open(self.out, "a", encoding="utf-8")
        total_new = 0
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox"])
            ctx = b.new_context(user_agent=UA, locale="en-US", viewport={"width": 1440, "height": 900})
            pg = ctx.new_page()

            # 预热：先访问首页过 Cloudflare
            try:
                pg.goto(BASE + "/community/iphone?page=2", wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(1500)
            except Exception:
                pass

            jobs = []   # (url, board, kind)
            if mode in ("boards", "both"):
                for bd in boards:
                    for p in range(1, self.pages + 1):
                        jobs.append((f"{BASE}/community/{bd}?page={p}", bd, "board"))
            if mode in ("search", "both") and queries:
                for q in queries:
                    for p in range(1, self.pages + 1):
                        jobs.append((f"{BASE}/search?q={q.replace(' ', '+')}&page={p}", q, "search"))

            pending = []
            for url, bd, kind in jobs:
                items = self.scrape_list(pg, url)
                if not items:
                    continue
                new = 0
                for href, title in items:
                    tid = href.split("/")[2]
                    if tid in self.listed:
                        continue
                    self.listed.add(tid)
                    pending.append((href, title, bd, kind))
                    new += 1
                log(f"[{kind}] {bd[:40]:42} p{url.split('page=')[-1][:3]:4} {len(items):3} 条 (新 {new:3}) 待抓 {len(pending)}")
                if max_details and len(pending) >= max_details:
                    break
                time.sleep(self.delay)

            log(f"=== 列表采集完成，待抓详情 {len(pending)} 帖 ===")
            for i, (href, title, bd, kind) in enumerate(pending):
                tid = href.split("/")[2]
                if tid in self.seen:
                    continue
                d = self.scrape_detail(pg, href, title, bd)
                if not d:
                    continue
                rec = {
                    "thread_id": tid,
                    "url": BASE + href,
                    "title": d.get("h1") or title,
                    "list_title": title,
                    "board": bd,
                    "source_kind": kind,
                    "body_snippet": d.get("body", ""),
                    "body_len": d.get("bodyLen", 0),
                    "replies": d.get("replies", 0),
                    "participants": d.get("participants", 0),
                    "likes": d.get("likes", 0),
                    "has_official_reply": d.get("official", False),
                    "has_accepted_answer": d.get("hasAccepted", False),
                    "date": d.get("date"),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                }
                self.seen.add(tid)
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                total_new += 1
                if total_new % 10 == 0:
                    fh.flush()
                    log(f"  ... 已抓 {total_new} 帖")
                time.sleep(self.delay)

            fh.close()
            b.close()
        log(f"=== DONE 新增 {total_new} 帖 -> {self.out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--boards", default="")
    ap.add_argument("--pages", type=int, default=12)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--mode", default="boards", choices=["boards", "search", "both"])
    ap.add_argument("--qfile", default="")
    ap.add_argument("--max-details", type=int, default=0)
    a = ap.parse_args()
    boards = [x for x in a.boards.split(",") if x]
    queries = json.load(open(a.qfile)) if a.qfile else None
    c = Collector(delay=a.delay, pages=a.pages, out=a.out)
    c.load_existing(a.out)
    c.run(boards, mode=a.mode, queries=queries, max_details=a.max_details)


if __name__ == "__main__":
    main()
