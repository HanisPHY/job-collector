# -*- coding: utf-8 -*-
"""PROBE 8 - one file per natural day vs req2 5.5's five offset chunks.

req2 5.5 chunks by OFFSET from the generation day (d0 / d1_2 / d3_6 / d7_13 / d14_29).
Offsets shift every morning, so all five files are rewritten every day and no
historical <day>.html can ever reuse them. The alternative is one file per natural
day, named by an ABSOLUTE date, written once and never touched again.

The cost of the alternative is 30 dynamic <script> injections instead of 4.
That cost is what this probe measures, under file://, against the 5-chunk layout
and against one single 30-day file.
"""
import io
import json
import os
import re
import shutil
import subprocess
import tempfile

from _pm_base import banner

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

HTML = """<!doctype html><html><head><meta charset="utf-8"><title>chunks</title></head>
<body><pre id="out">PENDING</pre><script>
var R = {}, PLANS = __PLANS__;
function inject(files, cb){
  var t0 = performance.now(), n = 0, err = 0;
  files.forEach(function(f){
    var s = document.createElement('script');
    s.src = f;
    s.onload  = function(){ if (++n === files.length) cb(performance.now()-t0, err); };
    s.onerror = function(){ err++; if (++n === files.length) cb(performance.now()-t0, err); };
    document.head.appendChild(s);
  });
}
var names = Object.keys(PLANS), qi = 0;
function next(){
  if (qi >= names.length){
    R.total_rows = window.__ROWS || 0;
    document.getElementById('out').textContent = JSON.stringify(R);
    return;
  }
  var nm = names[qi++];
  inject(PLANS[nm], function(ms, err){
    R[nm] = {ms: +ms.toFixed(1), files: PLANS[nm].length, err: err,
             rows: window.__ROWS || 0};
    window.__ROWS = 0;
    next();
  });
}
next();
</script></body></html>
"""


def main():
    banner("PROBE 8  per-day chunk injection vs 5 offset chunks vs one big file")
    tmp = tempfile.mkdtemp(prefix="pmchunk_")
    ROWS_PER_DAY, NDAYS = 2000, 30
    # a row payload of the measured size (80-88 B/row in the E4 column encoding)
    def blob(nrows):
        return {"t": ["Software Engineer, New Grad %d" % i for i in range(nrows)],
                "l": ["/jobs/view/44562013%02d" % (i % 100) for i in range(nrows)],
                "c": [i % 1284 for i in range(nrows)],
                "g": [i % 6 for i in range(nrows)],
                "s": [i % 3 for i in range(nrows)],
                "d": [0] * nrows, "r": [800 + i % 900 for i in range(nrows)],
                "x": [0] * nrows, "lp": [0] * nrows}

    J = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    # (a) one file per natural day
    perday = []
    for i in range(NDAYS):
        n = "day-%02d.js" % i
        io.open(os.path.join(tmp, n), "w", encoding="utf-8").write(
            "window.__ROWS=(window.__ROWS||0)+%d;window.D%d=%s;" %
            (ROWS_PER_DAY, i, J(blob(ROWS_PER_DAY))))
        perday.append(n)
    # (b) req2 5.5's five offset chunks
    five = []
    for name, ndays in (("d0", 1), ("d1_2", 2), ("d3_6", 4), ("d7_13", 7), ("d14_29", 16)):
        n = "chunk-%s.js" % name
        io.open(os.path.join(tmp, n), "w", encoding="utf-8").write(
            "window.__ROWS=(window.__ROWS||0)+%d;window.C_%s=%s;" %
            (ROWS_PER_DAY * ndays, name, J(blob(ROWS_PER_DAY * ndays))))
        five.append(n)
    # (c) one 30-day file
    io.open(os.path.join(tmp, "all30.js"), "w", encoding="utf-8").write(
        "window.__ROWS=(window.__ROWS||0)+%d;window.ALL=%s;" %
        (ROWS_PER_DAY * NDAYS, J(blob(ROWS_PER_DAY * NDAYS))))

    sz = lambda f: os.path.getsize(os.path.join(tmp, f))
    print("per-day files : %d files, %.1f KB each, %.2f MB total"
          % (len(perday), sz(perday[0]) / 1024.0,
             sum(sz(f) for f in perday) / 2.0 ** 20))
    print("5 offset chunks: %s"
          % ", ".join("%s %.2f MB" % (f, sz(f) / 2.0 ** 20) for f in five))
    print("one big file  : %.2f MB" % (sz("all30.js") / 2.0 ** 20))
    print("\nOneDrive rewrite per morning:")
    print("   per-day layout : %.2f MB (today only)" % (sz(perday[0]) / 2.0 ** 20))
    print("   5-chunk layout : %.2f MB (all five shift by one day)"
          % (sum(sz(f) for f in five) / 2.0 ** 20))

    plans = {
        "perday_N1": perday[-1:],
        "perday_N7": perday[-7:],
        "perday_N30": perday,
        "five_chunks_N30": five,
        "one_big_file_N30": ["all30.js"],
    }
    io.open(os.path.join(tmp, "c.html"), "w", encoding="utf-8").write(
        HTML.replace("__PLANS__", J(plans)))
    if not os.path.exists(CHROME):
        print("no chrome")
        return
    url = "file:///" + os.path.join(tmp, "c.html").replace("\\", "/")
    prof = tempfile.mkdtemp(prefix="pmchunkprof_")
    try:
        p = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                            "--user-data-dir=" + prof, "--virtual-time-budget=40000",
                            "--dump-dom", url],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        dom = p.stdout.decode("utf-8", "replace")
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
    if not m:
        print("no result, dom %d B" % len(dom))
        return
    d = json.loads(m.group(1))
    print("\nchrome headless, file://, dynamic <script src> injection:")
    for k in ("perday_N1", "perday_N7", "perday_N30", "five_chunks_N30",
              "one_big_file_N30"):
        v = d.get(k, {})
        print("   %-18s %2d file(s)  %8.1f ms  errors %d  rows %d"
              % (k, v.get("files", 0), v.get("ms", -1), v.get("err", -1),
                 v.get("rows", -1)))
    print("\ntemp dir %s" % tmp)


if __name__ == "__main__":
    main()
