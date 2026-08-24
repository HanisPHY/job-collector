# -*- coding: utf-8 -*-
"""EVAL B probe: rubric item 6 - does clicking an anchor whose target equals the
CURRENT location.hash actually fire a 'hashchange' event?

design_v1.md S4.8 says the *entire* jump mechanism is:
    "JS 只做一件事：hashchange + 首屏读 location.hash -> el.open = true"
If hashchange does not fire when the hash string does not change (well-known DOM
behaviour, but worth confirming on the actual browser/binary this project uses,
not taking it on faith), then re-clicking the same stacked-bar segment / legend
item a second time (after the user manually collapsed it) is a silent no-op:
nothing re-opens the <details>, nothing scrolls, nothing focuses.

Run:
  export PYTHONIOENCODING=utf-8
  D:/Apps/Miniconda/envs/job-classifier/python.exe dashboard_loop/v2/_evalB_hashclick.py
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
    ("chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ("edge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>probe</title></head>
<body>
<a id="lnk" href="#seg-1a_t3">jump</a>
<details id="seg-1a_t3"><summary>seg</summary>body</details>
<pre id="out">PENDING</pre>
<script>
var events = 0;
window.addEventListener('hashchange', function(){ events++; });

function clickIt(cb){
  document.getElementById('lnk').click();
  setTimeout(cb, 60);
}

var log = [];
// 1st click: hash goes from '' to '#seg-1a_t3' -> should fire hashchange
clickIt(function(){
  log.push('after_click_1 hash=' + location.hash + ' events=' + events);
  // user manually "closes" the details (simulating collapse) then clicks the SAME
  // anchor again while the hash is unchanged
  document.getElementById('seg-1a_t3').open = false;
  clickIt(function(){
    log.push('after_click_2_same_hash hash=' + location.hash + ' events=' + events);
    document.getElementById('out').textContent = JSON.stringify(log);
  });
});
</script>
</body></html>
"""


def run(exe, url):
    prof = tempfile.mkdtemp(prefix="pmprof_")
    cmd = [exe, "--headless=new", "--disable-gpu", "--no-first-run",
           "--user-data-dir=" + prof, "--virtual-time-budget=4000",
           "--dump-dom", url]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return p.stdout.decode("utf-8", "replace")
    finally:
        shutil.rmtree(prof, ignore_errors=True)


def main():
    banner("EVAL B - does re-clicking the SAME #anchor fire hashchange again?")
    tmp = tempfile.mkdtemp(prefix="pmhash_")
    path = os.path.join(tmp, "probe.html")
    io.open(path, "w", encoding="utf-8").write(PAGE)
    url = "file:///" + path.replace("\\", "/")
    print("temp page: %s\n" % url)
    for name, exe in BROWSERS:
        if not os.path.exists(exe):
            print("%-8s NOT INSTALLED" % name)
            continue
        dom = run(exe, url)
        m = re.search(r'<pre id="out">(.*?)</pre>', dom, re.S)
        raw = m.group(1) if m else "(no output; dom %d bytes)" % len(dom)
        print("%-8s %s" % (name, raw))
    print("\ntemp dir left at %s (delete freely)" % tmp)


if __name__ == "__main__":
    main()
