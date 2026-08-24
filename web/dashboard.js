/* Dashboard v2 - classic script, no modules, no build step, no network.
 *
 * What this file is allowed to do: filter by the chosen window, drop rows Python
 * already flagged as superseded, group, count, lay out DOM, and reconcile what it
 * produced against JOB_INDEX.check. What it must NEVER do is decide anything:
 * which segment a row belongs to, how prominent a company is, whether a company
 * is an intermediary - all of that arrives pre-computed in fixed-length arrays,
 * and fixture F23 greps this file to keep it that way.
 *
 * The segment containers are found through [data-gidx], never by name, so the
 * segment order has exactly one home (company_lane.SEGMENT_ORDER).
 */
(function () {
  "use strict";

  var IDX = window.JOB_INDEX;
  var DAY = (window.JOB_DAY = window.JOB_DAY || {});
  var CAP, SEGN, VIEWS, NCH;

  var reconEl = document.getElementById("recon");
  var problems = {};          /* key -> message; rendered as one red banner */
  var lostDays = [];

  var gen = 0;                /* generation counter; every rAF batch checks it */
  var cur = null;             /* the current compute() result */
  var segs = [];              /* per-segment DOM bookkeeping */
  var carry = null;
  var busyEls = [];
  var loading = {};

  var st = {n: 0, view: ""};
  var PC = ["", -1], PP = ["", -1], HAS_WM = false;

  /* ------------------------------------------------------------ tiny helpers */
  function esc(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function stampOf(s) {
    /* "YYYY-MM-DD HH:MM" -> ["YYYY-MM-DD", HH*100+MM]; "" -> ["", -1] */
    s = String(s || "");
    if (s.length < 16) { return ["", -1]; }
    return [s.slice(0, 10), (+s.slice(11, 13)) * 100 + (+s.slice(14, 16))];
  }

  function after(d, r, k) {          /* (d, r) > k */
    if (d !== k[0]) { return d > k[0]; }
    return r > k[1];
  }

  /* Order-sensitive 32-bit checksum. Math.imul is an exact 32-bit multiply and
   * ">>> 0" makes it unsigned, so this is bit-for-bit view.seq_hash in Python.
   * F29 holds the two together; L2 check 6 is what it buys. */
  function mix(h, v) { h = (h ^ (v >>> 0)) >>> 0; return Math.imul(h, 16777619) >>> 0; }

  function seqHash(pairs) {
    var h = 2166136261 >>> 0;
    for (var k = 0; k < pairs.length; k++) {
      h = mix(h, pairs[k][0]);
      h = mix(h, pairs[k][1]);
    }
    return mix(h, pairs.length);
  }

  /* a, b = [rank, day index, r, title, row index].
   * The DAY INDEX MUST BE COMPARED FIRST: r is HH*100+MM and carries no day, so
   * comparing r first sorts "yesterday 03:22" above "today 02:22". The row index
   * is the final deterministic tie-break - without it two implementations can
   * disagree on ties and nothing would notice. */
  function cmpRow(a, b) {
    if (a[1] !== b[1]) { return b[1] - a[1]; }
    if (a[2] !== b[2]) { return b[2] - a[2]; }
    if (a[3] !== b[3]) { return a[3] < b[3] ? 1 : -1; }
    return b[4] - a[4];
  }

  function sameArr(a, b) {
    if (!a || !b || a.length !== b.length) { return false; }
    for (var i = 0; i < a.length; i++) { if (a[i] !== b[i]) { return false; } }
    return true;
  }

  function samePairs(a, b) {
    if (!a || !b || a.length !== b.length) { return false; }
    for (var i = 0; i < a.length; i++) {
      if (a[i][0] !== b[i][0] || a[i][1] !== b[i][1]) { return false; }
    }
    return true;
  }

  function coords(list) {
    var out = [], i;
    for (i = 0; i < list.length; i++) { out.push([list[i][1], list[i][4]]); }
    return out;
  }

  /* ------------------------------------------------------- the red banner */
  function fail(key, msg) { problems[key] = msg; paintRecon(); }
  function pass(key) { if (problems[key]) { delete problems[key]; paintRecon(); } }

  function paintRecon() {
    if (!reconEl) { return; }
    var keys = Object.keys(problems);
    if (!keys.length) { reconEl.hidden = true; reconEl.innerHTML = ""; return; }
    keys.sort();
    var h = "<b>⚠ 对账失败：页面显示的行可能少于、多于或不同于 Python 算出来的那些。"
          + "别拿这一屏做决定。</b><ul>";
    for (var i = 0; i < keys.length; i++) { h += "<li>" + esc(problems[keys[i]]) + "</li>"; }
    reconEl.innerHTML = h + "</ul>";
    reconEl.hidden = false;
  }

  /* --------------------------------------------------------------- compute */
  function compute(n, view) {
    var days = IDX.days, nd = days.length, lo = Math.max(0, nd - n);
    var pc = PC, pp = PP, hasWm = HAS_WM;
    var isNew = (view === VIEWS[1]), isWm = (view === VIEWS[2]);
    var raw = [], bars = [], bucket = [], g, i, di;

    for (g = 0; g < SEGN; g++) { raw.push(0); bucket.push({}); }
    for (i = 0; i < nd; i++) { bars.push(0); }

    for (di = lo; di < nd; di++) {
      var col = DAY[days[di]];
      if (!col) { continue; }
      var xs = col.x, gs = col.g, cs = col.c, rs = col.r, ts = col.t;
      var d = days[di];
      for (i = 0; i < xs.length; i++) {
        if (xs[i]) { continue; }                       /* THE dedup rule, 1 bit */
        var r = rs[i];
        if (isNew) {
          if (!hasWm || !after(d, r, pc)) { continue; }
        } else if (isWm) {
          if (!hasWm || !after(d, r, pp) || after(d, r, pc)) { continue; }
        }
        g = gs[i];
        raw[g]++;
        bars[di]++;
        var m = bucket[g], c = cs[i];
        (m[c] || (m[c] = [])).push([IDX.o[c], di, r, ts[i], i, c]);
      }
    }

    var cap2 = [], heads = [], overs = [];
    for (g = 0; g < SEGN; g++) {
      var m2 = bucket[g], keys = [], k;
      for (k in m2) { if (Object.prototype.hasOwnProperty.call(m2, k)) { keys.push(+k); } }
      keys.sort(function (a, b) { return (IDX.o[a] - IDX.o[b]) || (a - b); });
      var h = [], ov = [];
      for (i = 0; i < keys.length; i++) {
        var arr = m2[keys[i]];
        arr.sort(cmpRow);
        for (k = 0; k < arr.length; k++) {
          if (k < CAP) { h.push(arr[k]); } else { ov.push(arr[k]); }
        }
      }
      heads.push(h); overs.push(ov); cap2.push(h.length);
    }

    var dedup = 0;
    for (g = 0; g < SEGN; g++) { dedup += raw[g]; }
    return {n: n, view: view, raw: raw, cap2: cap2, bars: bars, dedup: dedup,
            heads: heads, overs: overs};
  }

  function computeCarry(n) {
    /* Section 7: what the LAST issue put in front of the reader and the current
     * window does not cover. One rule, no branch on N. */
    var days = IDX.days, nd = days.length, lo = Math.max(0, nd - n);
    var pc = PC, pp = PP;
    if (!HAS_WM) { return {head: [], over: []}; }
    var want = IDX.carry_segs || [], bucket = {}, di, i;
    for (di = 0; di < lo; di++) {
      var col = DAY[days[di]];
      if (!col) { continue; }
      var d = days[di];
      for (i = 0; i < col.x.length; i++) {
        if (col.x[i] || want.indexOf(col.g[i]) < 0) { continue; }
        var r = col.r[i];
        if (!after(d, r, pp) || after(d, r, pc)) { continue; }
        var c = col.c[i];
        (bucket[c] || (bucket[c] = [])).push([IDX.o[c], di, r, col.t[i], i, c]);
      }
    }
    var keys = [], k;
    for (k in bucket) { if (Object.prototype.hasOwnProperty.call(bucket, k)) { keys.push(+k); } }
    keys.sort(function (a, b) { return (IDX.o[a] - IDX.o[b]) || (a - b); });
    var head = [], over = [];
    for (i = 0; i < keys.length; i++) {
      var arr = bucket[keys[i]];
      arr.sort(cmpRow);
      for (k = 0; k < arr.length; k++) {
        if (k < CAP) { head.push(arr[k]); } else { over.push(arr[k]); }
      }
    }
    return {head: head, over: over};
  }

  /* ---------------------------------------------------------------- markup */
  function headHtml(showDate, showSeg) {
    var h = "<thead><tr><th>公司</th><th>岗位</th>";
    if (showDate) { h += "<th>日期</th>"; }
    h += "<th>来源</th>";
    if (showSeg) { h += "<th>段</th>"; }
    h += "<th>近 " + IDX.w7_days + " 天</th><th>信号</th></tr></thead>";
    return h;
  }

  function rowHtml(row, showDate, showSeg) {
    var di = row[1], i = row[4], c = row[5];
    var col = DAY[IDX.days[di]];
    var info = IDX.co[c] || ["", 0, 0, 0, 0, 0, 0];
    var s = col.s[i];
    var lp = col.lp[i];
    var url = lp < 0 ? col.l[i] : (IDX.lpre[lp] + col.l[i]);
    var fresh = HAS_WM && after(IDX.days[di], col.r[i], PC);
    var name = esc(info[0]);
    var lvl = info[1];
    var out = '<tr data-k="' + di + "," + i + '">'
      + '<td class="co"><span class="t t' + lvl + '">T' + lvl + "</span> " + name + "</td>";
    var t = esc(col.t[i]);
    out += '<td class="ti">'
      + (url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + t + "</a>" : t)
      + (fresh ? ' <span class="new" title="上一期之后新增">● 新</span>' : "") + "</td>";
    if (showDate) { out += '<td class="dt">' + esc(IDX.days[di]) + "</td>"; }
    out += '<td class="sm">' + esc(IDX.srcs[s] || "") + "</td>";
    if (showSeg) { out += '<td class="sm">' + esc(IDX.segl[col.g[i]] || "") + "</td>"; }
    out += '<td class="num">' + info[3] + "</td>";
    /* a lookup, not a decision: index 5 is the company's signal, index 6 is the
     * signal for a row that came off the company's own board */
    out += '<td class="sm sig">' + esc(IDX.sigs[info[s === 0 ? 5 : 6]] || "") + "</td></tr>";
    return out;
  }

  function rowsHtml(rows, a, b, showDate, showSeg) {
    var out = [];
    for (var i = a; i < b; i++) { out.push(rowHtml(rows[i], showDate, showSeg)); }
    return out.join("");
  }

  function tableShell(showDate, showSeg) {
    return "<table>" + headHtml(showDate, showSeg) + "<tbody></tbody></table>";
  }

  function emptyP() { return '<p class="empty">（空）</p>'; }

  /* Fill one <tbody>. Above 2000 rows it goes through requestAnimationFrame in
   * 500-row batches, and every batch re-checks the generation counter: without
   * that, a batch left over from the previous N keeps appending into the new
   * container and produces duplicated or out-of-order rows - exactly the shape
   * the per-segment checksum exists to catch. */
  function fill(tb, rows, showDate, showSeg, done) {
    var myGen = gen;
    if (rows.length <= 2000) {
      tb.innerHTML = rowsHtml(rows, 0, rows.length, showDate, showSeg);
      if (done) { done(); }
      return;
    }
    tb.innerHTML = "";
    var k = 0;
    (function step() {
      if (myGen !== gen) { return; }
      var end = Math.min(rows.length, k + 500);
      tb.insertAdjacentHTML("beforeend", rowsHtml(rows, k, end, showDate, showSeg));
      k = end;
      if (k < rows.length) { window.requestAnimationFrame(step); }
      else if (done) { done(); }
    }());
  }

  function seqOf(tb) {
    var out = [];
    if (!tb) { return out; }
    var trs = tb.children;
    for (var i = 0; i < trs.length; i++) {
      var k = trs[i].getAttribute("data-k");
      if (!k) { continue; }
      var p = k.split(",");
      out.push([+p[0], +p[1]]);
    }
    return out;
  }

  /* --------------------------------------------------------- segment render */
  function clearSeg(rec) {
    rec.rendered = false;
    rec.moreDone = false;
    rec.body.innerHTML = "";
    rec.main = null; rec.rest = null; rec.more = null;
  }

  function renderSeg(g) {
    var rec = segs[g];
    if (!rec || rec.rendered || !cur) { return; }
    var chk = currentCheck();
    var head = cur.heads[g], over = cur.overs[g];
    var limit = chk ? chk.plan[g] : 0;
    if (!limit || limit > head.length) { limit = head.length; }
    var showDate = st.n > 1;
    var html = head.length ? tableShell(showDate, false) : emptyP();
    var rest = head.slice(limit);
    if (rest.length) {
      html += '<details class="rest"><summary>还有 ' + rest.length
        + ' 条 <span class="cnt">（知名度更靠后，先看上面的）</span></summary>'
        + '<div class="body">' + tableShell(showDate, false) + "</div></details>";
    }
    if (over.length) {
      html += '<details class="more"><summary>+' + over.length
        + ' more <span class="cnt">（同公司的第 ' + (CAP + 1)
        + " 条及以后）</span></summary>"
        + '<div class="body">' + tableShell(showDate, false) + "</div></details>";
    }
    rec.body.innerHTML = html;
    rec.rendered = true;

    var tables = rec.body.querySelectorAll("table tbody");
    var ti = 0;
    rec.main = head.length ? tables[ti++] : null;
    rec.rest = rest.length ? tables[ti++] : null;
    rec.more = over.length ? tables[ti++] : null;

    var pending = 0, myGen = gen;
    function done() {
      pending--;
      if (pending <= 0 && myGen === gen) { checkSeg(g); }
    }
    if (rec.main) { pending++; fill(rec.main, head.slice(0, limit), showDate, false, done); }
    if (rec.rest) { pending++; fill(rec.rest, rest, showDate, false, done); }
    if (!pending) { checkSeg(g); }

    if (rec.more) {
      var moreEl = rec.body.querySelector("details.more");
      moreEl.addEventListener("toggle", function () {
        if (!moreEl.open || rec.moreDone) { return; }
        rec.moreDone = true;
        var mg = gen;
        fill(rec.more, cur.overs[g], showDate, false, function () {
          if (mg === gen) { checkOver(g); }
        });
      });
    }
  }

  function ensureSeg(el) {
    var g = +el.getAttribute("data-gidx");
    if (segs[g] && !segs[g].rendered) { renderSeg(g); }
  }

  function renderCarry() {
    if (!carry) { return; }
    var res = computeCarry(st.n);
    carry.cnt.textContent = (res.head.length + res.over.length) + " 行";
    carry.rendered = false;
    carry.data = res;
    carry.body.innerHTML = "";
    if (carry.el.open) { fillCarry(); }
  }

  function fillCarry() {
    if (!carry || carry.rendered) { return; }
    carry.rendered = true;
    var res = carry.data || {head: [], over: []};
    if (!HAS_WM) {
      carry.body.innerHTML = '<p class="empty">还没有上一期水位线（这是第一次生成）。'
        + "下一次运行开始，这里会列出上一期摆在你面前、可能还没处理的 ①②④ 行。</p>";
      return;
    }
    if (!res.head.length && !res.over.length) {
      carry.body.innerHTML = '<p class="empty">上一期的行都落在当前窗口内了 —— '
        + "用上面的「上一期未处理」视图看它们。</p>";
      return;
    }
    var html = tableShell(true, true);
    if (res.over.length) {
      html += '<details class="more"><summary>+' + res.over.length
        + " more</summary><div class=\"body\">" + tableShell(true, true) + "</div></details>";
    }
    carry.body.innerHTML = html;
    var tbs = carry.body.querySelectorAll("table tbody");
    fill(tbs[0], res.head, true, true, null);
    if (res.over.length) {
      var mEl = carry.body.querySelector("details.more");
      mEl.addEventListener("toggle", function () {
        if (mEl.open && !mEl.dataset.done) {
          mEl.dataset.done = "1";
          fill(tbs[1], res.over, true, true, null);
        }
      });
    }
  }

  /* ----------------------------------------------------------- reconciling */
  function currentCheck() {
    var byView = IDX.check[st.view];
    return byView ? byView[String(st.n)] : null;
  }

  function reconcileCounts() {
    var chk = currentCheck();
    if (!chk) { fail("check", "JOB_INDEX.check 缺少当前档位，无法对账"); return; }
    pass("check");

    /* 1 - I1, the window edition */
    var s = 0;
    for (var g = 0; g < SEGN; g++) { s += cur.raw[g]; }
    if (s !== cur.dedup) { fail("i1", "各段 raw 之和 " + s + " ≠ 去重后 " + cur.dedup); }
    else { pass("i1"); }

    /* 2 - the counts this file produced against the ones Python shipped */
    if (chk.dedup !== cur.dedup) {
      fail("dedup", "去重后行数 " + cur.dedup + " ≠ Python 的 " + chk.dedup);
    } else { pass("dedup"); }
    if (!sameArr(chk.raw, cur.raw)) {
      fail("raw", "分段 raw 计数与 Python 不符：" + cur.raw.join("/") + " vs " + chk.raw.join("/"));
    } else { pass("raw"); }
    if (!sameArr(chk.cap2, cur.cap2)) {
      fail("cap2", "分段 cap2 计数与 Python 不符：" + cur.cap2.join("/") + " vs " + chk.cap2.join("/"));
    } else { pass("cap2"); }
    if (!sameArr(chk.bars, cur.bars)) {
      fail("bars", "趋势柱高与 Python 不符");
    } else { pass("bars"); }

    /* 4 - a data block that never loaded, or an old one, shows up here */
    var bad = [];
    for (var i = 0; i < IDX.days.length; i++) {
      var blk = DAY[IDX.days[i]];
      if (!blk) { continue; }
      if (blk.n !== IDX.nrows[i]) { bad.push(IDX.days[i]); }
    }
    if (bad.length) { fail("blocks", "数据块行数与索引不符：" + bad.join("、")); }
    else { pass("blocks"); }
    if (lostDays.length) {
      fail("load", "这些天的数据块没能加载，页面少行：" + lostDays.join("、"));
    }

    /* the days the window needs but nothing was loaded for */
    var miss = [];
    var lo = Math.max(0, IDX.days.length - st.n);
    for (i = lo; i < IDX.days.length; i++) {
      if (IDX.chunk[i] && !DAY[IDX.days[i]]) { miss.push(IDX.days[i]); }
    }
    if (miss.length) { fail("miss", "窗口需要但尚未加载：" + miss.join("、")); }
    else { pass("miss"); }
  }

  function checkFirstScreen() {
    var chk = currentCheck();
    if (!chk) { return; }
    var seq = [];
    for (var g = 0; g < SEGN; g++) {
      if (chk.plan[g] > 0 && segs[g] && segs[g].main) {
        seq = seq.concat(seqOf(segs[g].main));
      }
    }
    if (!samePairs(seq, chk.head)) {
      fail("head", "首屏渲染出的 " + seq.length + " 行与 Python 给的首屏序列不符");
    } else { pass("head"); }
  }

  function checkSeg(g) {
    var chk = currentCheck();
    var rec = segs[g];
    if (!chk || !rec) { return; }
    var seq = seqOf(rec.main).concat(seqOf(rec.rest));
    var label = rec.label || ("第 " + (g + 1) + " 段");

    /* 5 - localisation: which end of the segment went wrong */
    var a = chk.anchors[String(g)];
    if (a) {
      var mine = seq.length ? [seq[0], seq[Math.floor(seq.length / 2)], seq[seq.length - 1]] : [];
      if (!samePairs(mine, a)) {
        fail("anch" + g, label + "：首/中/末三行坐标与 Python 不符");
      } else { pass("anch" + g); }
    }
    /* 6 - 100% coverage: every row, in order, no drops, no repeats */
    if (seqHash(seq) !== chk.hsum[String(g)]) {
      fail("hsum" + g, label + " 段序列校验和不符（共 " + seq.length
        + " 行；行序、漏行或重复行都会命中这一条）");
    } else { pass("hsum" + g); }
  }

  function checkOver(g) {
    var chk = currentCheck();
    var rec = segs[g];
    if (!chk || !rec || !rec.more) { return; }
    var seq = seqOf(rec.more);
    var label = rec.label || ("第 " + (g + 1) + " 段");
    if (seqHash(seq) !== chk.osum[String(g)]) {
      fail("osum" + g, label + "「+N more」序列校验和不符（共 " + seq.length + " 行）");
    } else { pass("osum" + g); }
  }

  /* -------------------------------------------------------------- chrome */
  function applyChrome(n) {
    var c = (IDX.chrome || {})[String(n)];
    if (!c) { return; }
    var map = {"ch-hero": "hero", "ch-trend": "trend", "ch-stack": "stack",
               "ch-legend": "legend", "ch-note": "note", "ch-p2": "p2", "ch-p3": "p3"};
    for (var id in map) {
      if (!Object.prototype.hasOwnProperty.call(map, id)) { continue; }
      var el = document.getElementById(id);
      if (el && typeof c[map[id]] === "string") { el.innerHTML = c[map[id]]; }
    }
  }

  function updateSummaries() {
    var chk = currentCheck();
    if (!chk) { return; }
    for (var g = 0; g < SEGN; g++) {
      if (segs[g] && segs[g].cnt) {
        segs[g].cnt.textContent = "raw " + chk.raw[g] + " · cap2 " + chk.cap2[g];
      }
    }
  }

  /* ------------------------------------------------------- chunk loading */
  function neededDays(n) {
    var out = [], nd = IDX.days.length, lo = Math.max(0, nd - n), i;
    for (i = lo; i < nd; i++) { out.push(i); }
    /* section 7 reads days OUTSIDE the window, so the watermark days are always
     * part of the set - forget this and section 7 quietly loses rows */
    for (i = 0; i < IDX.wm_days.length; i++) {
      if (out.indexOf(IDX.wm_days[i]) < 0) { out.push(IDX.wm_days[i]); }
    }
    var todo = [];
    for (i = 0; i < out.length; i++) {
      var k = out[i];
      if (IDX.chunk[k] && !DAY[IDX.days[k]] && !loading[k]) { todo.push(k); }
    }
    return todo;
  }

  function setBusy(on) {
    for (var i = 0; i < busyEls.length; i++) {
      if (on) { busyEls[i].setAttribute("aria-busy", "true"); }
      else { busyEls[i].removeAttribute("aria-busy"); }
    }
  }

  function loadDays(list, cb) {
    if (!list.length) { cb(); return; }
    setBusy(true);
    var left = list.length;
    function one() { left--; if (left <= 0) { setBusy(false); cb(); } }
    for (var i = 0; i < list.length; i++) {
      (function (k) {
        loading[k] = 1;
        var sc = document.createElement("script");
        sc.async = false;
        sc.onload = function () { one(); };
        sc.onerror = function () {
          if (lostDays.indexOf(IDX.days[k]) < 0) { lostDays.push(IDX.days[k]); }
          one();
        };
        sc.src = IDX.chunk[k];
        document.head.appendChild(sc);
      }(list[i]));
    }
  }

  /* ---------------------------------------------------------------- render */
  function renderAll() {
    gen++;
    cur = compute(st.n, st.view);
    reconcileCounts();
    applyChrome(st.n);
    updateSummaries();
    var chk = currentCheck();
    for (var g = 0; g < SEGN; g++) {
      var rec = segs[g];
      if (!rec) { continue; }
      clearSeg(rec);
      if (chk && chk.plan[g] > 0) { rec.el.open = true; }
      if (rec.el.open) { renderSeg(g); }
    }
    checkFirstScreen();
    renderCarry();
  }

  /* keep the reader where they were: this runs AFTER reconciliation on purpose,
   * so a scroll that throws can never be mistaken for a reconciliation failure */
  function snapshot() {
    /* the topmost <details> still at or above the fold; when the reader is
     * parked on something that is not a <details> at all - panel 2' for
     * instance - there is no anchor and the absolute scrollTop is the fallback */
    var best = null, all = document.querySelectorAll("details[id]");
    for (var i = 0; i < all.length; i++) {
      var t = all[i].getBoundingClientRect().top;
      if (t <= 8) { best = all[i]; } else { break; }
    }
    var se = document.scrollingElement || document.documentElement;
    return {el: best, top: best ? best.getBoundingClientRect().top : 0,
            abs: se ? se.scrollTop : 0};
  }

  function restore(snap) {
    try {
      if (snap.el && snap.el.isConnected) {
        window.scrollTo(0, snap.el.offsetTop - snap.top);
      } else {
        window.scrollTo(0, snap.abs);
      }
    } catch (e) { /* a failed scroll must never colour the reconciliation */ }
  }

  function setWindow(n) {
    if (n === st.n) { return; }
    st.n = n;
    save();
    paintRadios();
    var snap = snapshot();
    loadDays(neededDays(n), function () { renderAll(); restore(snap); });
  }

  function setView(v) {
    if (v === st.view) { return; }
    st.view = v;
    save();
    paintRadios();
    var snap = snapshot();
    renderAll();
    restore(snap);
  }

  /* ------------------------------------------------------------- controls */
  function paintRadios() {
    var i, b, bs = document.querySelectorAll('#nsel [role="radio"]');
    for (i = 0; i < bs.length; i++) {
      b = bs[i];
      var on = (+b.getAttribute("data-n") === st.n);
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.tabIndex = on ? 0 : -1;
    }
    bs = document.querySelectorAll('#vsel [role="radio"]');
    for (i = 0; i < bs.length; i++) {
      b = bs[i];
      var on2 = (b.getAttribute("data-v") === st.view);
      b.setAttribute("aria-checked", on2 ? "true" : "false");
      b.tabIndex = on2 ? 0 : -1;
    }
  }

  function wireGroup(id, attr, apply) {
    var box = document.getElementById(id);
    if (!box) { return; }
    box.addEventListener("click", function (e) {
      var b = e.target.closest('[role="radio"]');
      if (b) { apply(b.getAttribute(attr)); }
    });
    box.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft"
          && e.key !== "ArrowDown" && e.key !== "ArrowUp") { return; }
      var bs = box.querySelectorAll('[role="radio"]');
      var at = -1, i;
      for (i = 0; i < bs.length; i++) { if (bs[i] === document.activeElement) { at = i; } }
      if (at < 0) { return; }
      e.preventDefault();
      var step = (e.key === "ArrowRight" || e.key === "ArrowDown") ? 1 : -1;
      var nx = bs[(at + step + bs.length) % bs.length];
      apply(nx.getAttribute(attr));
      nx.focus();
    });
  }

  function save() {
    try {
      window.localStorage.setItem("dash.n", String(st.n));
      window.localStorage.setItem("dash.view", st.view);
    } catch (e) { /* file:// with site data blocked - the page still works */ }
  }

  function load() {
    var n = IDX.n_default, v = VIEWS[0];
    try {
      var sn = +window.localStorage.getItem("dash.n");
      if (NCH.indexOf(sn) >= 0) { n = sn; }
      var sv = window.localStorage.getItem("dash.view");
      if (VIEWS.indexOf(sv) >= 0) { v = sv; }
    } catch (e) { /* no stored preference; the defaults are always valid */ }
    st.n = n; st.view = v;
  }

  /* ------------------------------------------------------- anchors (R3/B7) */
  function openSegment(id) {
    var el = null;
    try { el = document.getElementById(String(id).replace(/^#/, "")); } catch (e) { el = null; }
    if (!el || el.tagName !== "DETAILS") { return; }
    el.open = true;
    if (el.hasAttribute("data-gidx")) { ensureSeg(el); }
    else if (carry && el === carry.el) { fillCarry(); }
    el.setAttribute("tabindex", "-1");
    try { el.focus({preventScroll: true}); } catch (e2) { try { el.focus(); } catch (e3) {} }
    try { el.scrollIntoView({block: "start"}); } catch (e4) {}
  }

  /* Clicking the SAME anchor twice fires hashchange only once (measured in
   * Chrome 151 under file://), so the click path cannot go through hashchange.
   * preventDefault is deliberately NOT called: the hash still updates and
   * back/forward keep working. */
  function wireAnchors() {
    document.addEventListener("click", function (e) {
      var a = e.target.closest ? e.target.closest('a[href^="#seg-"]') : null;
      if (!a) {
        var t = e.target;
        while (t && t !== document) {
          if (t.getAttribute && (t.getAttribute("href") || "").indexOf("#seg-") === 0) { a = t; break; }
          t = t.parentNode;
        }
      }
      if (!a) { return; }
      openSegment(a.getAttribute("href"));
    }, false);
    window.addEventListener("hashchange", function () {
      if (location.hash.indexOf("#seg-") === 0) { openSegment(location.hash); }
    });
  }

  /* ------------------------------------------------------------ selfcheck */
  function selfcheck() {
    var pre = document.getElementById("selfcheck");
    var all = [], i;
    for (i = 0; i < IDX.days.length; i++) {
      if (IDX.chunk[i] && !DAY[IDX.days[i]] && !loading[i]) { all.push(i); }
    }
    loadDays(all, function () {
      var out = {};
      for (var vi = 0; vi < VIEWS.length; vi++) {
        var f = VIEWS[vi];
        out[f] = {};
        for (var ni = 0; ni < NCH.length; ni++) {
          var n = NCH[ni];
          var chk = (IDX.check[f] || {})[String(n)];
          var c = compute(n, f);
          var why = [];
          if (!chk) { why.push("no check"); }
          else {
            var s = 0, g;
            for (g = 0; g < SEGN; g++) { s += c.raw[g]; }
            if (s !== c.dedup) { why.push("I1"); }
            if (chk.dedup !== c.dedup) { why.push("dedup"); }
            if (!sameArr(chk.raw, c.raw)) { why.push("raw"); }
            if (!sameArr(chk.cap2, c.cap2)) { why.push("cap2"); }
            if (!sameArr(chk.bars, c.bars)) { why.push("bars"); }
            var seq = [];
            for (g = 0; g < SEGN; g++) {
              if (chk.plan[g] > 0) { seq = seq.concat(coords(c.heads[g]).slice(0, chk.plan[g])); }
            }
            if (!samePairs(seq, chk.head)) { why.push("head"); }
            for (g = 0; g < SEGN; g++) {
              if (seqHash(coords(c.heads[g])) !== chk.hsum[String(g)]) { why.push("hsum" + g); }
              if (seqHash(coords(c.overs[g])) !== chk.osum[String(g)]) { why.push("osum" + g); }
              var a = chk.anchors[String(g)];
              var cs = coords(c.heads[g]);
              if (a) {
                var mine = cs.length ? [cs[0], cs[Math.floor(cs.length / 2)], cs[cs.length - 1]] : [];
                if (!samePairs(mine, a)) { why.push("anchors" + g); }
              }
            }
          }
          out[f][String(n)] = {ok: why.length === 0, dedup: c.dedup, why: why};
        }
      }
      var bad = 0;
      for (var f2 in out) {
        if (!Object.prototype.hasOwnProperty.call(out, f2)) { continue; }
        for (var k in out[f2]) {
          if (Object.prototype.hasOwnProperty.call(out[f2], k) && !out[f2][k].ok) { bad++; }
        }
      }
      if (pre) {
        pre.hidden = false;
        pre.textContent = "SELFCHECK " + (bad ? "FAILED " + bad : "ok")
          + " (" + (VIEWS.length * NCH.length) + " cells)\n"
          + JSON.stringify(out, null, 1);
      }
      if (bad) { fail("selfcheck", "#selfcheck: " + bad + " 个组合对账失败"); }
    });
  }

  /* ------------------------------------------------------------------ boot */
  function boot() {
    if (!IDX || typeof IDX !== "object") {
      if (reconEl) {
        reconEl.hidden = false;
        reconEl.innerHTML = "<b>⚠ 数据索引没有加载</b>：data-index.js 不在同一个目录里，"
          + "或者被浏览器拦住了。页面上的数字是生成时的静态快照。";
      }
      return;
    }
    if (IDX.v !== 2) {
      if (reconEl) {
        reconEl.hidden = false;
        reconEl.innerHTML = "<b>⚠ 数据格式版本不匹配</b>（索引 v=" + esc(IDX.v)
          + "，本页需要 v=2）。停止渲染，以免显示错的行。";
      }
      return;
    }
    CAP = IDX.cap || 2;
    PC = stampOf(IDX.prev_cutoff);
    PP = stampOf(IDX.prev_prev);
    HAS_WM = !!(IDX.prev_cutoff && String(IDX.prev_cutoff).length);
    VIEWS = IDX.views;
    NCH = IDX.n_choices;
    SEGN = IDX.check[VIEWS[0]][String(IDX.n_default)].raw.length;

    var els = document.querySelectorAll("[data-gidx]");
    for (var i = 0; i < els.length; i++) {
      var el = els[i], g = +el.getAttribute("data-gidx");
      segs[g] = {el: el, body: el.querySelector(".body"),
                 cnt: el.querySelector(".cnt"),
                 label: (el.querySelector(".segname") || {}).textContent || "",
                 rendered: false, moreDone: false};
      (function (node) {
        node.addEventListener("toggle", function () { if (node.open) { ensureSeg(node); } });
      }(el));
    }
    var cEl = document.getElementById("seg-carry");
    if (cEl) {
      carry = {el: cEl, body: cEl.querySelector(".body"), cnt: cEl.querySelector(".cnt"),
               rendered: false};
      cEl.addEventListener("toggle", function () { if (cEl.open) { fillCarry(); } });
    }
    busyEls = [];
    var nb = document.getElementById("nsel"), vb = document.getElementById("vsel");
    if (nb) { busyEls.push(nb); }
    if (vb) { busyEls.push(vb); }

    load();
    /* a one-off "#n=7" is honoured, then the hash goes back to being anchors only:
     * leaving N in the hash means one click on the stacked bar wipes it out */
    var m = /^#n=(\d+)$/.exec(location.hash || "");
    if (m && NCH.indexOf(+m[1]) >= 0) {
      st.n = +m[1];
      save();
      try { history.replaceState(null, "", location.pathname + location.search); }
      catch (e) { location.hash = ""; }
    }
    paintRadios();
    wireGroup("nsel", "data-n", function (v) { setWindow(+v); });
    wireGroup("vsel", "data-v", function (v) { setView(v); });
    wireAnchors();

    var wantSelf = (location.hash === "#selfcheck");
    loadDays(neededDays(st.n), function () {
      if (wantSelf) { selfcheck(); return; }
      renderAll();
      if (location.hash.indexOf("#seg-") === 0) { openSegment(location.hash); }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else { boot(); }
}());
