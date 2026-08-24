# -*- coding: utf-8 -*-
"""
HTML dashboard over the three collector CSVs.

Reads the same CSVs daily_report.py reads and writes an independent bundle. It
imports nothing from daily_report.py and changes nothing in it: the markdown report
the user reads every morning must not be able to regress because of this.

Output: a self-contained bundle in `logs/dashboard/` - `latest.html` (the only HTML
file; double-click it), `dashboard.css`, `dashboard.js`, `data-index.js` and one
`data-<day>.js` block per natural day inside the retention window. There is no
per-day HTML page: a frozen snapshot is `--date <day> --out <dir>`, which writes the
whole bundle recomputed under that anchor.

Technical constraints (the file lives in OneDrive and must open offline):
  * zero external dependencies - no CDN, no fonts, no npm, no build step
  * classic <script src> and same-directory <link rel=stylesheet> only: ES modules
    and fetch/XHR are blocked under file:// (measured)
  * inline SVG; hover text via the SVG <title> element
  * collapsing is native <details>; "+N more" is always a real <details>
  * prefers-color-scheme dark mode
  * colour: segments 1-5 use one 5-step single-hue sequential ramp. The intermediary
    segment is NOT a weaker step of that ramp - it is a different kind of thing - so
    it gets neutral grey plus a warning accent, an icon and the word. Every status
    colour is paired with an icon and a word; colour alone never carries meaning.

This file computes; web/dashboard.js frames. The dividing line is not a style
preference: which segment a row belongs to carries five of the nine invariants and
every one of them has a fixture, so it is decided here and shipped to the browser as
an integer. The browser reconciles what it rendered against `JOB_INDEX.check`, which
is `view.window_view()`'s own return value.

Two different clocks live in this page on purpose, and both are labelled in it:
  * the window (N days) is what the reader chose to look at;
  * "new since the last report" and section 7 are driven by the WATERMARK in
    logs/last_report.json (file state, reproducible).
"""

import argparse
import html
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import company_lane as CL          # noqa: E402
import view                        # noqa: E402

LOG_ROOT = os.environ.get("JOB_LOG_ROOT") or os.path.join(HERE, "logs")
OUT_DIR = os.path.join(LOG_ROOT, "dashboard")
STATE_PATH = os.path.join(LOG_ROOT, "last_report.json")
WEB_DIR = os.path.join(HERE, "web")

CAP = view.CAP                     # rows per company per segment, over the WINDOW
OPEN_CAP = view.SEG_OPEN_CAP       # name kept: tests/test_lane.py imports it
TREND_DAYS = 7                     # svg_trend's default; the page passes N instead

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
CLS_OF = {"1a_t3": "seg1", "1a_t2": "seg2", "1b": "seg3", "B1": "seg4",
          "B2": "seg5", "C": "segc"}
DAY_HTML_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.html$")


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
def svg_trend(day, per_day, days=None, w=560, h=64):
    """Bar per natural day of rows that survived dedup. Native <title> tooltips.

    `days` is the list of dates to draw, oldest first (R1: it follows the reader's
    N). Empty days keep their slot so a gap in collection stays visible.
    """
    if days is None:
        days = view.days_back(day, TREND_DAYS)
    nd = max(1, len(days))
    vals = [per_day.get(d, 0) for d in days]
    top = max(vals + [1])
    bw = w / float(nd)
    every = 1 if nd <= 10 else (3 if nd <= 16 else 5)
    parts = ['<svg class="trend" viewBox="0 0 %d %d" width="100%%" height="%d" '
             'role="img" aria-label="近 %d 天每日去重后行数">' % (w, h, h, nd)]
    for i, (d, v) in enumerate(zip(days, vals)):
        bh = 0 if top == 0 else max(1.0, (h - 20) * v / float(top))
        x = i * bw + 3
        cls = "bar cur" if d == day else "bar"
        parts.append('<rect class="%s" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2">'
                     '<title>%s: %d 行</title></rect>'
                     % (cls, x, (h - 16) - bh, max(1.0, bw - 6), bh, d, v))
        if (nd - 1 - i) % every == 0:
            parts.append('<text class="tick" x="%.1f" y="%d" text-anchor="middle">%s</text>'
                         % (x + (bw - 6) / 2.0, h - 4, d[5:]))
        if v and nd <= 10:
            parts.append('<text class="val" x="%.1f" y="%.1f" text-anchor="middle">%d</text>'
                         % (x + (bw - 6) / 2.0, (h - 20) - bh, v))
    parts.append("</svg>")
    return "".join(parts)


def svg_stack(counts, w=560, h=26):
    """Part-to-whole: one horizontal stacked bar over the six segments.

    Every rect is wrapped in an SVG-native <a href="#seg-...">, so jumping to a
    segment costs zero JS (R3 steps 1-3).
    """
    total = sum(counts.get(s, 0) for s in SEG_META) or 1
    x = 0.0
    parts = ['<svg class="stack" viewBox="0 0 %d %d" width="100%%" height="%d" '
             'role="img" aria-label="窗口内各段占比">' % (w, h, h)]
    for s in CL.SEGMENT_ORDER:
        v = counts.get(s, 0)
        if not v:
            continue
        seg_w = w * v / float(total)
        m = SEG_META[s]
        cls = "sl%d" % m["step"] if m["step"] else "sc"
        parts.append('<a href="#seg-%s"><rect class="%s" x="%.2f" y="0" width="%.2f" '
                     'height="%d"><title>%s %s: %d 行 (%.1f%%)</title></rect></a>'
                     % (s, cls, x, seg_w, h, m["n"], m["title"], v, 100.0 * v / total))
        x += seg_w
    parts.append("</svg>")
    return "".join(parts)


def legend_html(counts):
    out = ['']
    for s in CL.SEGMENT_ORDER:
        m = SEG_META[s]
        col = "var(--s%d)" % m["step"] if m["step"] else "var(--cgrey)"
        out.append('<a href="#seg-%s"><i style="background:%s"></i>%s %s %d</a>'
                   % (s, col, m["n"], esc(m["title"]), counts.get(s, 0)))
    return "".join(out)


# ------------------------------------------------------------- window helpers
def _win_rows(payload, n):
    """[(day index, row index, cols), ...] for the rows the window actually shows
    (view=all). Reads the PAYLOAD, so the panels describe the same bytes the
    browser got."""
    index = payload["index"]
    days, blocks = index["days"], payload["days"]
    lo = max(0, len(days) - n)
    out = []
    for di in range(lo, len(days)):
        cols = blocks.get(days[di])
        if not cols:
            continue
        for i, x in enumerate(cols["x"]):
            if not x:
                out.append((di, i, cols))
    return out


def hero_html(index, wv, state):
    """The four big numbers. Every title carries "全部窗口": switching the display
    filter changes the segment tables by 11x-90x while these keep describing the
    whole window, and a line of small print next to the switch is not enough."""
    segs = CL.SEGMENT_ORDER
    cap2 = {s: wv["cap2"][i] for i, s in enumerate(segs)}
    raw = {s: wv["raw"][i] for i, s in enumerate(segs)}
    total = wv["dedup"]
    opened = wv["open"]
    prev_hero = state.get("hero")
    c_share = 100.0 * raw["C"] / total if total else 0.0
    untrunc = sum(cap2.get(s, 0) for s in view.OPEN_ORDER)
    if opened < view.FLOOR and untrunc >= view.FLOOR:
        d2 = ("①② 的量不够，④ 按设计封顶 %d 行" % view.SEG_OPEN_CAP["B1"])
    else:
        d2 = ("在 ①④② 各自上限内补到 %d 行，最多 %d 行" % (view.FLOOR, view.CEIL))
    p = []
    p.append('<div class="tile main"><div class="k">今日必看（段①，全部窗口）</div>'
             '<div class="v">%d</div><div class="d">上一期 %s 条</div></div>'
             % (cap2["1a_t3"], "—" if prev_hero is None else str(prev_hero)))
    p.append('<div class="tile"><div class="k">首屏展开（①④②，全部窗口）</div>'
             '<div class="v">%d</div><div class="d">%s</div></div>' % (opened, esc(d2)))
    p.append('<div class="tile"><div class="k">窗口去重后（全部窗口）</div>'
             '<div class="v">%d</div><div class="d">压缩 %.0f 倍</div></div>'
             % (total, (total / opened) if opened else 0))
    p.append('<div class="tile warn"><div class="k">⚠ 中介 / 刷屏（下界，全部窗口）</div>'
             '<div class="v">%.0f%%</div><div class="d">%d 行</div></div>'
             % (c_share, raw["C"]))
    return "".join(p)


def panel2_html(payload, n, wv):
    """Intermediary share over the whole window."""
    index = payload["index"]
    co, sigs = index["co"], index["sigs"]
    segs = CL.SEGMENT_ORDER
    ci = segs.index("C")
    rows = _win_rows(payload, n)
    total = wv["dedup"]
    craw = wv["raw"][ci]
    per_co = Counter()
    win_all = Counter()
    srcs = defaultdict(set)
    for di, i, cols in rows:
        c = cols["c"][i]
        win_all[c] += 1
        if cols["g"][i] == ci:
            per_co[c] += 1
            srcs[c].add(index["srcs"][cols["s"][i]])
    share = 100.0 * craw / total if total else 0.0
    p = ['<p class="sub">窗口内 <b>%d / %d 行 = %.1f%%</b>，来自 <b>%d</b> 家公司。'
         '<b>这是下界</b>：识别靠 LLM 的 kind 判定，日常增量用 gpt-4o-mini，'
         '它的中介召回明显低于 gpt-4o（50 家样本 16/50 → 5/50）。每月手动跑一次 '
         '<code>python enrich_companies.py --deep</code> 把召回补回来。'
         '这一块与上面的趋势图一样描述<b>整个窗口</b>，不随「显示」开关变。</p>'
         % (craw, total, share, len(per_co))]
    p.append('<table><thead><tr><th>公司</th><th>窗口内</th><th>近 %d 天</th>'
             '<th>来源</th><th>判据</th><th>状态</th></tr></thead><tbody>'
             % index["w7_days"])
    for c, k in sorted(per_co.items(), key=lambda kv: (-kv[1], co[kv[0]][0]))[:25]:
        rec = co[c]
        n7 = rec[3]
        burst = k >= max(5, int(0.7 * n7)) and n7 > k * 0.9
        stt = ('<span class="st warn">🔺 突发</span>' if burst
               else '<span class="st ok">持续</span>')
        p.append('<tr><td class="co">%s</td><td class="num">%d</td>'
                 '<td class="num">%d</td><td class="sm">%s</td>'
                 '<td class="sm sig">%s</td><td>%s</td></tr>'
                 % (esc(rec[0]), k, n7, esc("/".join(sorted(srcs.get(c, ())))),
                    esc(sigs[rec[5]]), stt))
    if not per_co:
        p.append('<tr><td colspan="6" class="sm">（窗口内没有被判为中介的行）</td></tr>')
    p.append("</tbody></table>")
    return "".join(p)


def panel3_html(payload, n):
    """Repost evidence. A display column, never a criterion."""
    index = payload["index"]
    co = index["co"]
    segs = CL.SEGMENT_ORDER
    rows = _win_rows(payload, n)
    at_by = Counter()
    all_by = Counter()
    example = {}
    for di, i, cols in rows:
        c = cols["c"][i]
        all_by[c] += 1
        t = cols["t"][i]
        if " at " in t:
            at_by[c] += 1
            example.setdefault(c, (t, cols["g"][i]))
    p = ['<p class="sub">标题里带 <code> at X</code> = 把别家岗位挂在自己名下。'
         '这个信号 signature 很干净但覆盖极窄，所以它只是证据，判断权在你。'
         '统计口径是<b>整个窗口</b>。</p>']
    if not at_by:
        return "".join(p) + '<p class="empty">窗口内没有带 “at X” 的标题。</p>'
    p.append('<table><thead><tr><th>公司</th><th>带 “at X” 的行</th>'
             '<th>窗口内全部行</th><th>当前段</th><th>例</th></tr></thead><tbody>')
    for c, k in sorted(at_by.items(), key=lambda kv: (-kv[1], co[kv[0]][0]))[:15]:
        t, g = example[c]
        m = SEG_META[segs[g]]
        p.append('<tr><td class="co">%s</td><td class="num">%d</td>'
                 '<td class="num">%d</td><td class="sm">%s %s</td>'
                 '<td class="sm sig">%s</td></tr>'
                 % (esc(co[c][0]), k, all_by[c], m["n"], esc(m["title"]), esc(t[:60])))
    p.append("</tbody></table>")
    return "".join(p)


def chrome_for(payload, n):
    """Every non-row-table block, pre-rendered by Python, one set per N.

    This is what keeps dashboard.js free of an SVG renderer, a panel renderer and
    a hero renderer, and it is why the page still shows all of Python's numbers
    when JS is switched off entirely.
    """
    index = payload["index"]
    wv = index["check"]["all"][str(n)]
    segs = CL.SEGMENT_ORDER
    counts = {s: wv["raw"][i] for i, s in enumerate(segs)}
    days = index["days"][max(0, len(index["days"]) - n):]
    per_day = {d: wv["bars"][i] for i, d in enumerate(index["days"])}
    note = ('柱高 = 该日仍是「同公司同标题最新一条」的行数（整份设计只有这一条去重规则），'
            'Σ 柱高 = 窗口去重后的 %d 行。窗口 = 近 %d 天，与判定用的固定 %d 天窗口无关。'
            % (wv["dedup"], n, index["w7_days"]))
    return {"hero": hero_html(index, wv, {"hero": index.get("_prev_hero")}),
            "trend": svg_trend(index["day"], per_day, days=days),
            "stack": svg_stack(counts),
            "legend": legend_html(counts),
            "note": note,
            "p2": panel2_html(payload, n, wv),
            "p3": panel3_html(payload, n)}


# ------------------------------------------------------------------ the shell
def controls_html():
    p = ['<div class="ctl">']
    p.append('<div class="ctlrow"><span class="ctllab">窗口</span>'
             '<div role="radiogroup" aria-label="窗口天数" id="nsel">')
    for k in view.N_CHOICES:
        on = "true" if k == view.N_DEFAULT else "false"
        p.append('<button type="button" role="radio" data-n="%d" aria-checked="%s"%s>'
                 '%d 天</button>' % (k, on, "" if k == view.N_DEFAULT else ' tabindex="-1"', k))
    p.append("</div></div>")
    labels = {"all": "全部", "new": "新增", "wm": "上一期未处理"}
    p.append('<div class="ctlrow"><span class="ctllab">显示</span>'
             '<div role="radiogroup" aria-label="显示范围" id="vsel">')
    for f in view.VIEWS:
        on = "true" if f == view.VIEWS[0] else "false"
        p.append('<button type="button" role="radio" data-v="%s" aria-checked="%s"%s>'
                 '%s</button>' % (f, on, "" if f == view.VIEWS[0] else ' tabindex="-1"',
                                  esc(labels.get(f, f))))
    p.append("</div></div>")
    p.append('<p class="sub">「显示」只改下面六个分段的行表与计数；'
             'hero、趋势图、堆叠条、图例、面板 ②′ 与 ③ 始终描述<b>整个窗口</b>'
             '（切到「新增」后二者相差 11-90 倍，所以它们的标题里带着「全部窗口」）。'
             '需要 JS 才能切换；JS 挂掉时页面显示的是生成时的默认档位。</p>')
    p.append("</div>")
    return "".join(p)


def segments_html(index, wv, carry_n):
    segs = CL.SEGMENT_ORDER
    p = []
    for g, s in enumerate(segs):
        m = SEG_META[s]
        icon = "⚠ " if s == "C" else ""
        p.append('<details id="seg-%s" data-gidx="%d" class="%s"%s>'
                 '<summary>%s%s <span class="segname">%s</span> '
                 '<span class="cnt">raw %d · cap2 %d</span>'
                 '<span class="sub">%s</span></summary>'
                 '<div class="body"></div></details>'
                 % (s, g, CLS_OF[s], " open" if wv["plan"][g] > 0 else "",
                    icon, m["n"], esc(m["title"]), wv["raw"][g], wv["cap2"][g],
                    esc(m["sub"])))
    p.append('<details id="seg-carry" class="segw"><summary>⑦ '
             '<span class="segname">上一期未处理</span> '
             '<span class="cnt">%d 行</span>'
             '<span class="sub">水位线区间 %s → %s 内落在 ①②④、而当前窗口盖不到的行</span>'
             '</summary><div class="body"></div></details>'
             % (carry_n, esc(index["prev_prev"] or "开始"),
                esc(index["prev_cutoff"] or "—")))
    return "".join(p)


def banner_html(index):
    h = index["health"]
    if not h["unenriched"]:
        return ""
    return ('<div class="banner">⚠ <b>%d 家未分层</b>'
            '（近 %d 天出现、但还没有富化档案）。它们按设计<b>不会</b>进中介面板，'
            '而是落在 ⑤ 长尾里等明早 07:30 的 <code>enrich_companies.py</code>。'
            '例：%s</div>'
            % (h["unenriched"], view.N_DEFAULT, esc("、".join(h["examples"]))))


def footer_html(index, overrides):
    p = ["<footer><b>口径与已知缺口</b><ul>"]
    p.append("<li><b>零丢弃</b>：六段 raw 相加 = 窗口去重后的行数 = Σ 柱高，"
             "没有任何一行被丢掉。页面每次渲染完都会自己对一遍账，"
             "对不上就在顶部亮红条，而不是安静少几行。</li>")
    p.append("<li><b>只有一条去重规则</b>：同公司同标题只留 <code>_recorded</code> 最新的一条，"
             "作用域是「收录日 ≤ 生成日」。趋势柱、分段、计数全部用它，没有第二条。</li>")
    p.append("<li><b>窗口 ≠ 水位线</b>：窗口（N 天）是你选的取景范围；"
             "「● 新」、「新增」/「上一期未处理」视图与 ⑦ 段由 "
             "<code>logs/last_report.json</code> 的水位线驱动。两者正交。</li>")
    p.append("<li><b>两个「7 天」不是一回事</b>：行表里的「近 %d 天」是判定刷屏用的固定窗口，"
             "不随你选的 N 变。</li>" % index["w7_days"])
    p.append("<li><b>不做已投 / 已忽略</b>：唯一的「看过」线索是链接的已访问颜色"
             "（浏览器状态，清缓存即失效）与水位线驱动的「● 新」。</li>")
    p.append("<li><b>没有历史 <code>&lt;day&gt;</code> 页面</b>：钉住的历史页会引用每天被重写的数据块，"
             "静默改判。要冻结快照就跑 "
             "<code>python -u dashboard.py --date YYYY-MM-DD --out 某目录</code>，"
             "那是一整套自包含的 bundle。</li>")
    p.append("<li>2023 年之后成立/分拆的公司（Cursor、Sierra AI、Harvey、Figure、"
             "Decagon、Solventum…）<b>任何模型任何批次都拿不到 tier</b>，永久落 ⑤ 段。"
             "唯一兜底是 <code>company_overrides.json</code>（当前 %d 条）。</li>"
             % len(overrides or {}))
    p.append("<li><code>prom</code> 是一次 LLM 采样并永久缓存；约 4.4%% 的公司"
             "其段内位置由那一次调用决定。override 可以覆盖 <code>prom</code>。</li>")
    p.append("<li><b>只追踪新增侧</b>：<code>date_recorded</code> 是首次收录时间，"
             "岗位下架不反映在这里。</li>")
    p.append("<li>中介占比是<b>下界</b>，理由见面板 ②′。</li>")
    p.append("</ul></footer>")
    return "".join(p)


def render_shell(tpl, ctx):
    """<!--SLOT:NAME--> -> ctx["NAME"]. No template engine, no expression syntax:
    the only thing that can go wrong is a missing key, and that raises."""
    def sub(m):
        return ctx[m.group(1)]
    out, n = re.subn(r"<!--SLOT:([A-Z0-9_]+)-->", sub, tpl)
    return out


def _read_web(name):
    with open(os.path.join(WEB_DIR, name), encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------- assembly
def build_bundle(day, rows, profiles, overrides, priority, state,
                 retain=view.RETAIN_DAYS):
    """-> (files, new_state, stats). `files` maps output file name to text; the
    caller writes them atomically. Nothing here touches the disk."""
    payload = view.build_payload(day, rows, profiles, overrides, priority, state,
                                 retain=retain)
    index = payload["index"]
    index["_prev_hero"] = state.get("hero") if isinstance(state, dict) else None
    segs = CL.SEGMENT_ORDER
    index["segl"] = ["%s %s" % (SEG_META[s]["n"], SEG_META[s]["title"]) for s in segs]
    index["carry_segs"] = [segs.index(s) for s in ("1a_t3", "1a_t2", "B1")]

    n0 = view.N_DEFAULT
    wv = index["check"]["all"][str(n0)]
    index["chrome"] = {str(n): chrome_for(payload, n) for n in view.N_CHOICES}
    del index["_prev_hero"]

    carry_head, carry_over = view.carry_seq(payload, n0)
    ch = index["chrome"][str(n0)]

    # the days the first screen needs: the default window plus the watermark days
    want = sorted(set(range(max(0, len(index["days"]) - n0), len(index["days"])))
                  | set(index["wm_days"]))
    scripts = "".join('<script src="%s"></script>' % index["chunk"][i]
                      for i in want if index["chunk"][i])

    sub = ('生成于 %s ·  默认窗口 近 %d 天 ·  去重后 %d 行 / %d 家公司 ·  '
           '水位线 %s' % (esc(index["generated"]), n0, wv["dedup"], len(index["co"]),
                          esc(index["prev_cutoff"] or "（首次生成）")))

    tpl = _read_web("shell.html")
    page = render_shell(tpl, {
        "DAY": esc(day),
        "SUB": sub,
        "CONTROLS": controls_html(),
        "HERO": ch["hero"],
        "BANNER": banner_html(index),
        "TREND": ch["trend"],
        "STACK": ch["stack"],
        "LEGEND": ch["legend"],
        "NOTE": esc(ch["note"]),
        "SEGMENTS": segments_html(index, wv, len(carry_head) + len(carry_over)),
        "PANEL2": ch["p2"],
        "PANEL3": ch["p3"],
        "FOOTER": footer_html(index, overrides),
        "SCRIPTS": scripts,
    })

    files = {"latest.html": page,
             "dashboard.css": _read_web("dashboard.css"),
             "dashboard.js": _read_web("dashboard.js"),
             "data-index.js": view.encode_index(index)}
    for d, cols in payload["days"].items():
        files["data-%s.js" % d] = view.encode_day(d, cols)

    cutoff_now = index["cutoff"]
    new_state = {"day": day, "cutoff": cutoff_now,
                 "prev_cutoff": index["prev_cutoff"],
                 "hero": wv["cap2"][segs.index("1a_t3")],
                 "generated_at": datetime.now().isoformat(timespec="seconds")}
    stats = {"raw": {s: wv["raw"][i] for i, s in enumerate(segs)},
             "cap2": {s: wv["cap2"][i] for i, s in enumerate(segs)},
             "visible": wv["open"],
             "total": wv["dedup"],
             "unenriched": index["health"]["unenriched"],
             "carry": len(carry_head) + len(carry_over),
             "by_n": {(f, n): index["check"][f][str(n)]
                      for f in view.VIEWS for n in view.N_CHOICES}}
    return files, new_state, stats


def build(day, rows, profiles, overrides, priority, state):
    """Compatibility shell: the signature tests/test_lane.py uses, unchanged."""
    files, new_state, stats = build_bundle(day, rows, profiles, overrides,
                                           priority, state)
    return files["latest.html"], new_state, stats


# ------------------------------------------------------------------ file I/O
def write_bundle(out_dir, files, prune_html=False):
    """Atomic writes only - the tree lives in OneDrive and a torn data block would
    take out every later run, not just this one.

    `prune_html` deletes leftover v1 per-day pages and is passed ONLY for the
    default output directory. `--out` is a path the caller chose; deleting a file
    there because its name happens to look like a date is not reversible, and the
    "no <day>.html" requirement is about logs/dashboard/ alone.
    """
    os.makedirs(out_dir, exist_ok=True)
    for name, text in files.items():
        path = os.path.join(out_dir, name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    removed = []
    for fn in sorted(os.listdir(out_dir)):
        if fn.startswith("data-") and fn.endswith(".js") and fn not in files:
            os.remove(os.path.join(out_dir, fn))
            removed.append(fn)
        elif prune_html and DAY_HTML_RE.match(fn):
            # v1 wrote one HTML page per day; those pages point at data blocks that
            # get rewritten every morning, so they would silently re-judge rows.
            os.remove(os.path.join(out_dir, fn))
            removed.append(fn)
    return removed


def main(argv=None):
    # This machine's console code page is 1252 and the summary below prints the
    # segment numerals as U+2460.. - without PYTHONIOENCODING that is a hard
    # UnicodeEncodeError AFTER the bundle has already been written, i.e. a healthy
    # run reporting failure. resolve_python.bat sets UTF-8 for the scheduled path;
    # this makes the hand-run path survive too. Never silence the exit code, only
    # the un-encodable characters.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="HTML dashboard over the collector CSVs")
    ap.add_argument("--date", default=None, metavar="YYYY-MM-DD")
    ap.add_argument("--out", default=None, metavar="DIR",
                    help="write the whole self-contained bundle into this directory")
    ap.add_argument("--retain", type=int, default=view.RETAIN_DAYS, metavar="N",
                    help="keep N days of data blocks (default %d)" % view.RETAIN_DAYS)
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

    files, new_state, stats = build_bundle(day, rows, profiles, overrides, priority,
                                           state, retain=args.retain)
    out_dir = args.out or OUT_DIR
    removed = write_bundle(out_dir, files, prune_html=(args.out is None))

    # Only advance the watermark on a real scheduled run, and only when something new
    # actually arrived - otherwise a second run in the same minute would collapse the
    # "unhandled from the last issue" interval to nothing.
    if (not args.no_watermark and not args.date and not args.out
            and new_state["cutoff"] != new_state["prev_cutoff"]):
        write_state(new_state)

    print("=" * 60)
    print("Dashboard - %s  (window %d days, view=all)" % (day, view.N_DEFAULT))
    print("=" * 60)
    for s in CL.SEGMENT_ORDER:
        m = SEG_META[s]
        print("  %s %-22s raw %4d   cap2 %4d" % (m["n"], m["title"], stats["raw"][s],
                                                 stats["cap2"][s]))
    print("  raw total %d == deduped rows in the window %d" % (sum(stats["raw"].values()),
                                                               stats["total"]))
    print("  first screen (1 + 4 + 2 filler): %d   [%d, %d]"
          % (stats["visible"],
             min(view.FLOOR, view.openable(stats["cap2"])), view.CEIL))
    print("  section 7 (unhandled from the last issue): %d" % stats["carry"])
    if stats["unenriched"]:
        print("  %d company/companies not yet enriched (they stay out of lane C)"
              % stats["unenriched"])
    blocks = sorted(k for k in files if k.startswith("data-") and k != "data-index.js")
    print("  %d files, %d day blocks, %.2f MB"
          % (len(files), len(blocks),
             sum(len(v.encode("utf-8")) for v in files.values()) / 1048576.0))
    if removed:
        print("  removed %d stale file(s): %s"
              % (len(removed), ", ".join(removed[:6])))
    print("\nWritten to %s" % os.path.join(out_dir, "latest.html"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
