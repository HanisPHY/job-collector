(function(){
  window.__marker = "alive";
  var out = [], pre = document.createElement("pre"); pre.id="qa9"; document.body.appendChild(pre);
  function flush(){ pre.textContent = out.join("\n"); }
  function dups(){
    var r=[]; document.querySelectorAll('details[data-gidx]').forEach(function(d){
      var seen={}, n=0, rows=d.querySelectorAll('tr');
      rows.forEach(function(tr){ var c=tr.querySelector('td.co'), t=tr.querySelector('td.ti'); if(!c||!t) return;
        var k=c.textContent.trim()+"\u0000"+t.textContent.trim().toLowerCase(); if(seen[k]) n++; seen[k]=1; });
      r.push(d.getAttribute('data-gidx')+":"+rows.length+"tr/"+n+"dup");
    }); return r.join(" ");
  }
  function snap(tag){
    var recon=document.getElementById('recon'), seg3=document.querySelector('details[data-gidx="2"]');
    var rect=seg3.getBoundingClientRect();
    out.push([tag,"marker="+(window.__marker?"ok":"LOST"),"banner_hidden="+(recon?recon.hidden:"?"),
      "busy="+!!document.querySelector('[aria-busy="true"]'),
      "seg3_open="+seg3.open,"seg3_top="+Math.round(rect.top),"scrollY="+Math.round(window.scrollY),
      "n="+document.querySelector('#nsel [aria-checked="true"]').getAttribute('data-n'), dups()].join(" | "));
    flush();
  }
  function run(){
    try {
      var seg3=document.querySelector('details[data-gidx="2"]'); seg3.open=true;
      seg3.scrollIntoView({block:"start"}); window.scrollBy(0,120);
      snap("baseline");
      [1,3,7,14,30,3].forEach(function(n){
        var b=document.querySelector('#nsel [data-n="'+n+'"]'); out.push("pre-click "+n+" b="+!!b); flush(); console.log("QA pre-click "+n); b.click(); console.log("QA post-click "+n); snap("after N="+n);
      });
      ["new","wm","all"].forEach(function(v){
        var b=document.querySelector('#vsel [data-v="'+v+'"]'); if(b){ b.click(); snap("after view="+v); }
      });
      out.push("DONE"); flush();
    } catch(e){ out.push("ERR "+e+" "+(e.stack||"")); flush(); }
  }
  window.addEventListener("error", function(ev){ out.push("WINERR "+ev.message); flush(); });
  if(document.readyState==="complete") run(); else window.addEventListener("load",run);
})();
