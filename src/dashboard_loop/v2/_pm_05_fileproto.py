# -*- coding: utf-8 -*-
"""PROBE 5 - the file:// capability table of req2 section 6, actually executed.

req2 section 6 asserts what works under file:// from reasoning. This runs it in the
two browsers that are installed on this machine and prints what really happened.
Everything is written to a throwaway temp dir - nothing lands in the repo tree.

Headless is not the same event as a human double-click (QA still has to do that one),
but it is the same URL scheme, the same opaque origin and the same CORS rules.
"""
import io
import json
import os
import re
import shutil
import subprocess
import tempfile

from _pm_base import banner

BROWSERS = [
    ("edge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ("chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
]

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>probe</title>
<link rel="stylesheet" href="probe.css">
<script src="probe_static.js"></script>
</head><body>
<div id="marker">x</div>
<pre id="out">PENDING</pre>
<script>
var R = {};
function fin(){ document.getElementById('out').textContent = JSON.stringify(R); }

// 1. classic same-dir <script src>
R.static_script = (typeof window.PROBE_STATIC === 'string') ? window.PROBE_STATIC : 'FAIL';

// 2. same-dir <link rel=stylesheet>
R.stylesheet = getComputedStyle(document.getElementById('marker')).color;

// 3. localStorage under an opaque origin
try { localStorage.setItem('k','v'); R.localStorage = localStorage.getItem('k'); }
catch(e){ R.localStorage = 'THROW:' + e.name; }

// 4. fetch() a same-dir file
R.fetch = 'pending';
try {
  fetch('probe_data.js').then(function(r){ R.fetch='ok:'+r.status; }, function(e){ R.fetch='REJECT:'+e.name; });
} catch(e){ R.fetch = 'THROW:' + e.name; }

// 5. XMLHttpRequest
try { var x=new XMLHttpRequest(); x.open('GET','probe_data.js',false); x.send();
      R.xhr='ok:'+x.status; } catch(e){ R.xhr='THROW:'+e.name; }

// 6. dynamically injected classic <script src>  <-- the load strategy depends on this
R.dyn_script = 'pending';
var s = document.createElement('script');
s.src = 'probe_data.js';
s.onload = function(){
  R.dyn_script = (window.JOB_DATA_CHUNK && window.JOB_DATA_CHUNK.rows === 3)
                 ? 'ok:onload+data' : 'onload_but_no_data';
  step7();
};
s.onerror = function(){ R.dyn_script = 'ONERROR'; step7(); };
document.head.appendChild(s);

// 7. a SECOND dynamic injection of the same shape (5 chunks in a row must all land)
function step7(){
  var n = 0, want = 3, got = [];
  for (var i = 1; i <= want; i++) {
    (function(i){
      var t = document.createElement('script');
      t.src = 'probe_chunk' + i + '.js';
      t.onload = function(){ got.push(i); if (++n === want) done(); };
      t.onerror = function(){ got.push('E' + i); if (++n === want) done(); };
      document.head.appendChild(t);
    })(i);
  }
  function done(){
    R.multi_chunk = got.sort().join(',');
    R.chunk_sum = window.CHUNK_SUM || 0;
    // 8. ES module - expected to be blocked
    var m = document.createElement('script');
    m.type = 'module';
    m.src = 'probe_mod.js';
    m.onload = function(){ R.module = 'ok'; last(); };
    m.onerror = function(){ R.module = 'BLOCKED'; last(); };
    document.head.appendChild(m);
    setTimeout(last, 1200);
  }
}
var finished = false;
function last(){
  if (finished) return; finished = true;
  if (R.module === undefined) R.module = 'no-event';
  setTimeout(function(){ R.origin = String(location.origin); fin(); }, 300);
}
setTimeout(last, 4000);
</script>
</body></html>
"""


def run(exe, url, tmp):
    prof = tempfile.mkdtemp(prefix="pmprof_")
    cmd = [exe, "--headless=new", "--disable-gpu", "--no-first-run",
           "--user-data-dir=" + prof, "--virtual-time-budget=6000",
           "--dump-dom", url]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=120)
        return p.stdout.decode("utf-8", "replace")
    finally:
        shutil.rmtree(prof, ignore_errors=True)


def main():
    banner("PROBE 5  file:// capability table, executed")
    tmp = tempfile.mkdtemp(prefix="pmfile_")
    W = lambda n, s: io.open(os.path.join(tmp, n), "w", encoding="utf-8").write(s)
    W("probe.html", PAGE)
    W("probe.css", "#marker{color:rgb(1, 2, 3)}")
    W("probe_static.js", "window.PROBE_STATIC='ok';")
    W("probe_data.js", "window.JOB_DATA_CHUNK={rows:3};")
    for i in (1, 2, 3):
        W("probe_chunk%d.js" % i,
          "window.CHUNK_SUM=(window.CHUNK_SUM||0)+%d;" % i)
    W("probe_mod.js", "export const x = 1;")
    url = "file:///" + os.path.join(tmp, "probe.html").replace("\\", "/")
    print("temp page: %s\n" % url)

    for name, exe in BROWSERS:
        if not os.path.exists(exe):
            print("%-8s NOT INSTALLED" % name)
            continue
        dom = run(exe, url, tmp)
        m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        raw = m.group(1) if m else "(no output; dom %d bytes)" % len(dom)
        print("%-8s %s" % (name, raw))
        try:
            d = json.loads(raw)
            for k in ("static_script", "stylesheet", "localStorage", "fetch", "xhr",
                      "dyn_script", "multi_chunk", "chunk_sum", "module", "origin"):
                print("           %-14s %s" % (k, d.get(k)))
        except Exception:
            pass
        print("")
    print("temp dir left at %s (delete freely)" % tmp)


if __name__ == "__main__":
    main()
