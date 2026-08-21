# -*- coding: utf-8 -*-
"""
HTML dashboard over the three collector CSVs.

Reads the same CSVs daily_report.py reads and writes an independent HTML file. It
imports nothing from daily_report.py and changes nothing in it: the markdown report
the user reads every morning must not be able to regress because of this.

Output: logs/dashboard/<day>.html  and  logs/dashboard/latest.html

Technical constraints (the file lives in OneDrive and must open offline):
  * zero external dependencies - no CDN, no fonts, no JS
  * inline SVG + inline CSS only; hover text via the SVG <title> element
  * collapsing is native <details>; "+N more" is always a real <details>
  * prefers-color-scheme dark mode
  * colour: segments 1-5 use one 5-step single-hue sequential ramp. The intermediary
    segment is NOT a weaker step of that ramp - it is a different kind of thing - so
    it gets neutral grey plus a warning accent, an icon and the word. Every status
    colour is paired with an icon and a word; colour alone never carries meaning.

Two different "today" definitions live in this page on purpose, and both are labelled
in the page itself:
  * the segments and the intermediary share are one NATURAL DAY (date_recorded[:10]);
  * "new since the last report" and the "unhandled from the last issue" section are
    driven by the WATERMARK in logs/last_report.json (file state, reproducible).
"""

import argparse
import html
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import company_lane as CL          # noqa: E402

LOG_ROOT = os.environ.get("JOB_LOG_ROOT") or os.path.join(HERE, "logs")
OUT_DIR = os.path.join(LOG_ROOT, "dashboard")
STATE_PATH = os.path.join(LOG_ROOT, "last_report.json")

CAP = 2                 # rows shown per company per segment before "+N more"
TREND_DAYS = 7

# Rows a default-expanded segment shows before the rest goes into a nested
# <details>. cap=2 bounds a single company, not the day: on a heavy day (8/20
# grew to 2068 newgrad rows) segment 1 reached 61 rows and the first screen 73,
# past the 30-50 the spec set in 4.2. These caps make the first screen a
# function of how much you can read, not of how much the collectors found.
# Ordering is prom-descending, so what stays expanded is the most prominent -
# a truncation on the sort, never a threshold on prom (round 3 principle).
OPEN_CAP = {"1a_t3": 35, "B1": 12}

SOURCE_LABEL = {"newgrad": "LinkedIn", "ats_direct": "ATS 直连", "ddg": "DDG"}

# --- segment presentation -------------------------------------------------------
# step: index into the 5-step sequential ramp; None = off-ramp (the intermediary lane)
SEG_META = {
    "1a_t3": dict(n="①", title="今日必看", sub="tier 3 大公司 · 应届岗", step=1, open=True),
    "1a_t2": dict(n="②", title="大中公司应届岗", sub="tier 2 · 应届岗", step=2, open=False),
    "1b":    dict(n="③", title="大中公司其他岗位", sub="tier ≥ 2 · 标题不像应届岗", step=3, open=False),
    "B1":    dict(n="④", title="有自有 ATS board 的小公司", sub="tier ≤ 1，但公司出现在 ATS/DDG 采集里",
                  step=4, open=True),
    "B2":    dict(n="⑤", title="长尾", sub="其余非中介行", step=5, open=False),
    "C":     dict(n="⑥", title="中介 / 刷屏", sub="外包 · 派遣 · 培训 · 聚合站 · 纯量刷屏",
                  step=None, open=False),
}


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


# --------------------------------------------------------------------- watermark
def read_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def write_state(state):
    try:
        CL.atomic_write_json(STATE_PATH, state)
    except Exception as e:
        print("Warning: could not update the watermark %s: %s" % (STATE_PATH, e))


# --------------------------------------------------------------------- grouping
def group_segment(resolver, rows_of_segment):
    """-> [(company_key, [rows...]), ...] ordered by sort_key, rows newest first."""
    by = defaultdict(list)
    for r in rows_of_segment:
        by[CL.norm(r["company_name"])].append(r)
    for v in by.values():
        v.sort(key=lambda r: (r.get("_recorded") or "", r.get("job_title") or ""), reverse=True)
    return sorted(by.items(), key=lambda kv: resolver.sort_key(kv[0]))


def split_cap(groups, cap=CAP):
    """-> (head_rows, overflow_rows). head is the cap-2 view, overflow is "+N more"."""
    head, over = [], []
    for c, rs in groups:
        head.extend((c, r) for r in rs[:cap])
        over.extend((c, r) for r in rs[cap:])
    return head, over


# --------------------------------------------------------------------- rendering
def svg_trend(day, per_day, w=560, h=64):
    """7-day bar of deduped rows per day. Native <title> tooltips, no JS."""
    d0 = datetime.strptime(day, "%Y-%m-%d")
    days = [(d0 - timedelta(days=TREND_DAYS - 1 - i)).strftime("%Y-%m-%d")
            for i in range(TREND_DAYS)]
    vals = [per_day.get(d, 0) for d in days]
    top = max(vals + [1])
    bw = w / float(TREND_DAYS)
    parts = ['<svg class="trend" viewBox="0 0 %d %d" width="100%%" height="%d" '
             'role="img" aria-label="近 %d 天每日去重后行数">' % (w, h, h, TREND_DAYS)]
    for i, (d, v) in enumerate(zip(days, vals)):
        bh = 0 if top == 0 else max(1.0, (h - 20) * v / float(top))
        x = i * bw + 3
        cls = "bar cur" if d == day else "bar"
        parts.append('<rect class="%s" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2">'
                     '<title>%s: %d 行</title></rect>'
                     % (cls, x, (h - 16) - bh, bw - 6, bh, d, v))
        parts.append('<text class="tick" x="%.1f" y="%d" text-anchor="middle">%s</text>'
                     % (x + (bw - 6) / 2.0, h - 4, d[5:]))
        if v:
            parts.append('<text class="val" x="%.1f" y="%.1f" text-anchor="middle">%d</text>'
                         % (x + (bw - 6) / 2.0, (h - 20) - bh, v))
    parts.append("</svg>")
    return "".join(parts)


def svg_stack(counts, w=560, h=26):
    """Part-to-whole: one horizontal stacked bar over the six segments."""
    total = sum(counts.get(s, 0) for s in SEG_META) or 1
    x = 0.0
    parts = ['<svg class="stack" viewBox="0 0 %d %d" width="100%%" height="%d" '
             'role="img" aria-label="今日各段占比">' % (w, h, h)]
    for s in ("1a_t3", "1a_t2", "1b", "B1", "B2", "C"):
        v = counts.get(s, 0)
        if not v:
            continue
        seg_w = w * v / float(total)
        m = SEG_META[s]
        cls = "sl%d" % m["step"] if m["step"] else "sc"
        parts.append('<rect class="%s" x="%.2f" y="0" width="%.2f" height="%d">'
                     '<title>%s %s: %d 行 (%.1f%%)</title></rect>'
                     % (cls, x, seg_w, h, m["n"], m["title"], v, 100.0 * v / total))
        x += seg_w
    parts.append("</svg>")
    return "".join(parts)


def row_html(resolver, c, r, cutoff, show_seg=None):
    v = resolver.profile(c)
    title = (r.get("job_title") or "").strip() or "(no title)"
    link = (r.get("job_link") or "").strip()
    src = SOURCE_LABEL.get(r.get("_source"), r.get("_source") or "")
    fresh = bool(cutoff) and (r.get("_recorded") or "") > cutoff
    sig = ", ".join(resolver.row_lane(r)[1]) or (v.get("why") or "")
    cells = []
    cells.append('<td class="co"><span class="t t%d" title="tier %d">T%d</span> %s</td>'
                 % (v["tier"], v["tier"], v["tier"], esc(v.get("name") or c)))
    if link:
        cells.append('<td class="ti"><a href="%s" target="_blank" rel="noopener">%s</a>%s</td>'
                     % (esc(link), esc(title),
                        ' <span class="new" title="上一期之后新增">● 新</span>' if fresh else ""))
    else:
        cells.append('<td class="ti">%s%s</td>'
                     % (esc(title), ' <span class="new" title="上一期之后新增">● 新</span>'
                        if fresh else ""))
    cells.append('<td class="sm">%s</td>' % esc(src))
    cells.append('<td class="num">%d</td>' % resolver.window_count(c))
    if show_seg:
        m = SEG_META[show_seg]
        cells.append('<td class="sm">%s %s</td>' % (m["n"], esc(m["title"])))
    cells.append('<td class="sm sig">%s</td>' % esc(sig))
    return "<tr>%s</tr>" % "".join(cells)


def table_html(resolver, pairs, cutoff, show_seg=False, seg_of=None):
    if not pairs:
        return '<p class="empty">（空）</p>'
    head = ["公司", "岗位", "来源", "7天"]
    if show_seg:
        head.append("段")
    head.append("信号")
    out = ['<table><thead><tr>%s</tr></thead><tbody>'
           % "".join("<th>%s</th>" % h for h in head)]
    for c, r in pairs:
        out.append(row_html(resolver, c, r, cutoff,
                            show_seg=(seg_of(r) if show_seg and seg_of else None)))
    out.append("</tbody></table>")
    return "".join(out)


def details(summary_html, body_html, is_open, cls=""):
    return ('<details%s%s><summary>%s</summary><div class="body">%s</div></details>'
            % (" open" if is_open else "", (' class="%s"' % cls) if cls else "",
               summary_html, body_html))


CSS = """
:root{
  --bg:#ffffff; --fg:#16202b; --muted:#5b6876; --line:#e2e7ee; --card:#f7f9fc;
  --link:#1a4f9c; --visited:#6b5b95;
  /* single-hue sequential ramp, 5 steps, strongest = most important segment */
  --s1:#12447f; --s2:#2a78d6; --s3:#5b9ee6; --s4:#93c1f0; --s5:#c7ddf5;
  /* the intermediary lane is off-ramp on purpose: neutral + warning, never a weak blue */
  --cgrey:#6b7280; --cwarn:#a2560c; --cwarn-bg:#fdf3e6;
  --ok:#1b7a4b; --bad:#b3261e;
}
:root:not([data-theme="light"]){}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#12171d; --fg:#e6ecf3; --muted:#9aa7b4; --line:#28313b; --card:#1a212a;
    --link:#8ab8ff; --visited:#c0a8e8;
    --s1:#9ec8ff; --s2:#6ea8f0; --s3:#4a83c8; --s4:#35618f; --s5:#27455f;
    --cgrey:#8b95a1; --cwarn:#f0a44a; --cwarn-bg:#2a2118;
    --ok:#5ed09a; --bad:#ff8b82;
  }
}
:root[data-theme="dark"]{
  --bg:#12171d; --fg:#e6ecf3; --muted:#9aa7b4; --line:#28313b; --card:#1a212a;
  --link:#8ab8ff; --visited:#c0a8e8;
  --s1:#9ec8ff; --s2:#6ea8f0; --s3:#4a83c8; --s4:#35618f; --s5:#27455f;
  --cgrey:#8b95a1; --cwarn:#f0a44a; --cwarn-bg:#2a2118;
  --ok:#5ed09a; --bad:#ff8b82;
}
*{box-sizing:border-box}
body{margin:0;padding:20px 18px 60px;background:var(--bg);color:var(--fg);
  font:14px/1.5 "Segoe UI","Microsoft YaHei",system-ui,-apple-system,sans-serif;}
.wrap{max-width:1080px;margin:0 auto}
h1{font-size:19px;margin:0 0 2px}
h2{font-size:15px;margin:26px 0 8px}
.sub{color:var(--muted);font-size:12px;margin:0 0 14px}
a{color:var(--link)}
a:visited{color:var(--visited)}
a:hover{text-decoration:none}
.hero{display:flex;flex-wrap:wrap;gap:14px;align-items:stretch;margin:14px 0 6px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:12px 16px;min-width:150px}
.tile .k{font-size:11px;color:var(--muted);letter-spacing:.04em}
.tile .v{font-size:30px;font-weight:650;line-height:1.15}
.tile .d{font-size:11px;color:var(--muted)}
.tile.main{border-left:5px solid var(--s1)}
.tile.warn{border-left:5px solid var(--cwarn);background:var(--cwarn-bg)}
.banner{border:1px solid var(--cwarn);background:var(--cwarn-bg);color:var(--fg);
  border-radius:8px;padding:9px 12px;margin:12px 0;font-size:13px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:10px;
  padding:12px 14px;margin:10px 0}
details{border:1px solid var(--line);border-radius:9px;margin:9px 0;background:var(--bg);
  overflow:hidden}
details>summary{cursor:pointer;padding:9px 12px;font-weight:600;list-style:none;
  display:flex;gap:9px;align-items:baseline;flex-wrap:wrap}
details>summary::-webkit-details-marker{display:none}
details>summary::before{content:"\\25B8";color:var(--muted);font-weight:400}
details[open]>summary::before{content:"\\25BE"}
details>summary .cnt{color:var(--muted);font-weight:400;font-size:12px}
details>summary .sub{margin:0;font-size:11px}
details .body{padding:0 12px 10px;overflow-x:auto}
details details{margin:8px 0 2px;border-style:dashed}
.seg1>summary{border-left:5px solid var(--s1)}
.seg2>summary{border-left:5px solid var(--s2)}
.seg3>summary{border-left:5px solid var(--s3)}
.seg4>summary{border-left:5px solid var(--s4)}
.seg5>summary{border-left:5px solid var(--s5)}
.segc>summary{border-left:5px solid var(--cgrey);background:var(--cwarn-bg)}
table{border-collapse:collapse;width:100%;font-size:13px}
th{text-align:left;font-weight:600;color:var(--muted);font-size:11px;
  border-bottom:1px solid var(--line);padding:5px 8px 5px 0;white-space:nowrap}
td{padding:4px 8px 4px 0;border-bottom:1px solid var(--line);vertical-align:top}
td.co{white-space:nowrap;max-width:230px;overflow:hidden;text-overflow:ellipsis}
td.num{text-align:right;color:var(--muted);white-space:nowrap}
td.sm{color:var(--muted);font-size:11px;white-space:nowrap}
td.sig{max-width:210px;white-space:normal}
.t{display:inline-block;min-width:20px;text-align:center;border-radius:4px;
  font-size:10px;font-weight:700;padding:1px 3px;color:#fff}
.t3{background:var(--s1)} .t2{background:var(--s2)} .t1{background:var(--s3);color:#08243f}
.t0{background:var(--cgrey)}
.new{color:var(--cwarn);font-size:10px;font-weight:700}
.empty{color:var(--muted);font-size:12px;margin:6px 0}
.trend .bar{fill:var(--s3)} .trend .bar.cur{fill:var(--s1)}
.trend .tick,.trend .val{fill:var(--muted);font-size:9px}
.stack .sl1{fill:var(--s1)} .stack .sl2{fill:var(--s2)} .stack .sl3{fill:var(--s3)}
.stack .sl4{fill:var(--s4)} .stack .sl5{fill:var(--s5)} .stack .sc{fill:var(--cgrey)}
.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:11px;color:var(--muted);margin-top:6px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px}
.st{font-size:11px;white-space:nowrap}
.st.ok{color:var(--ok)} .st.warn{color:var(--cwarn)} .st.bad{color:var(--bad)}
footer{margin-top:34px;border-top:1px solid var(--line);padding-top:12px;
  color:var(--muted);font-size:11px}
footer li{margin:3px 0}
code{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:0 4px}
"""


def build(day, rows, profiles, overrides, priority, state):
    R = CL.LaneResolver(rows, profiles, day, overrides=overrides, priority=priority)
    today = CL.day_rows(rows, day)

    seg_of = {}
    by_seg = defaultdict(list)
    for r in today:
        s = R.segment(r)
        seg_of[id(r)] = s
        by_seg[s].append(r)

    raw = {s: len(by_seg.get(s, ())) for s in SEG_META}
    groups = {s: group_segment(R, by_seg.get(s, ())) for s in SEG_META}
    heads, overs = {}, {}
    for s in SEG_META:
        heads[s], overs[s] = split_cap(groups[s])
    cap2 = {s: len(heads[s]) for s in SEG_META}

    # ---- watermark -------------------------------------------------------
    cutoff_now = max((r.get("_recorded") or "") for r in rows) if rows else ""
    prev_cutoff = state.get("cutoff") or ""
    prev_prev = state.get("prev_cutoff") or ""
    prev_hero = state.get("hero")

    # section 7: the rows the LAST issue put in front of the user (1/2/4), so that a
    # day skipped or half-read does not silently vanish.
    carry = []
    if prev_cutoff:
        pool = [r for r in rows
                if prev_prev < (r.get("_recorded") or "") <= prev_cutoff]
        for r in CL.dedup_rows(pool)[0]:
            if R.segment(r) in ("1a_t3", "1a_t2", "B1"):
                carry.append(r)
    carry_head, carry_over = split_cap(group_segment(R, carry))
    carry_seg = {}
    for _c, r in carry_head + carry_over:
        carry_seg[id(r)] = R.segment(r)

    # ---- health ----------------------------------------------------------
    day_cos = {}
    for r in today:
        day_cos.setdefault(CL.norm(r["company_name"]), (r.get("company_name") or "").strip())
    unenriched = sorted((v or k) for k, v in day_cos.items()
                        if R.profile(k).get("stage", 0) < 1)
    per_day = Counter()
    for r in rows:
        per_day[r["_day"]] += 1
    dedup_per_day = {}
    d0 = datetime.strptime(day, "%Y-%m-%d")
    for i in range(TREND_DAYS):
        d = (d0 - timedelta(days=i)).strftime("%Y-%m-%d")
        dedup_per_day[d] = len(CL.day_rows(rows, d))

    # what is actually expanded on load: the open segments, each capped by OPEN_CAP
    visible = sum(min(cap2[s], OPEN_CAP.get(s, cap2[s])) for s in ("1a_t3", "B1"))
    total_raw = sum(raw.values())
    c_share = 100.0 * raw["C"] / total_raw if total_raw else 0.0

    # ---- head ------------------------------------------------------------
    P = []
    P.append('<div class="wrap">')
    P.append('<h1>岗位 Dashboard · %s</h1>' % esc(day))
    P.append('<p class="sub">生成于 %s ·  去重后 %d 行 / %d 家公司 ·  '
             '分段口径 = 自然日 <code>date_recorded[:10]</code></p>'
             % (esc(datetime.now().strftime("%Y-%m-%d %H:%M")), total_raw, len(day_cos)))

    # hero
    P.append('<div class="hero">')
    P.append('<div class="tile main"><div class="k">今日必看（段①）</div>'
             '<div class="v">%d</div><div class="d">上一期 %s 条</div></div>'
             % (cap2["1a_t3"], "—" if prev_hero is None else str(prev_hero)))
    P.append('<div class="tile"><div class="k">默认可见（①+④）</div>'
             '<div class="v">%d</div><div class="d">一键展开 ② 后 %d 条</div></div>'
             % (visible, visible + cap2["1a_t2"]))
    P.append('<div class="tile"><div class="k">今日去重后</div>'
             '<div class="v">%d</div><div class="d">压缩 %.0f 倍</div></div>'
             % (total_raw, (total_raw / visible) if visible else 0))
    P.append('<div class="tile warn"><div class="k">⚠ 中介 / 刷屏（下界）</div>'
             '<div class="v">%.0f%%</div><div class="d">%d 行 / %d 家</div></div>'
             % (c_share, raw["C"],
                len({CL.norm(r["company_name"]) for r in by_seg.get("C", ())})))
    P.append('</div>')

    if unenriched:
        P.append('<div class="banner">⚠ <b>%d 家未分层</b>'
                 '（今天出现、但还没有富化档案）。它们按设计<b>不会</b>进中介面板，'
                 '而是落在 ⑤ 长尾里等明早 07:30 的 <code>enrich_companies.py</code>。'
                 '例：%s</div>'
                 % (len(unenriched),
                    esc("、".join(unenriched[:6]))))

    # ---- panel: 7-day bar + stacked share ---------------------------------
    P.append('<h2>近 %d 天 / 今日构成</h2>' % TREND_DAYS)
    P.append('<div class="panel">%s%s' % (svg_trend(day, dedup_per_day), svg_stack(raw)))
    P.append('<div class="legend">')
    for s in ("1a_t3", "1a_t2", "1b", "B1", "B2", "C"):
        m = SEG_META[s]
        col = "var(--s%d)" % m["step"] if m["step"] else "var(--cgrey)"
        P.append('<span><i style="background:%s"></i>%s %s %d</span>'
                 % (col, m["n"], esc(m["title"]), raw[s]))
    P.append('</div></div>')

    # ---- the seven sections ------------------------------------------------
    P.append('<h2>分段（raw = 当日全部行，cap2 = 每家公司最多先看 2 条）</h2>')
    cls_of = {"1a_t3": "seg1", "1a_t2": "seg2", "1b": "seg3", "B1": "seg4",
              "B2": "seg5", "C": "segc"}
    for s in ("1a_t3", "1a_t2", "1b", "B1", "B2", "C"):
        m = SEG_META[s]
        shown, folded = heads[s], []
        if m["open"] and s in OPEN_CAP and len(shown) > OPEN_CAP[s]:
            shown, folded = shown[:OPEN_CAP[s]], shown[OPEN_CAP[s]:]
        body = table_html(R, shown, prev_cutoff)
        if folded:
            body += details('还有 %d 条 <span class="cnt">（知名度更靠后，先看上面的）</span>'
                            % len(folded),
                            table_html(R, folded, prev_cutoff), False)
        if overs[s]:
            body += details('+%d more <span class="cnt">（同公司的第 3 条及以后）</span>'
                            % len(overs[s]),
                            table_html(R, overs[s], prev_cutoff), False)
        icon = "⚠ " if s == "C" else ""
        summary = ('%s%s %s <span class="cnt">raw %d · cap2 %d</span>'
                   '<span class="sub">%s</span>'
                   % (icon, m["n"], esc(m["title"]), raw[s], cap2[s], esc(m["sub"])))
        P.append(details(summary, body, m["open"], cls_of[s]))

    # section 7 - carry-over
    cbody = table_html(R, carry_head, "", show_seg=True,
                       seg_of=lambda r: carry_seg.get(id(r), "1a_t3"))
    if carry_over:
        cbody += details('+%d more' % len(carry_over),
                         table_html(R, carry_over, "", show_seg=True,
                                    seg_of=lambda r: carry_seg.get(id(r), "1a_t3")), False)
    if not prev_cutoff:
        cbody = ('<p class="empty">还没有上一期水位线（这是第一次生成）。'
                 '下一次运行开始，这里会列出上一期摆在你面前、可能还没处理的 ①②④ 行。</p>')
    P.append(details('⑦ 上一期未处理 <span class="cnt">%d 行</span>'
                     '<span class="sub">水位线区间 %s → %s 内落在 ①②④ 的行</span>'
                     % (len(carry_head) + len(carry_over),
                        esc(prev_prev or "开始"), esc(prev_cutoff or "—")),
                     cbody, False))

    # ---- panel 2' : intermediary share ------------------------------------
    P.append("<h2>面板 ②′ 中介 / 刷屏占比</h2>")
    cco = Counter(CL.norm(r["company_name"]) for r in by_seg.get("C", ()))
    P.append('<div class="panel"><p class="sub">今日 <b>%d / %d 行 = %.1f%%</b>，'
             '来自 <b>%d</b> 家公司。<b>这是下界</b>：识别靠 LLM 的 kind 判定，'
             '日常增量用 gpt-4o-mini，它的中介召回明显低于 gpt-4o'
             '（50 家样本 16/50 → 5/50）。每月手动跑一次 '
             '<code>python enrich_companies.py --deep</code> 把召回补回来。'
             '本面板按<b>自然日</b>计，与上面 hero 的水位线口径不同。</p>'
             % (raw["C"], total_raw, c_share, len(cco)))
    P.append('<table><thead><tr><th>公司</th><th>今日</th><th>近 7 天</th>'
             '<th>来源</th><th>判据</th><th>状态</th></tr></thead><tbody>')
    for c, n in sorted(cco.items(), key=lambda kv: (-kv[1], kv[0]))[:25]:
        v = R.profile(c)
        sig = ", ".join(R.company_lane(c)[1])
        n7 = R.window_count(c)
        srcs = {SOURCE_LABEL.get(r.get("_source"), "?")
                for r in R.win_by.get(c, ()) if r}
        burst = n >= max(5, int(0.7 * n7)) and n7 > n * 0.9
        st = ('<span class="st warn">🔺 突发</span>' if burst
              else '<span class="st ok">持续</span>')
        P.append("<tr><td class=\"co\">%s</td><td class=\"num\">%d</td>"
                 "<td class=\"num\">%d</td><td class=\"sm\">%s</td>"
                 "<td class=\"sm sig\">%s</td><td>%s</td></tr>"
                 % (esc(v.get("name") or c), n, n7, esc("/".join(sorted(srcs))), esc(sig), st))
    P.append("</tbody></table></div>")

    # ---- panel 3 : repost evidence ----------------------------------------
    at_rows = [r for r in today if " at " in (r.get("job_title") or "")]
    at_by = Counter(CL.norm(r["company_name"]) for r in at_rows)
    P.append("<h2>面板 ③ 转贴证据（展示列，<b>不参与判定</b>）</h2>")
    P.append('<div class="panel"><p class="sub">标题里带 <code> at X</code> = '
             '把别家岗位挂在自己名下。这个信号 signature 很干净但覆盖极窄，'
             '所以它只是证据，判断权在你。</p>')
    if at_by:
        P.append('<table><thead><tr><th>公司</th><th>带 “at X” 的行</th>'
                 '<th>今日全部行</th><th>当前段</th><th>例</th></tr></thead><tbody>')
        cnt_all = Counter(CL.norm(r["company_name"]) for r in today)
        for c, n in sorted(at_by.items(), key=lambda kv: (-kv[1], kv[0]))[:15]:
            ex = next(r for r in at_rows if CL.norm(r["company_name"]) == c)
            m = SEG_META[R.segment(ex)]
            P.append("<tr><td class=\"co\">%s</td><td class=\"num\">%d</td>"
                     "<td class=\"num\">%d</td><td class=\"sm\">%s %s</td>"
                     "<td class=\"sm sig\">%s</td></tr>"
                     % (esc(R.profile(c).get("name") or c), n, cnt_all[c],
                        m["n"], esc(m["title"]), esc((ex.get("job_title") or "")[:60])))
        P.append("</tbody></table>")
    else:
        P.append('<p class="empty">今天没有带 “at X” 的标题。</p>')
    P.append("</div>")

    # ---- footnotes ---------------------------------------------------------
    P.append("<footer><b>口径与已知缺口</b><ul>")
    P.append("<li><b>零丢弃</b>：应届相关性正则是<u>分段依据</u>，不是过滤器。"
             "六段 raw 相加 = %d = 当日去重后行数，没有任何一行被丢掉。</li>" % total_raw)
    P.append("<li><b>两个「今天」</b>：分段与面板 ②′ 用自然日；"
             "hero 的「上一期」、行尾的「● 新」、⑦ 段用水位线 "
             "<code>logs/last_report.json</code>。两者对不上是设计，不是 bug。</li>")
    P.append("<li><b>两套已读记忆</b>：水位线是文件状态、唯一权威、可复现；"
             "链接的已访问颜色是浏览器状态、best-effort，清缓存或换浏览器即失效。</li>")
    P.append("<li>2023 年之后成立/分拆的公司（Cursor、Sierra AI、Harvey、Figure、"
             "Decagon、Solventum…）<b>任何模型任何批次都拿不到 tier</b>，永久落 ⑤ 段。"
             "唯一兜底是 <code>company_overrides.json</code>（当前 %d 条）。</li>"
             % len(overrides))
    P.append("<li><code>prom</code> 是一次 LLM 采样并永久缓存；约 4.4%% 的公司"
             "其段内位置由那一次调用决定。override 可以覆盖 <code>prom</code>。</li>")
    P.append("<li><b>只追踪新增侧</b>：<code>date_recorded</code> 是首次收录时间，"
             "岗位下架不反映在这里。</li>")
    P.append("<li>中介占比是<b>下界</b>，理由见面板 ②′。</li>")
    P.append("</ul></footer></div>")

    new_state = {"day": day, "cutoff": cutoff_now, "prev_cutoff": prev_cutoff,
                 "hero": cap2["1a_t3"],
                 "generated_at": datetime.now().isoformat(timespec="seconds")}
    stats = {"raw": raw, "cap2": cap2, "visible": visible, "total": total_raw,
             "unenriched": len(unenriched), "carry": len(carry_head) + len(carry_over)}
    page = ("<!doctype html><html lang=\"zh\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>岗位 Dashboard %s</title><style>%s</style></head><body>%s</body></html>"
            % (esc(day), CSS, "".join(P)))
    return page, new_state, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description="HTML dashboard over the collector CSVs")
    ap.add_argument("--date", default=None, metavar="YYYY-MM-DD")
    ap.add_argument("--out", default=None, help="write the HTML here instead")
    ap.add_argument("--no-watermark", action="store_true",
                    help="do not advance logs/last_report.json (re-runs, tests)")
    args = ap.parse_args(argv)

    day = args.date or date.today().strftime("%Y-%m-%d")
    datetime.strptime(day, "%Y-%m-%d")

    rows = CL.load_rows(HERE)
    profiles = CL.load_profiles()
    overrides = CL.load_overrides()
    priority = CL.load_priority()
    state = read_state()

    page, new_state, stats = build(day, rows, profiles, overrides, priority, state)

    os.makedirs(OUT_DIR, exist_ok=True)
    out = args.out or os.path.join(OUT_DIR, "%s.html" % day)
    for path in ([out] if args.out else [out, os.path.join(OUT_DIR, "latest.html")]):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(page)
        os.replace(tmp, path)

    # Only advance the watermark on a real scheduled run, and only when something new
    # actually arrived - otherwise a second run in the same minute would collapse the
    # "unhandled from the last issue" interval to nothing.
    if (not args.no_watermark and not args.date and not args.out
            and new_state["cutoff"] != new_state["prev_cutoff"]):
        write_state(new_state)

    print("=" * 60)
    print("Dashboard - %s" % day)
    print("=" * 60)
    for s in ("1a_t3", "1a_t2", "1b", "B1", "B2", "C"):
        m = SEG_META[s]
        print("  %s %-22s raw %4d   cap2 %4d" % (m["n"], m["title"], stats["raw"][s],
                                                 stats["cap2"][s]))
    print("  raw total %d == deduped rows for the day %d" % (sum(stats["raw"].values()),
                                                             stats["total"]))
    print("  default visible (1 + 4): %d" % stats["visible"])
    if stats["unenriched"]:
        print("  %d company/companies not yet enriched (they stay out of lane C)"
              % stats["unenriched"])
    print("\nWritten to %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
