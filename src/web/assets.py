#!/usr/bin/env python3
"""CSS and the small amount of JavaScript the app needs, as strings.

No build step, no bundler, no CDN. Served from memory with a long cache header
keyed on a content hash, which is the whole of the asset pipeline this
application needs.

The JavaScript here does three things and none of them is a decision: it toggles
disclosure sections, filters a table client-side, and posts a form. Every
verdict on every screen was computed on the server. `tests/test_web_security.py`
asserts this file contains no `fetch` of a provider, no token, and nothing that
writes a verdict.
"""
import hashlib

CSS = """
*{box-sizing:border-box}
:root{
/* Surface. Warm off-white rather than blue-grey: the page should read as
   paper, and the panels sit on it rather than floating over a gradient. */
--bg:#f7f7f5; --panel:#fff; --panel-2:#fbfbfa;
--ink:#14161a; --muted:#6b7280; --faint:#9aa1ab; --line:#e3e3df;
/* One accent, used sparingly. Colour is semantic in this product; a screen
   that accents everything has told the reader nothing. */
--accent:#1a4d8f; --accent-soft:#eef3fa; --accent-deep:#12355f;
--pass:#1b6640; --pass-bg:#e6f4ec; --warn:#8a5a00; --warn-bg:#fdf1d8;
--block:#8d2020; --block-bg:#fbe6e6; --pause:#4b2d85; --pause-bg:#efe9fb;
--head:#14161a;
/* Channel colour is a semantic, not a decoration: the same hue means the
   same channel on the cadence view, the sender screens and the reply
   centre. Two screens that colour email differently teach nothing. */
--email:#25457e; --linkedin:#0a66c2; --both:#4b2d85;
/* The one focus ring. Defined once so it cannot drift per control, and
   never removed - a keyboard user with no visible focus is lost. */
--focus:#4d8fe0;
/* Type scale. Eight steps, and the jumps between them are large enough to
   read as hierarchy rather than as inconsistency. */
--t-display:30px; --t-title:21px; --t-section:16px; --t-card:14px;
--t-body:13.5px; --t-small:12px; --t-caption:11px; --t-metric:26px;
--lh-tight:1.2; --lh-body:1.55;
--radius:6px; --radius-lg:9px; --radius-pill:11px;
--shadow:0 1px 2px rgba(16,32,53,.06);
--shadow-lift:0 4px 14px rgba(16,32,53,.10);
}
body{margin:0;background:var(--bg);color:var(--ink);
font:var(--t-body)/var(--lh-body) -apple-system,BlinkMacSystemFont,
"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
code{background:#eef1f5;padding:1px 5px;border-radius:4px;
font:12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
h1{font-size:var(--t-title);margin:0 0 6px;letter-spacing:-.35px;
font-weight:640;line-height:var(--lh-tight)}
h2{font-size:var(--t-section);margin:30px 0 12px;letter-spacing:-.2px;
font-weight:640}
h3{font-size:var(--t-card);margin:0 0 10px;letter-spacing:-.1px;
font-weight:640}
h4{font-size:var(--t-caption);margin:16px 0 7px;color:var(--muted);
text-transform:uppercase;letter-spacing:.08em;font-weight:650}
.display{font-size:var(--t-display);letter-spacing:-.7px;font-weight:660;
line-height:var(--lh-tight);margin:0 0 6px}
p{margin:8px 0}

/* ---------------------------------------------------------------- shell */
.shell{display:grid;grid-template-columns:216px 1fr;min-height:100vh}
.side{background:var(--head);color:#b9bcc2;padding:20px 0;position:sticky;
top:0;height:100vh;overflow-y:auto}
.brand{padding:0 20px 16px;border-bottom:1px solid #262a31;margin-bottom:12px}
.brand b{color:#fff;font-size:15px;display:block;letter-spacing:-.35px;
font-weight:660}
.brand span{font-size:10.5px;color:#7c828c;letter-spacing:.02em}
.nav a{display:block;padding:7px 20px;color:#b9bcc2;font-size:13px;
border-left:2px solid transparent;transition:none}
.nav a:hover{background:#1d2026;color:#fff;text-decoration:none}
.nav a.on{background:#1d2026;border-left-color:var(--accent);color:#fff;
font-weight:640}
.quickrow{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 22px}
.quick{display:flex;flex-direction:column;gap:3px;padding:13px 17px;
  border:1px solid var(--line);border-radius:9px;background:var(--card);
  min-width:190px;text-decoration:none;color:var(--ink);
  transition:border-color .12s,box-shadow .12s}
.quick:hover{border-color:var(--accent);text-decoration:none;
  box-shadow:0 1px 3px rgba(16,24,40,.07)}
.quick b{font-size:14px}
.quick span{font-size:12px;color:var(--muted)}
.quick.primary{background:var(--accent);border-color:var(--accent)}
.quick.primary b,.quick.primary span{color:#fff}
.quick.primary span{opacity:.85}
.quick.primary:hover{box-shadow:0 2px 8px rgba(16,24,40,.18)}
.navsec>summary{padding:9px 20px;font-size:11px;text-transform:uppercase;
  letter-spacing:.09em;color:#8b9099;cursor:pointer;list-style:none;
  user-select:none;border-left:3px solid transparent}
.navsec>summary::-webkit-details-marker{display:none}
.navsec>summary::after{content:"+";float:right;opacity:.5;font-size:13px;
  line-height:1}
/* A plain hyphen, not an escaped unicode minus: the escape rendered as a
   missing-glyph box beside a stray digit, which reads as breakage. */
.navsec[open]>summary::after{content:"-"}
.navsec>summary:hover{color:#fff;background:#1d2026}
.navsec>summary:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.navsec[open]>summary{color:#e6e8ea}
.navsec .navkids{padding-bottom:6px}
.nav .sep{padding:18px 20px 6px;font-size:10px;text-transform:uppercase;
letter-spacing:.12em;color:#6a7078;font-weight:650}
.main{min-width:0}
.top{background:var(--panel);border-bottom:1px solid var(--line);
padding:11px 26px;display:flex;gap:16px;align-items:center;flex-wrap:wrap;
position:sticky;top:0;z-index:5}
.top form{display:flex;gap:6px;align-items:center;margin:0}
.top select{padding:5px 8px;border:1px solid var(--line);border-radius:6px;
background:#fff;font:inherit;font-size:13px}
.spacer{flex:1}
.wrap{padding:26px 26px 80px;max-width:1480px}
.crumb{color:var(--muted);font-size:var(--t-small);margin-bottom:18px}

/* --------------------------------------------------------------- safety */
.safety{display:flex;gap:7px;align-items:center;font-size:11.5px}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.dot.off{background:#3d9c6d}
.dot.demo{background:#d59b2a}
.banner{background:var(--warn-bg);border:1px solid #e2c268;border-radius:8px;
padding:10px 13px;margin:0 0 16px;font-size:13px}
.banner.stop{background:var(--block-bg);border-color:#d98080}

/* ---------------------------------------------------------------- cards */
.stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(132px,1fr));
gap:10px;margin:12px 0}
.stat{background:var(--panel);border:1px solid var(--line);
border-radius:var(--radius);padding:13px 15px}
.stat .n{font-size:var(--t-metric);font-weight:660;letter-spacing:-.9px;
line-height:1.1;font-variant-numeric:tabular-nums}
.stat .k{font-size:var(--t-caption);text-transform:uppercase;
letter-spacing:.07em;color:var(--muted);margin-top:4px;font-weight:600}
.stat.pass{border-color:#8fcbab;background:#f4fcf8}
.stat.warn{border-color:#e0c179;background:#fffcf3}
.stat.block{border-color:#e0a0a0;background:#fdf6f6}
.stat.pause{border-color:#c3b0e6;background:#f9f6fe}
.panel{background:var(--panel);border:1px solid var(--line);
border-radius:var(--radius-lg);padding:20px 22px;margin:18px 0;
box-shadow:var(--shadow)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}

/* --------------------------------------------------------------- tables */
table{width:100%;border-collapse:collapse;font-size:var(--t-small)}
th{text-align:left;background:var(--panel-2);padding:9px 11px;
font-weight:650;font-size:var(--t-caption);text-transform:uppercase;
letter-spacing:.07em;color:var(--muted);position:sticky;top:0;
border-bottom:1px solid var(--line)}
td{padding:10px 11px;border-top:1px solid var(--line);vertical-align:top;
font-variant-numeric:tabular-nums}
tbody tr:hover td{background:var(--accent-soft)}
tbody tr.on td{background:var(--accent-soft);
box-shadow:inset 2px 0 0 var(--accent)}
table.kv th{width:220px;background:none;text-transform:none;letter-spacing:0;
font-weight:500;color:var(--muted);font-size:13px;position:static}
table.kv td{border:none;padding:5px 0}
table.kv th{border:none;padding:5px 10px 5px 0}
.scroll{overflow-x:auto}

/* ---------------------------------------------------------------- badges */
.tag{display:inline-block;padding:2px 9px;border-radius:var(--radius-pill);
font-size:var(--t-caption);font-weight:640;background:#eeeeec;
color:#4a4f57;margin:0 3px 2px 0;white-space:nowrap;letter-spacing:.01em}
.tag.pass{background:var(--pass-bg);color:var(--pass)}
.tag.warn{background:var(--warn-bg);color:var(--warn)}
.tag.block{background:var(--block-bg);color:var(--block)}
.tag.pause{background:var(--pause-bg);color:var(--pause)}
.tag.info{background:#dee8f7;color:var(--accent)}
.mode{font-weight:700;letter-spacing:.03em;font-size:11px}

/* ----------------------------------------------------------------- misc */
.muted{color:var(--muted)}
.small{font-size:12px}
.note{background:#f1f5f9;border-radius:7px;padding:9px 11px;font-size:12.5px;
color:#3c4b5c;margin:8px 0}
.absent{color:#93a1b0;font-style:italic}
.empty{text-align:center;padding:38px 20px;color:var(--muted)}
.empty b{display:block;font-size:15px;color:var(--ink);margin-bottom:5px}
details{border-top:1px solid var(--line)}
details>summary{cursor:pointer;padding:9px 0;font-weight:600;font-size:13.5px;
list-style:none}
details>summary::-webkit-details-marker{display:none}
details>summary:before{content:"\\25B8";display:inline-block;width:15px;
color:#8fa3b8}
details[open]>summary:before{content:"\\25BE"}
.secbody{padding:2px 0 15px 15px}
pre.copy{white-space:pre-wrap;word-wrap:break-word;background:#fbfcfe;
border:1px solid var(--line);border-radius:7px;padding:11px 13px;margin:6px 0;
font:13.5px/1.6 inherit}
pre.json{white-space:pre-wrap;word-wrap:break-word;background:var(--head);
color:#cfe0f2;border-radius:8px;padding:12px;overflow-x:auto;
font:11.5px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.bar{height:7px;background:#e4eaf1;border-radius:4px;overflow:hidden;margin:4px 0}
.bar i{display:block;height:100%;background:var(--accent)}
.step{border:1px solid var(--line);border-left:4px solid #b9c4d0;border-radius:8px;
padding:11px 13px;margin:8px 0;background:#fcfdfe}
.step.pass{border-left-color:#3d9c6d;background:#f8fdfa}
.step.block{border-left-color:#c05a5a;background:#fdf8f8}
.step.warn{border-left-color:#d59b2a;background:#fffdf6}
.step.pause{border-left-color:#7d5bbe;background:#faf8fe}
.stephead{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.day{font-weight:700;font-size:11.5px;letter-spacing:.05em;color:var(--accent)}
.tree{list-style:none;padding-left:16px;margin:4px 0}
.tree li{margin:3px 0}
.tree .node{font-weight:600}
.btn{display:inline-block;padding:7px 13px;border-radius:7px;border:1px solid var(--line);
background:#fff;font:inherit;font-size:13px;cursor:pointer;color:var(--ink)}
.btn:hover{background:#f2f6fa;text-decoration:none}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.btn.primary:hover{background:#1d3766}
.btn[disabled]{opacity:.5;cursor:not-allowed}
.filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0}
.filters input,.filters select{padding:6px 9px;border:1px solid var(--line);
border-radius:6px;font:inherit;font-size:13px;background:#fff}
.login{max-width:400px;margin:9vh auto;background:var(--panel);
border:1px solid var(--line);border-radius:12px;padding:28px}
.login h1{margin-bottom:14px}
.login label{display:block;font-size:12px;color:var(--muted);margin:12px 0 4px}
.login input,.login select{width:100%;padding:9px 11px;border:1px solid var(--line);
border-radius:7px;font:inherit}
.login .btn{width:100%;margin-top:18px;padding:10px}
.stack{display:flex;flex-direction:column;gap:10px;align-items:flex-start;
max-width:520px}
.stack label{display:block;font-size:12px;color:var(--muted);width:100%}
.stack input,.stack select,.stack textarea{width:100%;margin-top:4px;
padding:8px 10px;border:1px solid var(--line);border-radius:7px;font:inherit;
font-size:13px;background:#fff}
.note.ok{background:var(--pass-bg)}
.note.stop{background:var(--block-bg)}
/* A conversation row that needs a second look: a confirmed step
   that went out after the person had already replied. */
tr.flagged td{background:var(--block-bg)}
.tag.muted{background:#e7ebf0;color:var(--muted)}
.block-text{color:var(--block)}
.wsname{font-weight:650;font-size:13.5px;letter-spacing:-.2px;
padding:3px 9px;border-radius:7px;background:#e4ecf8;color:var(--accent)}
.wsname.none{background:#f0e2e2;color:var(--block)}
.wsgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));
gap:14px;margin:14px 0}
.wscard{background:var(--panel);border:1px solid var(--line);border-radius:10px;
padding:14px 16px}
.wscard h3{margin-top:0}
.wscard .stats{grid-template-columns:repeat(auto-fill,minmax(96px,1fr))}
.wscard .stat .n{font-size:17px}
.timeline{list-style:none;padding:0;margin:8px 0}
.timeline li{border-left:3px solid var(--line);padding:6px 0 10px 14px;
margin-left:6px;position:relative}
.timeline li.confirmed{border-left-color:#3d9c6d}
.timeline li.refused{border-left-color:#d59b2a}
.xchan{border-radius:7px;padding:7px 10px;margin:6px 0;font-size:12.5px}
.xchan.ok{background:var(--pass-bg)}
.xchan.no{background:var(--warn-bg)}


/* ------------------------------------------------------------- controls */
/* One definition per control shape. Before this, a `<button>` outside
   `.btn` and an `<input type=date>` inherited the browser default and every
   form built from them looked like a different application. */
button,input[type=submit]{display:inline-block;padding:7px 13px;
border-radius:var(--radius);border:1px solid var(--accent);
background:var(--accent);color:#fff;font:inherit;font-size:13px;
font-weight:600;cursor:pointer}
button:hover,input[type=submit]:hover{background:#1d3766}
button[disabled],input[type=submit][disabled]{opacity:.5;cursor:not-allowed;
background:var(--muted);border-color:var(--muted)}
button.ghost{background:#fff;color:var(--ink);border-color:var(--line);
font-weight:500}
button.ghost:hover{background:#f2f6fa}
/* A destructive control must not look like a neighbouring safe one. */
button.danger{background:var(--block);border-color:var(--block)}
button.danger:hover{background:#701919}
input[type=text],input[type=date],input[type=search],input[type=number],
input[type=email],select,textarea{padding:7px 9px;border:1px solid var(--line);
border-radius:var(--radius);font:inherit;font-size:13px;background:#fff;
color:var(--ink)}
select[multiple]{padding:4px}
label{display:block;font-size:12px;color:var(--muted);margin:8px 0 0}
label input,label select,label textarea{display:block;margin-top:4px;
width:100%}
/* Never `outline:none`. The ring is the only thing telling a keyboard user
   where they are, and a design that removes it is not finished. */
:focus-visible{outline:2px solid var(--focus);outline-offset:2px;
border-radius:3px}
.checks{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));
gap:2px 14px;margin:12px 0;padding:12px;background:#fbfcfe;
border:1px solid var(--line);border-radius:var(--radius)}
label.check{display:flex;gap:7px;align-items:center;font-size:12.5px;
color:var(--ink);margin:0;padding:3px 0;cursor:pointer}
label.check input{display:inline;width:auto;margin:0}

/* ---------------------------------------------------------- channel hues */
.chan{display:inline-block;width:8px;height:8px;border-radius:2px;
margin-right:5px;vertical-align:baseline}
.chan.email{background:var(--email)}
.chan.linkedin{background:var(--linkedin)}
.chan.both{background:var(--both)}

/* --------------------------------------------------------------- states */
/* An empty state that only says "none" is a dead end. Every one of these
   carries the next safe action, which is why it gets its own shape. */
.empty .next{display:block;margin-top:10px;font-size:12.5px}
.skel{background:linear-gradient(90deg,#eef2f7 25%,#e3e9f1 50%,#eef2f7 75%);
background-size:400% 100%;animation:sk 1.4s ease-in-out infinite;
border-radius:var(--radius);height:14px;margin:6px 0}
@keyframes sk{0%{background-position:100% 0}100%{background-position:0 0}}
@media(prefers-reduced-motion:reduce){.skel{animation:none}}

@media(max-width:1000px){
.shell{grid-template-columns:1fr}
.side{position:static;height:auto}
.nav{display:flex;flex-wrap:wrap}
.nav a{border-left:none;border-bottom:3px solid transparent}
.nav a.on{border-left:none;border-bottom-color:#4d8fe0}
.nav .sep{display:none}
.grid2,.grid3{grid-template-columns:1fr}
table.kv th{width:auto;display:block;padding-bottom:0}
table.kv td{display:block;padding-top:2px}
}
"""

# Three behaviours, none of them a decision: disclosure, a client-side filter
# over rows the server already chose, and submitting a form. Everything that
# matters was decided before the page was rendered.
JS = """
(function(){
  function filterTable(input){
    var id = input.getAttribute('data-filter');
    var table = document.getElementById(id);
    if(!table) return;
    var q = input.value.trim().toLowerCase();
    var rows = table.tBodies[0] ? table.tBodies[0].rows : [];
    var shown = 0;
    for(var i=0;i<rows.length;i++){
      var hit = !q || rows[i].textContent.toLowerCase().indexOf(q) !== -1;
      rows[i].style.display = hit ? '' : 'none';
      if(hit) shown++;
    }
    var count = document.querySelector('[data-count="'+id+'"]');
    if(count) count.textContent = shown + ' of ' + rows.length;
  }
  document.addEventListener('input', function(e){
    if(e.target && e.target.hasAttribute('data-filter')) filterTable(e.target);
  });
  document.addEventListener('change', function(e){
    if(e.target && e.target.hasAttribute('data-autosubmit')){
      var form = e.target.form; if(form) form.submit();
    }
  });
})();
"""


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


CSS_VERSION = digest(CSS)
JS_VERSION = digest(JS)
