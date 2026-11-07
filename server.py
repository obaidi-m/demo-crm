"""My Work Brain website: a local, view-only window into brain.db and the files folder.

Start it with start-brain.bat (or: python server.py). It opens http://localhost:8790 in the browser.
Nothing on the website writes to the database; Claude writes through brain.py.
"""
import datetime as dt
import html
import json
import mimetypes
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import brain

PORT = 8792
FILES = brain.FILES.resolve()


def esc(v):
    return html.escape("" if v is None else str(v))


def fmt_date(s):
    if not s:
        return ""
    try:
        d = dt.date.fromisoformat(s)
    except ValueError:
        return esc(s)
    return f"{d:%a} {d.day} {d:%b}" + ("" if d.year == dt.date.today().year else f" {d.year}")


def num(v):
    return "–" if v is None or v == "" else f"{v:,}" if isinstance(v, int) else esc(v)


def link_for(target):
    """A record's link: a web address, or a path inside the files folder."""
    if not target:
        return ""
    if re.match(r"https?://", target):
        return f'<a href="{esc(target)}" target="_blank" rel="noopener">{esc(target)}</a>'
    return f'<a href="/file?p={quote(target)}">{esc(target)}</a>'


# ---------- markdown to html (small, enough for these files) ----------

def inline(text, base):
    codes = []

    def keep_code(m):
        codes.append(f"<code>{esc(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep_code, text)
    text = esc(text)

    def make_link(m):
        label, url = m.group(1), html.unescape(m.group(2))
        if re.match(r"https?://|mailto:", url):
            return f'<a href="{esc(url)}" target="_blank" rel="noopener">{label}</a>'
        if url.startswith("#"):
            return f'<a href="{esc(url)}">{label}</a>'
        target = (Path(base) / url).as_posix() if base else url
        return f'<a href="/file?p={quote(target)}">{label}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", make_link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"<em>\1</em>", text)
    text = re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)
    return text


LIST_RE = re.compile(r"^(\s*)([-*+]|\d+\.)\s+(.*)$")


def render_list(lines, base):
    out, stack = [], []  # stack of (indent, tag)
    for raw in lines:
        m = LIST_RE.match(raw)
        if not m:
            if out:
                out[-1] = out[-1].removesuffix("</li>") + " " + inline(raw.strip(), base) + "</li>"
            continue
        indent, marker, body = len(m.group(1).expandtabs(4)), m.group(2), m.group(3)
        tag = "ol" if marker[0].isdigit() else "ul"
        while stack and indent < stack[-1][0]:
            _, closing, nested = stack.pop()
            out.append(f"</{closing}>" + ("</li>" if nested else ""))
        if not stack or indent > stack[-1][0]:
            if stack and out and out[-1].endswith("</li>"):
                out[-1] = out[-1].removesuffix("</li>")
                stack.append((indent, tag, True))
            else:
                stack.append((indent, tag, False))
            out.append(f"<{tag}>")
        box = re.match(r"\[([ xX])\]\s+(.*)", body)
        if box:
            checked = "checked" if box.group(1).lower() == "x" else ""
            out.append(f'<li class="task"><input type="checkbox" disabled {checked}> {inline(box.group(2), base)}</li>')
        else:
            out.append(f"<li>{inline(body, base)}</li>")
    while stack:
        indent, tag, *nested = stack.pop()
        out.append(f"</{tag}>")
        if nested and nested[0]:
            out.append("</li>")
    return "\n".join(out)


def md_to_html(text, base=""):
    lines = text.replace("\r\n", "\n").split("\n")
    out, para, i = [], [], 0

    def flush():
        if para:
            out.append("<p>" + "<br>".join(inline(p, base) for p in para) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            flush()
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            out.append(f"<pre><code>{esc(chr(10).join(code))}</code></pre>")
        elif re.match(r"^#{1,6}\s", line):
            flush()
            level = len(line) - len(line.lstrip("#"))
            title = line[level:].strip()
            anchor = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            out.append(f'<h{level} id="{anchor}">{inline(title, base)}</h{level}>')
        elif re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
            flush()
            out.append("<hr>")
        elif line.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            flush()
            def cells(row):
                return [c.strip() for c in row.strip().strip("|").split("|")]
            head = cells(line)
            i += 2
            body = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                body.append(cells(lines[i]))
                i += 1
            i -= 1
            t = ["<div class='scroll'><table><thead><tr>"] + [f"<th>{inline(c, base)}</th>" for c in head] + ["</tr></thead><tbody>"]
            for r in body:
                t.append("<tr>" + "".join(f"<td>{inline(c, base)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
        elif LIST_RE.match(line):
            flush()
            block = []
            while i < len(lines) and (LIST_RE.match(lines[i]) or (lines[i].startswith("  ") and lines[i].strip())):
                block.append(lines[i])
                i += 1
            i -= 1
            out.append(render_list(block, base))
        elif line.startswith(">"):
            flush()
            quote_lines = []
            while i < len(lines) and lines[i].startswith(">"):
                quote_lines.append(lines[i][1:].lstrip())
                i += 1
            i -= 1
            out.append(f"<blockquote>{md_to_html(chr(10).join(quote_lines), base)}</blockquote>")
        elif not line.strip():
            flush()
        else:
            para.append(line.strip())
        i += 1
    flush()
    return "\n".join(out)


# ---------- page shell ----------

OWNER = "Mohammed"

NAV = [
    (None, "Plan", None),
    ("/", "Today", "sun"), ("/week", "Week", "calendar"), ("/board", "Board", "columns"),
    ("/projects", "Projects", "layers"), ("/review", "Weekly review", "inbox"),
    (None, "Work", None),
    ("/tasks", "Tasks", "check"), ("/posts", "Posts", "pen"), ("/ideas", "Ideas", "bulb"),
    ("/people", "People", "people"), ("/weekly", "Weekly numbers", "chart"),
    (None, "Memory", None),
    ("/decisions", "Decisions", "fork"), ("/goals", "Goals", "target"), ("/rules", "How we work", "compass"),
    ("/log", "Log", "log"), ("/activity", "Activity", "pulse"), ("/files", "Library", "book"),
]

ICONS = {
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4"/>',
    "pulse": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "calendar": '<rect x="3" y="4" width="18" height="17" rx="3"/><path d="M3 9h18M8 2v4M16 2v4"/>',
    "columns": '<rect x="3" y="4" width="5" height="16" rx="1.5"/><rect x="10" y="4" width="5" height="11" rx="1.5"/><rect x="17" y="4" width="4" height="7" rx="1.5"/>',
    "layers": '<path d="m12 3 9 5-9 5-9-5Z"/><path d="m3 13 9 5 9-5"/>',
    "inbox": '<path d="M3 13h5l1.5 3h5L16 13h5"/><path d="M5 5h14l2 8v6H3v-6Z"/>',
    "repeat": '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14M7 22l-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "up": '<path d="m6 15 6-6 6 6"/>',
    "ok": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    "log": '<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
    "fork": '<circle cx="6" cy="5" r="2"/><circle cx="18" cy="5" r="2"/><circle cx="12" cy="19" r="2"/><path d="M6 7v1a3 3 0 0 0 3 3h6a3 3 0 0 0 3-3V7M12 11v6"/>',
    "check": '<rect x="3" y="3" width="18" height="18" rx="5"/><path d="m8 12 3 3 5-6"/>',
    "pen": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    "bulb": '<path d="M9 18h6M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.3h6c0-1 .4-1.8 1-2.3A7 7 0 0 0 12 2Z"/>',
    "people": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M8 17v-5M13 17V8M18 17v-3"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/>',
    "compass": '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5Z"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5Z"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "moon": '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "dot": '<circle cx="12" cy="12" r="3"/>',
    "flag": '<path d="M4 22V4M4 4h13l-2 4 2 4H4"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
}


def icon(name, cls="ic"):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS.get(name, ICONS["dot"])}</svg>')


CSS = r"""
:root{
  --bg:#f4efe7;--bg-2:#ede6db;--panel:#fffdf9;--panel-2:#f8f3eb;--ink:#1a1815;--muted:#57514a;--faint:#6e675d;
  --line:rgba(28,26,23,.12);--line-2:rgba(28,26,23,.22);
  --accent:#a8441c;--accent-2:#e07a52;--accent-soft:rgba(194,85,44,.10);--accent-ink:#fff;
  --ok:#22684d;--ok-soft:rgba(44,122,92,.12);--warn:#9a4314;--warn-soft:rgba(224,122,82,.13);
  --chip:rgba(28,26,23,.055);--glow:rgba(224,122,82,.22);--glow-2:rgba(44,122,92,.10);
  --shadow:0 1px 0 rgba(255,255,255,.7) inset,0 1px 2px rgba(28,26,23,.04),0 8px 24px -12px rgba(28,26,23,.12);
  --shadow-up:0 1px 0 rgba(255,255,255,.7) inset,0 2px 4px rgba(28,26,23,.05),0 22px 44px -18px rgba(28,26,23,.22);
  --side:rgba(255,252,247,.66);--grain:.035;
  color-scheme:light;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0c0b0a;--bg-2:#141311;--panel:#1c1a18;--panel-2:#24221f;--ink:#f4efe7;--muted:#bdb5a8;--faint:#9c9488;
  --line:rgba(255,240,220,.10);--line-2:rgba(255,240,220,.20);
  --accent:#ef8a5f;--accent-2:#f3a47e;--accent-soft:rgba(233,130,87,.13);--accent-ink:#140c08;
  --ok:#86c9a9;--ok-soft:rgba(134,201,169,.12);--warn:#f0a070;--warn-soft:rgba(240,160,112,.12);
  --chip:rgba(255,240,220,.06);--glow:rgba(233,130,87,.20);--glow-2:rgba(134,201,169,.07);
  --shadow:0 1px 0 rgba(255,255,255,.035) inset,0 10px 30px -14px rgba(0,0,0,.7);
  --shadow-up:0 1px 0 rgba(255,255,255,.06) inset,0 26px 50px -20px rgba(0,0,0,.85);
  --side:rgba(19,18,16,.6);--grain:.05;color-scheme:dark;}}
:root[data-theme="dark"]{
  --bg:#0c0b0a;--bg-2:#141311;--panel:#1c1a18;--panel-2:#24221f;--ink:#f4efe7;--muted:#bdb5a8;--faint:#9c9488;
  --line:rgba(255,240,220,.10);--line-2:rgba(255,240,220,.20);
  --accent:#ef8a5f;--accent-2:#f3a47e;--accent-soft:rgba(233,130,87,.13);--accent-ink:#140c08;
  --ok:#86c9a9;--ok-soft:rgba(134,201,169,.12);--warn:#f0a070;--warn-soft:rgba(240,160,112,.12);
  --chip:rgba(255,240,220,.06);--glow:rgba(233,130,87,.20);--glow-2:rgba(134,201,169,.07);
  --shadow:0 1px 0 rgba(255,255,255,.035) inset,0 10px 30px -14px rgba(0,0,0,.7);
  --shadow-up:0 1px 0 rgba(255,255,255,.06) inset,0 26px 50px -20px rgba(0,0,0,.85);
  --side:rgba(19,18,16,.6);--grain:.05;color-scheme:dark;}

@view-transition{navigation:auto}
::view-transition-old(root){animation:none}
::view-transition-new(root){animation:.25s ease both vt-in}
@keyframes vt-out{to{opacity:0}}
@keyframes vt-in{from{opacity:0}}
aside{view-transition-name:side}

*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;scrollbar-gutter:stable;background:var(--bg)}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 "Inter",system-ui,-apple-system,"Segoe UI",sans-serif;
  font-feature-settings:"cv11","ss01";-webkit-font-smoothing:antialiased;min-height:100vh;overflow-x:hidden}
body::before{content:"";position:fixed;inset:-20vh -10vw auto auto;width:70vw;height:70vh;pointer-events:none;z-index:0;
  background:radial-gradient(closest-side,var(--glow),transparent 70%);filter:blur(20px);animation:drift 22s ease-in-out infinite alternate}
body::after{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;opacity:var(--grain);
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
@keyframes drift{from{transform:translate(0,0) scale(1)}to{transform:translate(-8vw,6vh) scale(1.15)}}
.glow-2{position:fixed;left:-15vw;bottom:-25vh;width:60vw;height:60vh;pointer-events:none;z-index:0;
  background:radial-gradient(closest-side,var(--glow-2),transparent 70%);filter:blur(30px)}
::selection{background:var(--accent);color:var(--accent-ink)}
a{color:var(--accent);text-decoration:none;transition:color .2s}
a:hover{color:var(--accent-2)}
main a{text-decoration:underline;text-decoration-color:transparent;text-decoration-thickness:1px;text-underline-offset:3px;transition:text-decoration-color .2s,color .2s}
main a:hover{text-decoration-color:currentColor}
main .filters a,main a.tile{text-decoration:none}
.ic{width:18px;height:18px;flex:none}

/* layout */
.wrap{position:relative;z-index:1;display:flex;min-height:100vh}
aside{width:252px;flex:none;position:sticky;top:0;height:100vh;overflow:auto;padding:22px 14px 18px;display:flex;flex-direction:column;
  background:var(--side);backdrop-filter:blur(18px) saturate(1.3);-webkit-backdrop-filter:blur(18px) saturate(1.3);border-right:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:11px;margin:0 8px 20px;color:var(--ink)}
.brand:hover{color:var(--ink)}
.orb{width:32px;height:32px;border-radius:10px;flex:none;position:relative;overflow:hidden;
  background:conic-gradient(from 200deg,var(--accent),#f3c19f,var(--ok),var(--accent));box-shadow:0 6px 18px -6px var(--glow)}
.orb::after{content:"";position:absolute;inset:2px;border-radius:8px;background:radial-gradient(circle at 30% 25%,rgba(255,255,255,.55),transparent 55%),var(--panel);opacity:.86}
.orb::before{content:"";position:absolute;inset:0;margin:auto;width:9px;height:9px;border-radius:50%;background:var(--accent);z-index:1;box-shadow:0 0 12px var(--accent);animation:pulse 3.2s ease-in-out infinite}
@keyframes pulse{50%{transform:scale(.7);opacity:.7}}
.brand b{display:block;font:600 15px/1.2 "Fraunces",Georgia,serif;letter-spacing:-.01em}
.brand small{display:block;font-size:11.5px;color:var(--muted)}
.kbar{display:flex;align-items:center;gap:9px;width:100%;padding:9px 11px;margin:0 0 16px;border:1px solid var(--line);border-radius:11px;
  background:var(--panel);color:var(--muted);font:inherit;font-size:13.5px;cursor:pointer;box-shadow:var(--shadow);transition:border-color .2s,transform .2s;white-space:nowrap}
.kbar span{overflow:hidden;text-overflow:ellipsis}
.kbar:hover{border-color:var(--line-2);transform:translateY(-1px)}
.kbar kbd{margin-left:auto}
kbd{font:500 11px/1 "JetBrains Mono",ui-monospace,monospace;padding:4px 6px;border-radius:6px;border:1px solid var(--line-2);color:var(--muted);background:var(--chip)}
aside nav{display:flex;flex-direction:column;gap:1px;position:relative}
aside nav a{position:relative;display:flex;align-items:center;gap:11px;padding:7.5px 11px;border-radius:10px;color:var(--muted);font-size:14px;font-weight:500;transition:color .2s,background .2s}
aside nav a .ic{opacity:.75;transition:transform .3s cubic-bezier(.2,.8,.2,1.4),opacity .2s}
aside nav a:hover{color:var(--ink);background:var(--chip)}
aside nav a:hover .ic{transform:scale(1.12) rotate(-4deg);opacity:1}
aside nav a.on{color:var(--ink);background:var(--panel);box-shadow:var(--shadow)}
aside nav a.on::before{content:"";position:absolute;left:-14px;top:9px;bottom:9px;width:3px;border-radius:0 3px 3px 0;background:var(--accent);box-shadow:0 0 12px var(--accent)}
aside nav a.on .ic{color:var(--accent);opacity:1}
aside nav h4:first-child{margin-top:4px}
aside h4{margin:22px 11px 8px;font:600 10.5px/1 "Inter",sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--faint)}
aside nav.areas a{font-size:13.5px;padding:6px 11px}
aside nav.areas a .dot{width:7px;height:7px;border-radius:50%;background:var(--faint);flex:none;margin:0 5px}
aside nav.areas a.on .dot,aside nav.areas a:hover .dot{background:var(--accent)}
aside nav.areas .chip{margin-left:auto;font-size:10.5px}
.side-foot{margin-top:auto;padding-top:18px;display:flex;gap:6px}
.icon-btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;height:34px;padding:0 11px;border-radius:10px;border:1px solid var(--line);
  background:var(--panel);color:var(--muted);font:inherit;font-size:12.5px;cursor:pointer;transition:all .2s}
.icon-btn:hover{color:var(--ink);border-color:var(--line-2)}
.icon-btn .ic{width:16px;height:16px}
:root[data-private] #privBtn{color:var(--accent);border-color:var(--accent)}
main{flex:1;min-width:0;padding:44px clamp(18px,4vw,56px) 80px;max-width:1180px}
.topbar{display:none}

/* type */
.eyebrow{display:inline-flex;align-items:center;gap:8px;font:600 11.5px/1 "Inter",sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin:0 0 14px}
.eyebrow::before{content:"";width:18px;height:1px;background:currentColor}
h1{font:500 clamp(30px,3.6vw,42px)/1.08 "Fraunces",Georgia,serif;letter-spacing:-.025em;margin:0 0 8px;font-variation-settings:"opsz" 96}
h1+.sub,.sub{color:var(--muted);margin:0 0 30px;font-size:15.5px;max-width:64ch}
h2{font:600 13px/1.3 "Inter",sans-serif;letter-spacing:.02em;margin:36px 0 12px;color:var(--ink);display:flex;align-items:center;gap:9px}
h2 .ic{color:var(--accent);width:16px;height:16px}
.muted{color:var(--muted)}.small{font-size:13px}
strong{font-weight:600}

/* surfaces */
.card{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:20px 22px;margin:0 0 16px;box-shadow:var(--shadow);
  transition:transform .35s cubic-bezier(.2,.7,.2,1),box-shadow .35s,border-color .35s;isolation:isolate}
.card::before{content:"";position:absolute;inset:0;border-radius:inherit;z-index:-1;opacity:0;transition:opacity .4s;
  background:radial-gradient(420px circle at var(--mx,50%) var(--my,0%),var(--accent-soft),transparent 45%)}
.card:hover{border-color:var(--line-2)}
.card:hover::before{opacity:1}
.grid .card:hover,.tile:hover{transform:translateY(-3px);box-shadow:var(--shadow-up)}
.card>h2:first-child{margin-top:0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px}
.grid .card{margin:0}

.chip{display:inline-flex;align-items:center;gap:5px;padding:2px 9px;border-radius:99px;background:var(--chip);color:var(--muted);font-size:11.5px;font-weight:500;white-space:nowrap;line-height:1.6}
.chip::before{content:"";width:5px;height:5px;border-radius:50%;background:currentColor;opacity:.6}
.chip.active,.chip.open,.chip.ready,.chip.planned{background:var(--accent-soft);color:var(--accent)}
.chip.posted,.chip.done,.chip.used,.chip.current{background:var(--ok-soft);color:var(--ok)}
.chip.replaced,.chip.dropped,.chip.parked,.chip.closed,.chip.history,.chip.paused,.chip.on.hold{opacity:.7}
.chip.me{background:var(--warn-soft);color:var(--warn)}
.chip.me::before{opacity:1;animation:pulse 1.8s ease-in-out infinite}
.flag{display:flex;gap:10px;align-items:flex-start;padding:12px 16px;border-radius:14px;background:var(--warn-soft);color:var(--warn);margin:0 0 8px;border:1px solid color-mix(in srgb,var(--warn) 22%,transparent)}
.flag .ic{margin-top:3px;width:16px;height:16px}
.flag a{color:inherit}
ul.rows{list-style:none;margin:0;padding:0}
ul.rows li{padding:11px 0;border-bottom:1px solid var(--line);transition:padding .25s}
ul.rows li:last-child{border-bottom:0}ul.rows li:first-child{padding-top:2px}
.row-head{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.date{color:var(--faint);font:500 12px/1.5 "JetBrains Mono",ui-monospace,monospace;min-width:86px;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
td.date{white-space:nowrap}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:11px 12px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr{transition:background .2s}tbody tr:hover{background:var(--chip)}
tbody tr:last-child td{border-bottom:0}
th{font-size:11px;color:var(--faint);font-weight:600;white-space:nowrap;letter-spacing:.08em;text-transform:uppercase}
td.n{text-align:right;font:500 13.5px/1.6 "JetBrains Mono",ui-monospace,monospace;white-space:nowrap}th.n{text-align:right}
tr.faded td{opacity:.5}
.card.scroll{padding:8px 10px}

/* documents */
.doc{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:clamp(22px,4vw,44px) clamp(20px,5vw,56px);box-shadow:var(--shadow);font-size:16px;line-height:1.75;max-width:820px}
.doc h1{font-size:30px}.doc h2{font:500 22px/1.3 "Fraunces",Georgia,serif;letter-spacing:-.01em;margin:36px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line);display:block}
.doc h3{font:600 16px/1.4 "Inter",sans-serif;margin:26px 0 8px}
.doc pre{background:var(--panel-2);padding:14px 16px;border-radius:12px;overflow:auto;border:1px solid var(--line);font-size:13px}
.doc code{font-family:"JetBrains Mono",ui-monospace,monospace;background:var(--chip);padding:1px 6px;border-radius:6px;font-size:.86em}.doc pre code{background:none;padding:0}
.doc blockquote{margin:16px 0;padding:4px 20px;border-left:2px solid var(--accent);color:var(--muted);font-style:italic}
.doc li.task{list-style:none;margin-left:-20px}
.doc table{font-size:14px;margin:8px 0}.doc hr{border:0;border-top:1px solid var(--line);margin:30px 0}
details{padding:8px 0;border-bottom:1px solid var(--line)}details:last-child{border-bottom:0}
summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:8px}
summary::before{content:"";width:6px;height:6px;border-right:1.5px solid var(--muted);border-bottom:1.5px solid var(--muted);transform:rotate(-45deg);transition:transform .25s}
details[open] summary::before{transform:rotate(45deg)}
details ul{margin:8px 0 4px;padding-left:22px}

/* conversation */
.convo{display:flex;flex-direction:column;gap:10px;padding:22px}
.msg{max-width:78%;padding:11px 15px;border-radius:18px;white-space:pre-wrap;line-height:1.55}
.msg.them{background:var(--chip);align-self:flex-start;border-bottom-left-radius:6px}
.msg.me{background:linear-gradient(135deg,#b54b22,#8f3713);color:#fff;align-self:flex-end;border-bottom-right-radius:6px;box-shadow:0 8px 20px -10px var(--glow)}
.msg.me .when{color:rgba(255,255,255,.75)}
.msg.note{align-self:center;background:none;border:1px dashed var(--line-2);color:var(--muted);font-size:13px;border-radius:12px}
.msg .when{display:block;font:500 10.5px/1.4 "JetBrains Mono",monospace;color:var(--faint);margin-bottom:3px;letter-spacing:.02em}

/* numbers */
.stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(138px,1fr));gap:10px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;box-shadow:var(--shadow)}
.stat b{display:block;font:500 26px/1.15 "Fraunces",Georgia,serif;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.stat span{font-size:12px;color:var(--muted)}
.filters{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 20px}
.filters a{padding:6px 14px;border-radius:99px;background:var(--panel);border:1px solid var(--line);color:var(--muted);font-size:13px;font-weight:500;transition:color .2s,border-color .2s,transform .2s,background-color .2s}
.filters a:hover{color:var(--ink);border-color:var(--line-2);transform:translateY(-1px)}
.filters a.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
iframe.view{width:100%;height:72vh;border:1px solid var(--line);border-radius:16px;background:#fff;box-shadow:var(--shadow)}
img.view{max-width:100%;border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow-up)}

.feed{position:relative;margin:0;padding:0;list-style:none}
.feed li{position:relative;display:grid;grid-template-columns:52px 1fr;gap:4px 14px;padding:12px 0;border-bottom:1px solid var(--line)}
.feed li:last-child{border-bottom:0}
.feed .time{font:500 12px/1.9 "JetBrains Mono",ui-monospace,monospace;color:var(--faint)}
.feed .what{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.feed .act{font-size:12px;font-weight:600;letter-spacing:.02em}
.feed .act.created{color:var(--ok)}.feed .act.updated{color:var(--accent)}
.feed .chg{grid-column:2;margin:2px 0 0;padding:0;list-style:none;font-size:13px;color:var(--muted)}
.feed .chg li{display:block;padding:2px 0;border:0}
.feed .chg b{font-weight:600;color:var(--ink)}
.feed .chg s{color:var(--faint)}
.day{position:sticky;top:0;z-index:2;margin:28px 0 10px;padding:6px 0;background:var(--bg);font:600 12px/1 "Inter",sans-serif;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}

/* tasks, projects, board, week, review */
.tline{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.tline .t{font-weight:500}
.meta{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:4px;font-size:12.5px;color:var(--muted)}
.meta .ic{width:13px;height:13px}
.chip.high{background:var(--warn-soft);color:var(--warn)}
.chip.low{opacity:.7}
.chip.late{background:var(--warn-soft);color:var(--warn)}
.chip.inbox{background:var(--chip)}.chip.doing{background:var(--accent-soft);color:var(--accent)}.chip.waiting{background:var(--ok-soft);color:var(--ok)}
.chip.todo{background:var(--chip);color:var(--ink)}
.sub-of{font-size:12px;color:var(--faint)}
.board{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(250px,1fr);gap:14px;overflow-x:auto;padding-bottom:10px;scroll-snap-type:x mandatory}
.col{background:var(--panel-2);border:1px solid var(--line);border-radius:18px;padding:12px;min-height:200px;scroll-snap-align:start}
.col>h3{display:flex;align-items:center;gap:8px;margin:2px 4px 12px;font:600 12.5px/1 "Inter",sans-serif;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.col>h3 .n{margin-left:auto;font:500 12px "JetBrains Mono",monospace;color:var(--faint)}
.col>h3 .dot{width:8px;height:8px;border-radius:50%}
.tcard{display:block;background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:11px 13px;margin:0 0 8px;box-shadow:var(--shadow);transition:transform .25s,border-color .25s;color:var(--ink)}
.tcard:hover{transform:translateY(-2px);border-color:var(--line-2)}
.tcard.p-high{border-left:3px solid var(--warn)}
.prog{height:6px;border-radius:99px;background:var(--chip);overflow:hidden;margin:12px 0 6px}
.prog i{display:block;height:100%;width:0;border-radius:inherit;background:linear-gradient(90deg,var(--accent-2),var(--accent));transition:width 1.2s cubic-bezier(.2,.7,.2,1) .2s}
.ready .prog i{width:var(--w)}
.pcard h2{font:500 21px/1.25 "Fraunces",Georgia,serif;letter-spacing:-.01em;margin:10px 0 6px;display:block}
.pcard h2 a{color:var(--ink)}
.pcard .next{margin-top:12px;padding-top:12px;border-top:1px solid var(--line);font-size:13.5px}
.pcard .next span{display:block;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--faint);margin-bottom:3px}
.outcome{font-size:14.5px;color:var(--muted)}
.days{display:flex;flex-direction:column;gap:10px}
.dayrow{display:grid;grid-template-columns:120px 1fr;gap:16px;padding:14px 18px;border-radius:16px;background:var(--panel);border:1px solid var(--line);box-shadow:var(--shadow)}
.dayrow.today{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft),var(--shadow)}
.dayrow.weekend{background:var(--panel-2)}
.dayrow .dname{font:500 20px/1.1 "Fraunces",Georgia,serif}
.dayrow .dname small{display:block;font:500 12px/1.6 "JetBrains Mono",monospace;color:var(--faint)}
.dayrow ul{list-style:none;margin:0;padding:0}
.dayrow li{padding:4px 0;display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.dayrow .empty{color:var(--faint);font-size:13px}
.kind{font-size:10.5px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;padding:2px 7px;border-radius:6px;background:var(--chip);color:var(--muted)}
.kind.post{background:var(--accent-soft);color:var(--accent)}.kind.person{background:var(--ok-soft);color:var(--ok)}
.rv-sec{display:grid;grid-template-columns:34px 1fr;gap:4px 12px;padding:16px 0;border-bottom:1px solid var(--line)}
.rv-sec:last-child{border-bottom:0}
.rv-sec .num{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font:600 13px "Inter";background:var(--warn-soft);color:var(--warn)}
.rv-sec.clear .num{background:var(--ok-soft);color:var(--ok)}
.rv-sec h3{margin:4px 0 2px;font:600 15px/1.3 "Inter",sans-serif}
.rv-sec p{margin:0;font-size:13px;color:var(--muted)}
.rv-sec ul{grid-column:2;margin:8px 0 0;padding:0;list-style:none}
.rv-sec ul li{padding:5px 0;font-size:14px}
@media (max-width:820px){.dayrow{grid-template-columns:1fr;gap:8px}.board{grid-auto-columns:82%}}

/* today */
.hero{position:relative;margin:0 0 34px}
.hero h1{font-size:clamp(38px,5.4vw,64px);line-height:1.02;margin:0 0 16px}
.hero h1 em{font-style:italic;color:var(--accent);font-variation-settings:"opsz" 144}
.north{display:inline-flex;align-items:center;gap:12px;padding:8px 16px 8px 8px;border-radius:99px;border:1px solid var(--line);background:var(--panel);box-shadow:var(--shadow);font-size:14px;color:var(--muted)}
.north span{padding:4px 10px;border-radius:99px;background:var(--accent-soft);color:var(--accent);font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase}
.north i{font:italic 500 16px/1 "Fraunces",Georgia,serif;color:var(--ink)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:0 0 30px}
.tile{position:relative;display:flex;flex-direction:column;gap:4px;padding:18px 20px;border-radius:18px;background:var(--panel);border:1px solid var(--line);
  box-shadow:var(--shadow);color:var(--ink);overflow:hidden;transition:transform .35s cubic-bezier(.2,.7,.2,1),box-shadow .35s,border-color .3s;isolation:isolate}
.tile:hover{color:var(--ink);border-color:var(--line-2)}
.tile::before{content:"";position:absolute;inset:0;z-index:-1;opacity:0;transition:opacity .4s;background:radial-gradient(260px circle at var(--mx,50%) var(--my,0%),var(--accent-soft),transparent 60%)}
.tile:hover::before{opacity:1}
.tile .big{font:400 46px/1 "Fraunces",Georgia,serif;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.tile .lbl{font-size:13px;color:var(--muted)}
.tile .ic{position:absolute;right:16px;top:16px;color:var(--faint);width:18px;height:18px;transition:color .3s,transform .4s}
.tile:hover .ic{color:var(--accent);transform:rotate(-8deg) scale(1.1)}
.tile.hot .big{color:var(--warn)}
.tile .ring{position:absolute;right:12px;top:12px;width:46px;height:46px}
.ring circle{fill:none;stroke-width:5}
.ring .track{stroke:var(--chip)}
.ring .bar{stroke:url(#rg);stroke-linecap:round;stroke-dasharray:157;stroke-dashoffset:157;transform:rotate(-90deg);transform-origin:center;transition:stroke-dashoffset 1.4s cubic-bezier(.2,.7,.2,1) .3s}
.ready .ring .bar{stroke-dashoffset:var(--off)}

/* entrance */
.rv{animation:rise .45s cubic-bezier(.2,.7,.2,1) both;animation-delay:calc(var(--i,0) * 35ms)}
@keyframes rise{from{opacity:0;transform:translateY(6px)}}

/* privacy mode: blur names and messages when showing the site to others */
:root[data-private] .priv{filter:blur(6px);transition:filter .3s;user-select:none}
:root[data-private] .priv:hover{filter:blur(6px)}
.priv{transition:filter .3s}

/* command palette */
.pal{position:fixed;inset:0;z-index:50;display:none;align-items:flex-start;justify-content:center;padding:14vh 16px 0;background:rgba(10,9,8,.45);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px)}
.pal.open{display:flex;animation:fade .2s ease}
@keyframes fade{from{opacity:0}}
.pal-box{width:min(620px,100%);background:var(--panel);border:1px solid var(--line-2);border-radius:20px;box-shadow:0 40px 80px -20px rgba(0,0,0,.5);overflow:hidden;animation:pop .28s cubic-bezier(.2,.8,.2,1.15)}
@keyframes pop{from{opacity:0;transform:translateY(-10px) scale(.97)}}
.pal-in{display:flex;align-items:center;gap:12px;padding:16px 20px;border-bottom:1px solid var(--line)}
.pal-in .ic{color:var(--accent)}
.pal-in input{flex:1;border:0;outline:0;background:none;color:var(--ink);font:inherit;font-size:17px}
.pal-list{max-height:52vh;overflow:auto;padding:8px}
.pal-list a{display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:12px;color:var(--ink);font-size:14.5px}
.pal-list a .ic{color:var(--muted)}
.pal-list a.sel{background:var(--accent-soft)}
.pal-list a.sel .ic{color:var(--accent)}
.pal-list a small{margin-left:auto;color:var(--faint);font-size:12px}
.pal-foot{display:flex;gap:14px;padding:10px 18px;border-top:1px solid var(--line);font-size:12px;color:var(--faint)}

@media (max-width:820px){
  .wrap{display:block}
  .topbar{display:flex;align-items:center;gap:10px;position:sticky;top:0;z-index:20;padding:12px 16px;background:var(--side);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border-bottom:1px solid var(--line)}
  .topbar .brand{margin:0}
  .topbar .icon-btn:first-of-type{margin-left:auto}
  aside{position:fixed;inset:0 auto 0 0;z-index:40;width:min(290px,86vw);transform:translateX(-102%);transition:transform .35s cubic-bezier(.2,.7,.2,1);background:var(--bg-2)}
  .nav-open aside{transform:none;box-shadow:30px 0 60px rgba(0,0,0,.35)}
  .scrim{position:fixed;inset:0;z-index:30;background:rgba(0,0,0,.4);opacity:0;pointer-events:none;transition:opacity .3s}
  .nav-open .scrim{opacity:1;pointer-events:auto}
  main{padding:26px 16px 60px}
  .msg{max-width:92%}
  .hero h1{font-size:40px}
  .tiles{gap:10px;grid-template-columns:repeat(2,1fr)}.tile{padding:14px 16px}.tile .big{font-size:36px}.tile .ring{width:38px;height:38px}
}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}.ring .bar{stroke-dashoffset:var(--off)}}
"""

HEAD_JS = """try{var t=localStorage.getItem('theme');if(t){document.documentElement.dataset.theme=t;document.documentElement.style.colorScheme=t;
document.documentElement.style.background=t==='dark'?'#0c0b0a':'#f4efe7'}
if(localStorage.getItem('private'))document.documentElement.setAttribute('data-private','')}catch(e){}"""

JS = r"""
(function(){
var d=document,root=d.documentElement,reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
var side=d.querySelector('aside');try{var st=+sessionStorage.getItem('sideScroll');if(side&&st)side.scrollTop=st}catch(e){}
addEventListener('pagehide',function(){try{sessionStorage.setItem('sideScroll',side?side.scrollTop:0)}catch(e){}});
function store(k,v){try{v?localStorage.setItem(k,v):localStorage.removeItem(k)}catch(e){}}
// theme
d.querySelectorAll('[data-act=theme]').forEach(function(b){b.addEventListener('click',function(){
  var cur=root.dataset.theme||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
  var n=cur==='dark'?'light':'dark';
  var go=function(){root.dataset.theme=n;root.style.colorScheme=n;root.style.background=''};
  d.startViewTransition&&!reduce?d.startViewTransition(go):go();store('theme',n)})});
// privacy mode
d.querySelectorAll('[data-act=private]').forEach(function(b){b.addEventListener('click',function(){
  var on=!root.hasAttribute('data-private');on?root.setAttribute('data-private',''):root.removeAttribute('data-private');store('private',on?'1':'')})});
// mobile menu
d.querySelectorAll('[data-act=menu]').forEach(function(b){b.addEventListener('click',function(){d.body.classList.toggle('nav-open')})});
// entrance: top-level blocks, then items inside lists and tables
var i=0;Array.prototype.forEach.call(d.querySelectorAll('main > *'),function(el){el.classList.add('rv');el.style.setProperty('--i',i++)});
d.querySelectorAll('.grid > *, .tiles > *, .stats > *').forEach(function(el,k){el.classList.add('rv');el.style.setProperty('--i',2+Math.min(k,10))});
d.querySelectorAll('ul.rows, tbody, .convo').forEach(function(list){
  Array.prototype.forEach.call(list.children,function(el,k){if(k<10){el.classList.add('rv');el.style.setProperty('--i',2+k)}})});
// count up
d.querySelectorAll('[data-count]').forEach(function(el){var t=+el.dataset.count;
  if(!t||reduce){el.textContent=t.toLocaleString();return}
  var s=null,dur=1100;function f(n){if(s===null)s=n;var p=Math.min(1,(n-s)/dur),e=1-Math.pow(1-p,4);el.textContent=Math.round(t*e).toLocaleString();if(p<1)requestAnimationFrame(f)}
  setTimeout(function(){requestAnimationFrame(f)},250)});
requestAnimationFrame(function(){setTimeout(function(){d.body.classList.add('ready')},60)});
// spotlight follows the pointer
d.addEventListener('pointermove',function(e){var c=e.target.closest&&e.target.closest('.card,.tile');if(!c)return;
  var r=c.getBoundingClientRect();c.style.setProperty('--mx',(e.clientX-r.left)+'px');c.style.setProperty('--my',(e.clientY-r.top)+'px')});
// command palette
var pal=d.getElementById('pal'),inp=d.getElementById('palIn'),list=d.getElementById('palList'),items=[],sel=0;
d.querySelectorAll('aside nav a').forEach(function(a){items.push({href:a.getAttribute('href'),label:a.textContent.trim(),icon:(a.querySelector('svg')||{}).outerHTML||'',kind:a.closest('.areas')?'Area':'Page'})});
function render(){var q=inp.value.trim().toLowerCase(),out=items.filter(function(x){return !q||x.label.toLowerCase().indexOf(q)>-1});
  if(q)out.push({href:'/search?q='+encodeURIComponent(inp.value.trim()),label:'Search everything for “'+inp.value.trim()+'”',icon:d.getElementById('icSearch').innerHTML,kind:'Enter'});
  sel=Math.min(sel,out.length-1);if(sel<0)sel=0;
  list.innerHTML=out.map(function(x,k){return '<a href="'+x.href+'" class="'+(k===sel?'sel':'')+'">'+x.icon+'<span></span><small>'+x.kind+'</small></a>'}).join('');
  Array.prototype.forEach.call(list.children,function(a,k){a.querySelector('span').textContent=out[k].label;a.addEventListener('mousemove',function(){if(sel!==k){sel=k;mark()}})})}
function mark(){Array.prototype.forEach.call(list.children,function(a,k){a.classList.toggle('sel',k===sel);if(k===sel)a.scrollIntoView({block:'nearest'})})}
function open(){pal.classList.add('open');inp.value='';sel=0;render();setTimeout(function(){inp.focus()},10)}
function close(){pal.classList.remove('open')}
d.querySelectorAll('[data-act=palette]').forEach(function(b){b.addEventListener('click',function(){d.body.classList.remove('nav-open');open()})});
pal.addEventListener('click',function(e){if(e.target===pal)close()});
inp.addEventListener('input',function(){sel=0;render()});
inp.addEventListener('keydown',function(e){var n=list.children.length;
  if(e.key==='ArrowDown'){sel=(sel+1)%n;mark();e.preventDefault()}
  else if(e.key==='ArrowUp'){sel=(sel-1+n)%n;mark();e.preventDefault()}
  else if(e.key==='Enter'&&n){location.href=list.children[sel].getAttribute('href')}});
d.addEventListener('keydown',function(e){var typing=/INPUT|TEXTAREA/.test((d.activeElement||{}).tagName||'');
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();pal.classList.contains('open')?close():open()}
  else if(e.key==='/'&&!typing){e.preventDefault();open()}
  else if(e.key==='Escape'){close();d.body.classList.remove('nav-open')}});
})();
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..600;1,9..144,400..600'
         '&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=block" rel="stylesheet">')


def page(title, body, path="/", sub="", hero=False, eyebrow="", private_title=False):
    con = brain.connect(readonly=True)
    areas = con.execute("SELECT * FROM areas ORDER BY sort").fetchall()
    con.close()

    def is_on(href):
        return (href == "/" and path == "/") or (href != "/" and path.startswith(href))

    nav = "".join(f'<h4>{name}</h4>' if href is None else
                  f'<a href="{href}" class="{"on" if is_on(href) else ""}">{icon(ic)}<span>{name}</span></a>' for href, name, ic in NAV)
    area_links = "".join(
        f'<a href="/area/{a["slug"]}" class="{"on" if path == "/area/" + a["slug"] else ""}"><i class="dot"></i>{esc(a["name"])}'
        f'{"" if a["status"] == "active" else " <span class=chip>" + esc(a["status"]) + "</span>"}</a>' for a in areas)
    section = next((name for href, name, _ in NAV if href and is_on(href)), "")
    eb = eyebrow or (section if section and section != title else "")
    head = "" if hero else (
        (f'<div class="eyebrow">{esc(eb)}</div>' if eb else "")
        + f'<h1 class="{"priv" if private_title else ""}">{esc(title)}</h1>' + (f'<p class="sub">{sub}</p>' if sub else ""))
    theme_btn = f'<button class="icon-btn" data-act="theme" title="Light or dark">{icon("moon")}</button>'
    priv_btn = f'<button class="icon-btn" id="privBtn" data-act="private" title="Privacy mode: blur names and messages">{icon("eye")}<span>Privacy</span></button>'
    brand = f'<a class="brand" href="/"><span class="orb"></span><span><b>My Work Brain</b><small>everything in one place</small></span></a>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark">
<title>{esc(title)} · My Work Brain</title><script>{HEAD_JS}</script><style>{CSS}</style>{FONTS}
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='9' fill='%23e98257'/%3E%3Ccircle cx='16' cy='16' r='5' fill='%23fff'/%3E%3C/svg%3E">
</head><body><div class="glow-2"></div>
<div class="topbar"><button class="icon-btn" data-act="menu" aria-label="Menu">{icon("menu")}</button>{brand}
<button class="icon-btn" data-act="palette" aria-label="Search">{icon("search")}</button>{theme_btn}</div>
<div class="scrim" data-act="menu"></div>
<div class="wrap"><aside>{brand}
<button class="kbar" data-act="palette">{icon("search")}<span>Search or jump to…</span><kbd>Ctrl K</kbd></button>
<nav>{nav}</nav><h4>Areas</h4><nav class="areas">{area_links}</nav>
<div class="side-foot">{theme_btn}{priv_btn}</div></aside>
<main>{head}{body}</main></div>
<div class="pal" id="pal" role="dialog" aria-label="Search"><div class="pal-box">
<div class="pal-in">{icon("search")}<input id="palIn" placeholder="Jump to a page, or type to search everything" autocomplete="off"><kbd>Esc</kbd></div>
<div class="pal-list" id="palList"></div>
<div class="pal-foot"><span><kbd>↑</kbd> <kbd>↓</kbd> move</span><span><kbd>Enter</kbd> open</span><span><kbd>/</kbd> or <kbd>Ctrl K</kbd> anywhere</span></div></div></div>
<template id="icSearch">{icon("search")}</template>
<svg width="0" height="0" style="position:absolute"><defs><linearGradient id="rg" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#f3a47e"/><stop offset="1" stop-color="#c2552c"/></linearGradient></defs></svg>
<script>{JS}</script></body></html>"""


def chip(v, cls=None):
    return f'<span class="chip {esc(cls if cls is not None else v)}">{esc(v)}</span>' if v else ""


def area_name(con):
    return {a["slug"]: a["name"] for a in con.execute("SELECT slug, name FROM areas")}


def area_filter(con, current, base):
    names = area_name(con)
    links = [f'<a href="{base}" class="{"" if current else "on"}">All</a>']
    links += [f'<a href="{base}?area={s}" class="{"on" if s == current else ""}">{esc(n)}</a>' for s, n in names.items()]
    return f'<div class="filters">{"".join(links)}</div>'


STATUS = {"inbox": "Inbox", "todo": "To do", "doing": "Doing", "waiting": "Waiting", "done": "Done", "dropped": "Dropped"}
STATUS_DOT = {"inbox": "var(--faint)", "todo": "var(--muted)", "doing": "var(--accent)", "waiting": "var(--ok)", "done": "var(--ok)"}
OPEN_SQL = brain.OPEN_SQL


def projects_by_id(con):
    return {r["id"]: r for r in con.execute("SELECT * FROM projects")}


def task_meta(t, projs, names, show_project=True, parents=None):
    """The small line under a task: priority, due, project, recurring, waiting."""
    today = dt.date.today().isoformat()
    bits = []
    if t["priority"] == "high":
        bits.append(chip("high", "high"))
    if t["due"] and t["status"] not in ("done", "dropped"):
        late = t["due"] < today
        bits.append(f'<span class="chip {"late" if late else ""}">{icon("clock")}{"overdue · " if late else ""}{fmt_date(t["due"])}</span>')
    if show_project and t["project_id"] in projs:
        bits.append(f'<a href="/projects/{t["project_id"]}">{icon("layers")}{esc(projs[t["project_id"]]["name"])}</a>')
    elif show_project:
        bits.append(chip(names.get(t["area"], t["area"]), ""))
    if t["recurring"]:
        bits.append(f'<span title="Repeats: {esc(t["recurring"])}">{icon("repeat")}{esc(t["recurring"].replace("weekly:", "every ").replace(",", ", "))}</span>')
    if t["status"] == "waiting":
        since = f' since {fmt_date(t["waiting_since"])}' if t["waiting_since"] else ""
        bits.append(f'<span>waiting{" on " + esc(t["waiting_on"]) if t["waiting_on"] else ""}{since}</span>')
    if t["status"] == "done" and t["done_date"]:
        bits.append(f'<span>done {fmt_date(t["done_date"])}</span>')
    parent = (parents or {}).get(t["parent_id"])
    head = f'<div class="sub-of">↳ {esc(parent["title"])}</div>' if parent else ""
    return head, f'<div class="meta">{" ".join(bits)}</div>' if bits else ""


def task_li(t, projs, names, show_project=True, parents=None):
    head, meta = task_meta(t, projs, names, show_project, parents)
    status = "" if t["status"] in ("todo",) else chip(STATUS.get(t["status"], t["status"]), t["status"])
    details = f'<div class="small muted">{esc(t["details"])}</div>' if t["details"] else ""
    return f'<li>{head}<div class="tline"><span class="t">{esc(t["title"])}</span>{status}</div>{meta}{details}</li>'


def project_stats(con, pid):
    rows = con.execute("SELECT status FROM tasks WHERE project_id=? AND status!='dropped'", (pid,)).fetchall()
    done = sum(1 for r in rows if r["status"] == "done")
    nxt = con.execute("SELECT * FROM tasks WHERE project_id=? AND status IN ('doing','todo') "
                      "ORDER BY status='doing' DESC, priority='high' DESC, priority='low', due='' , due, id LIMIT 1", (pid,)).fetchone()
    return done, len(rows), nxt


def post_label(p):
    return f'{("Post " + str(p["num"]) + " · ") if p["num"] else ""}{esc(p["title"])}'


# ---------- pages ----------

POSTS_PER_WEEK = 3


def view_today(con, q):
    b = brain.brief(con)
    names = area_name(con)
    now = dt.datetime.now()
    greet = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"
    t = b["today"]
    posted = sum(1 for p in b["week_posts"] if p["status"] == "posted")
    off = 157 * (1 - min(1, posted / POSTS_PER_WEEK))
    flags_n, tasks_n, move_n = len(b["flags"]), len(b["tasks"]), len(b["my_move"])

    hero = f"""<section class="hero"><div class="eyebrow">{t:%A}, {t.day} {t:%B %Y}</div>
<h1>{greet}, <em>{esc(OWNER)}.</em></h1>
<div class="north"><span>North star</span><i>Understand before you sell.</i></div></section>"""

    tiles = f"""<div class="tiles">
<a class="tile" href="/posts"><span class="big"><span data-count="{posted}">{posted}</span><span class="muted" style="font-size:.5em"> / {POSTS_PER_WEEK}</span></span>
<span class="lbl">posts out this week</span>
<svg class="ring" viewBox="0 0 60 60" style="--off:{off:.1f}"><circle class="track" cx="30" cy="30" r="25"/><circle class="bar" cx="30" cy="30" r="25"/></svg></a>
<a class="tile" href="/week">{icon("calendar")}<span class="big" data-count="{tasks_n}">{tasks_n}</span><span class="lbl">due in the next 7 days</span></a>
<a class="tile {"hot" if move_n else ""}" href="/people">{icon("people")}<span class="big" data-count="{move_n}">{move_n}</span><span class="lbl">{"person is" if move_n == 1 else "people are"} waiting on you</span></a>
<a class="tile {"hot" if flags_n else ""}" href="#look">{icon("flag")}<span class="big" data-count="{flags_n}">{flags_n}</span><span class="lbl">{"thing needs" if flags_n == 1 else "things need"} a look</span></a>
</div>"""

    parts = [hero, tiles]
    if b["flags"]:
        flags = "".join(
            f'<div class="flag">{icon("flag")}<a class="priv" href="/{tb}{"/" + str(rid) if rid and tb in ("posts", "people", "projects") else ""}">{esc(msg)}</a></div>' if tb in ("posts", "people", "weekly", "tasks", "projects", "review")
            else f'<div class="flag">{icon("flag")}<span class="priv">{esc(msg)}</span></div>' for tb, rid, msg in b["flags"])
        parts.append(f'<h2 id="look">{icon("flag")}Needs a look</h2><div>{flags}</div>')
    posts = "".join(
        f'<li><div class="row-head"><span class="date">{fmt_date(p["posted_date"] or p["planned_date"])}</span>'
        f'<a href="/posts/{p["id"]}">{post_label(p)}</a> {chip(p["status"])}</div></li>' for p in b["week_posts"]) or '<li class="muted">Nothing planned this week.</li>'
    projs = projects_by_id(con)
    tasks = "".join(task_li(x, projs, names) for x in [*b["doing"], *[x for x in b["tasks"] if x["status"] != "doing"]]) \
        or '<li class="muted">Nothing due in the next 7 days.</li>'
    proj_cards = []
    for pr in b["projects"]:
        done, total, nxt = project_stats(con, pr["id"])
        pct = round(100 * done / total) if total else 0
        proj_cards.append(f'<li><a href="/projects/{pr["id"]}"><strong>{esc(pr["name"])}</strong></a>'
                          f'<div class="prog" style="--w:{pct}%"><i></i></div>'
                          f'<div class="small muted">{done} of {total} done · next: {esc(nxt["title"]) if nxt else "<b>no next step</b>"}</div></li>')
    projects_html = "".join(proj_cards) or '<li class="muted">No active projects.</li>'
    people = "".join(
        f'<li><a class="priv" href="/people/{p["id"]}"><strong>{esc(p["name"])}</strong></a><div class="small muted priv">{esc(p["next_step"])}</div></li>'
        for p in b["my_move"]) or '<li class="muted">Nobody is waiting on you.</li>'
    log = "".join(
        f'<li><div class="row-head"><span class="date">{fmt_date(r["date"])}</span><span>{esc(r["title"])}</span></div></li>' for r in b["log"])
    decisions = "".join(
        f'<li><div class="row-head"><span class="date">{fmt_date(d["date"])}</span><span>{esc(d["decision"])}</span></div></li>' for d in b["decisions"])
    parts.append(f"""<div class="grid" style="margin-top:30px">
<div class="card"><h2>{icon("pen")}Posts this week</h2><ul class="rows">{posts}</ul></div>
<div class="card"><h2>{icon("check")}Doing and due this week</h2><ul class="rows">{tasks}</ul>
<p class="small muted" style="margin:10px 0 0">{len(b['undated'])} more open tasks with no date. <a href="/board">Open the board</a></p></div>
<div class="card"><h2>{icon("layers")}Projects</h2><ul class="rows">{projects_html}</ul></div>
<div class="card"><h2>{icon("people")}Your move</h2><ul class="rows">{people}</ul></div>
<div class="card"><h2>{icon("fork")}Latest decisions</h2><ul class="rows">{decisions}</ul></div>
</div><h2>{icon("log")}Latest log</h2><div class="card"><ul class="rows">{log}</ul></div>""")
    return page("Today", "".join(parts), "/", hero=True)


TABLE_NAMES = {"log": "Log", "decisions": "Decisions", "projects": "Projects", "tasks": "Tasks", "posts": "Posts", "ideas": "Ideas", "people": "People",
               "weekly": "Weekly numbers", "goals": "Goals", "rules": "How we work", "files": "Library", "areas": "Areas",
               "messages": "Messages"}


def record_link(table, rid, text):
    if table in ("posts", "people", "projects") and rid:
        href = f"/{table}/{rid}"
    elif table == "messages":
        href = "/people"
    elif table in ("areas", "files"):
        return text
    else:
        href = f"/{table}"
    return f'<a href="{href}">{text}</a>'


def view_activity(con, q):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='activity'").fetchone():
        return page("Activity", '<p class="muted">No activity yet. It starts with the next change Claude makes.</p>', "/activity")
    tbl = q.get("t", "")
    limit = 1000 if q.get("all") else 200
    rows = con.execute("SELECT * FROM activity WHERE (?='' OR tbl=?) ORDER BY at DESC, id DESC LIMIT ?", (tbl, tbl, limit)).fetchall()
    used = [r["tbl"] for r in con.execute("SELECT tbl, COUNT(*) n FROM activity GROUP BY tbl ORDER BY n DESC")]
    filt = '<div class="filters">' + f'<a href="/activity" class="{"" if tbl else "on"}">All</a>' + "".join(
        f'<a href="/activity?t={t}" class="{"on" if t == tbl else ""}">{TABLE_NAMES.get(t, t)}</a>' for t in used) + "</div>"
    out, day = [], None
    for r in rows:
        d = r["at"][:10]
        if d != day:
            if day:
                out.append("</ul></div>")
            day = d
            out.append(f'<div class="day">{fmt_date(d)}</div><div class="card"><ul class="feed">')
        priv = " priv" if r["tbl"] in ("people", "messages") else ""
        changes = json.loads(r["changes"] or "[]")
        chg = "".join(
            f'<li><b>{esc(c["f"].replace("_", " "))}</b>: '
            + (f'<s>{esc(c["from"]) or "empty"}</s> → ' if "from" in c else "")
            + f'{esc(c["to"]) or "empty"}</li>' for c in changes)
        out.append(
            f'<li><span class="time">{r["at"][11:16]}</span><div class="what"><span class="act {esc(r["action"])}">{esc(r["action"])}</span>'
            f'{chip(TABLE_NAMES.get(r["tbl"], r["tbl"]), "")}<span class="{priv.strip()}">{record_link(r["tbl"], r["record_id"], esc(r["label"]))}</span></div>'
            + (f'<ul class="chg{priv}">{chg}</ul>' if chg else "") + "</li>")
    if day:
        out.append("</ul></div>")
    more = "" if q.get("all") or len(rows) < limit else f'<p class="small"><a href="/activity?all=1{"&t=" + tbl if tbl else ""}">Show older activity</a></p>'
    return page("Activity", filt + ("".join(out) or '<p class="muted">Nothing yet.</p>') + more, "/activity",
                "Every change to the brain, recorded automatically. Separate from the Log, which is your own journal.")


def view_log(con, q):
    area = q.get("area", "")
    rows = con.execute("SELECT * FROM log WHERE (?='' OR area=?) ORDER BY date DESC, id DESC", (area, area)).fetchall()
    names = area_name(con)
    items = "".join(
        f'<li><div class="row-head"><span class="date">{fmt_date(r["date"])}</span><strong>{esc(r["title"])}</strong> {chip(names.get(r["area"], r["area"]), "")}</div>'
        + (f'<div class="small" style="margin-left:96px">{esc(r["details"])}</div>' if r["details"] else "")
        + (f'<div class="small" style="margin-left:96px">{link_for(r["link"])}</div>' if r["link"] else "") + "</li>" for r in rows)
    return page("Log", area_filter(con, area, "/log") + f'<div class="card"><ul class="rows">{items or "<li class=muted>Nothing yet.</li>"}</ul></div>',
                "/log", "Everything we did, newest first. Added when you say \"log this\".")


def view_decisions(con, q):
    area = q.get("area", "")
    rows = con.execute("SELECT * FROM decisions WHERE (?='' OR area=?) ORDER BY status='active' DESC, date DESC, id DESC", (area, area)).fetchall()
    names = area_name(con)
    by_id = {r["id"]: r for r in con.execute("SELECT id, date, decision FROM decisions")}
    items = []
    for r in rows:
        repl = by_id.get(r["replaced_by"])
        extra = f'<div class="small muted">Replaced on {fmt_date(repl["date"])} by: {esc(repl["decision"])}</div>' if repl else ""
        items.append(
            f'<tr class="{"" if r["status"] == "active" else "faded"}"><td class="date">{fmt_date(r["date"])}</td>'
            f'<td><strong>{esc(r["decision"])}</strong>' + (f'<div class="small muted">Why: {esc(r["why"])}</div>' if r["why"] else "")
            + extra + (f'<div class="small">{link_for(r["link"])}</div>' if r["link"] else "")
            + f'</td><td>{chip(names.get(r["area"], r["area"]), "")}</td><td>{chip(r["status"])}</td></tr>')
    body = area_filter(con, area, "/decisions") + f'<div class="card scroll"><table><thead><tr><th>Date</th><th>Decision</th><th>Area</th><th>Status</th></tr></thead><tbody>{"".join(items)}</tbody></table></div>'
    return page("Decisions", body, "/decisions", "What we decided, when and why. Active ones first. Only added after you say yes.")


def view_tasks(con, q):
    area = q.get("area", "")
    names = area_name(con)
    projs = projects_by_id(con)
    parents = {r["id"]: r for r in con.execute("SELECT id, title FROM tasks")}

    def rows(where, order):
        return con.execute(f"SELECT * FROM tasks WHERE (?='' OR area=?) AND {where} ORDER BY {order}", (area, area)).fetchall()

    groups = [
        ("Doing", rows("status='doing'", "priority='high' DESC, due='', due")),
        ("To do", rows("status='todo'", "due='', due, priority='high' DESC, priority='low', id")),
        ("Waiting on someone", rows("status='waiting'", "waiting_since")),
        ("Inbox", rows("status='inbox'", "id")),
        ("Done lately", rows("status IN ('done','dropped')", "done_date DESC, updated_at DESC LIMIT 25")),
    ]
    body = area_filter(con, area, "/tasks") + '<p class="small"><a href="/board">Board view</a> · <a href="/week">Week view</a></p>'
    for title, rs in groups:
        if rs or title in ("Doing", "To do"):
            body += (f'<h2>{title} <span class="muted small">({len(rs)})</span></h2><div class="card"><ul class="rows">'
                     + ("".join(task_li(t, projs, names, parents=parents) for t in rs) or "<li class=muted>None.</li>") + "</ul></div>")
    return page("Tasks", body, "/tasks", "Everything to do, by status. Overdue dates show in orange.")


def view_board(con, q):
    pid = q.get("p", "")
    names = area_name(con)
    projs = projects_by_id(con)
    parents = {r["id"]: r for r in con.execute("SELECT id, title FROM tasks")}
    active = [r for r in projs.values() if r["status"] == "active"]
    filt = '<div class="filters">' + f'<a href="/board" class="{"" if pid else "on"}">All</a>' + "".join(
        f'<a href="/board?p={r["id"]}" class="{"on" if str(r["id"]) == pid else ""}">{esc(r["name"])}</a>' for r in active) \
        + f'<a href="/board?p=none" class="{"on" if pid == "none" else ""}">No project</a></div>'
    where = "1" if not pid else ("project_id IS NULL" if pid == "none" else f"project_id={int(pid)}")
    cutoff = (dt.date.today() - dt.timedelta(days=14)).isoformat()
    cols = []
    for st in ("inbox", "todo", "doing", "waiting", "done"):
        extra = f" AND done_date>='{cutoff}'" if st == "done" else ""
        order = "done_date DESC" if st == "done" else "priority='high' DESC, due='', due, id"
        ts = con.execute(f"SELECT * FROM tasks WHERE status=? AND {where}{extra} ORDER BY {order}", (st,)).fetchall()
        cards = "".join(
            f'<div class="tcard p-{t["priority"]}">{task_meta(t, projs, names, not pid, parents)[0]}<div class="t">{esc(t["title"])}</div>'
            f'{task_meta(t, projs, names, not pid, parents)[1]}</div>' for t in ts)
        label = STATUS[st] + (" (14 days)" if st == "done" else "")
        cols.append(f'<div class="col"><h3><i class="dot" style="background:{STATUS_DOT[st]}"></i>{label}<span class="n">{len(ts)}</span></h3>'
                    f'{cards or "<p class='small muted' style='margin:4px'>Empty</p>"}</div>')
    return page("Board", filt + f'<div class="board">{"".join(cols)}</div>', "/board",
                "Every task as a card, by status. Filter by project.")


def view_projects(con, q):
    names = area_name(con)
    goals = {r["id"]: r for r in con.execute("SELECT * FROM goals")}
    out = {"active": [], "paused": [], "done": [], "dropped": []}
    for pr in con.execute("SELECT * FROM projects ORDER BY sort, id"):
        done, total, nxt = project_stats(con, pr["id"])
        pct = round(100 * done / total) if total else 0
        goal = goals.get(pr["goal_id"])
        out.setdefault(pr["status"], []).append(
            f'<div class="card pcard"><div class="row-head">{chip(names.get(pr["area"], pr["area"]), "")} {chip(pr["status"])}'
            + (f' <span class="chip">{icon("clock")}due {fmt_date(pr["due"])}</span>' if pr["due"] else "") + '</div>'
            f'<h2><a href="/projects/{pr["id"]}">{esc(pr["name"])}</a></h2>'
            + (f'<div class="outcome">{esc(pr["outcome"])}</div>' if pr["outcome"] else "")
            + f'<div class="prog" style="--w:{pct}%"><i></i></div><div class="small muted">{done} of {total} tasks done · {pct}%</div>'
            + (f'<div class="small muted" style="margin-top:4px">{icon("target")} {esc(goal["goal"])}</div>' if goal else "")
            + (f'<div class="next"><span>Next step</span>{esc(nxt["title"])}</div>' if nxt else
               '<div class="next" style="color:var(--warn)"><span>Next step</span>None yet: this project is stuck</div>' if pr["status"] == "active" else "")
            + "</div>")
    body = ""
    for st, title in (("active", "Active"), ("paused", "Paused"), ("done", "Done"), ("dropped", "Dropped")):
        if out.get(st):
            body += f'<h2>{title}</h2><div class="grid">{"".join(out[st])}</div>'
    return page("Projects", body or '<p class="muted">No projects yet.</p>', "/projects",
                "Things that finish. Each one has an outcome, a progress bar and a next step.")


def view_project(con, pid):
    pr = con.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not pr:
        return None
    names = area_name(con)
    projs = projects_by_id(con)
    parents = {r["id"]: r for r in con.execute("SELECT id, title FROM tasks")}
    goal = con.execute("SELECT * FROM goals WHERE id=?", (pr["goal_id"],)).fetchone() if pr["goal_id"] else None
    done, total, nxt = project_stats(con, pid)
    pct = round(100 * done / total) if total else 0
    body = (f'<p>{chip(names.get(pr["area"], pr["area"]), "")} {chip(pr["status"])}'
            + (f' <span class="chip">{icon("clock")}due {fmt_date(pr["due"])}</span>' if pr["due"] else "") + "</p>"
            + f'<div class="card"><span class="small muted">Done looks like</span><div style="font-size:16px;margin-top:4px"><strong>{esc(pr["outcome"]) or "Not written yet"}</strong></div>'
            + f'<div class="prog" style="--w:{pct}%"><i></i></div><div class="small muted">{done} of {total} tasks done · {pct}%</div>'
            + (f'<div class="small muted" style="margin-top:6px">{icon("target")} Moves the goal: <a href="/goals">{esc(goal["goal"])}</a></div>' if goal else "")
            + (f'<p class="small muted" style="margin:8px 0 0">{esc(pr["note"])}</p>' if pr["note"] else "") + "</div>")
    for st in ("doing", "todo", "waiting", "inbox", "done", "dropped"):
        ts = con.execute("SELECT * FROM tasks WHERE project_id=? AND status=? ORDER BY priority='high' DESC, priority='low', due='', due, id",
                         (pid, st)).fetchall()
        if ts:
            body += (f'<h2>{STATUS[st]} <span class="muted small">({len(ts)})</span></h2><div class="card"><ul class="rows">'
                     + "".join(task_li(t, projs, names, False, parents) for t in ts) + "</ul></div>")
    return page(pr["name"], body, "/projects", eyebrow="Project")


def view_week(con, q):
    t = dt.date.today()
    start = t - dt.timedelta(days=t.weekday())
    days = [start + dt.timedelta(days=i) for i in range(14)]
    end = days[-1].isoformat()
    names = area_name(con)
    projs = projects_by_id(con)
    items = {}

    def add(day, html):
        items.setdefault(day, []).append(html)

    for r in con.execute(f"SELECT * FROM tasks WHERE status IN {OPEN_SQL} AND due!='' AND due<=? ORDER BY priority='high' DESC", (end,)):
        day = r["due"] if r["due"] >= t.isoformat() else "overdue"
        _, meta = task_meta(r, projs, names)
        add(day, f'<li><span class="kind">task</span><span>{esc(r["title"])}</span>{meta}</li>')
    for r in con.execute("SELECT * FROM posts WHERE COALESCE(NULLIF(posted_date,''), planned_date) BETWEEN ? AND ?",
                         (start.isoformat(), end)):
        day = r["posted_date"] or r["planned_date"]
        add(day, f'<li><span class="kind post">post</span><a href="/posts/{r["id"]}">{post_label(r)}</a> {chip(r["status"])}</li>')
    for r in con.execute("SELECT * FROM people WHERE ball!='closed' AND due!='' AND due<=?", (end,)):
        day = r["due"] if r["due"] >= t.isoformat() else "overdue"
        who = "your move" if r["ball"] == "me" else "check if they replied"
        add(day, f'<li><span class="kind person">person</span><a class="priv" href="/people/{r["id"]}">{esc(r["name"])}</a><span class="small muted">{who}</span></li>')
    body = ""
    if items.get("overdue"):
        body += f'<h2>{icon("flag")}Overdue</h2><div class="card"><ul class="rows">{"".join(items["overdue"])}</ul></div>'
    for wk, label in ((days[:7], "This week"), (days[7:], "Next week")):
        rows = []
        for d in wk:
            cls = "today" if d == t else ("weekend" if d.weekday() >= 5 else "")
            its = items.get(d.isoformat(), [])
            rows.append(f'<div class="dayrow {cls}"><div class="dname">{d:%a}<small>{d.day} {d:%b}{" · today" if d == t else ""}</small></div>'
                        f'<ul>{"".join(its) or "<li class=empty>Nothing planned</li>"}</ul></div>')
        body += f'<h2>{icon("calendar")}{label}</h2><div class="days">{"".join(rows)}</div>'
    return page("Week", body, "/week", "Tasks, posts and follow-ups, day by day for two weeks.")


def view_review(con, q):
    t = dt.date.today()
    names = area_name(con)
    projs = projects_by_id(con)
    secs = []

    def sec(title, hint, lis):
        n = len(lis)
        secs.append(f'<div class="rv-sec {"clear" if not n else ""}"><span class="num">{icon("ok") if not n else n}</span>'
                    f'<div><h3>{title}</h3><p>{hint if n else "All clear."}</p></div>'
                    + (f'<ul>{"".join(lis)}</ul>' if n else "") + "</div>")

    def tl(r, extra=""):
        _, meta = task_meta(r, projs, names)
        return f'<li><strong>{esc(r["title"])}</strong>{extra}{meta}</li>'

    sec("Inbox", "Give each one a project, a priority or a date, or drop it.",
        [tl(r) for r in con.execute("SELECT * FROM tasks WHERE status='inbox' ORDER BY id")])
    sec("Overdue", "Do it, move the date, or drop it.",
        [tl(r) for r in con.execute(f"SELECT * FROM tasks WHERE status IN {OPEN_SQL} AND due!='' AND due<? ORDER BY due", (t.isoformat(),))])
    sec("Waiting on someone", "Chase, or let go.",
        [tl(r) for r in con.execute("SELECT * FROM tasks WHERE status='waiting' ORDER BY waiting_since")])
    stuck = []
    for pr in con.execute("SELECT * FROM projects WHERE status='active' ORDER BY sort, id"):
        if not con.execute("SELECT 1 FROM tasks WHERE project_id=? AND status IN ('todo','doing','waiting')", (pr["id"],)).fetchone():
            stuck.append(f'<li><a href="/projects/{pr["id"]}"><strong>{esc(pr["name"])}</strong></a> has no next step</li>')
    sec("Projects with no next step", "Every active project needs one clear next step.", stuck)
    old = (t - dt.timedelta(days=7)).isoformat()
    sec("Doing for over a week", "Still really in progress? Split it, or move it back to To do.",
        [tl(r) for r in con.execute("SELECT * FROM tasks WHERE status='doing' AND updated_at<?", (old,))])
    sec("Loose tasks", "No project and no date. Give them a home, or drop them.",
        [tl(r) for r in con.execute("SELECT * FROM tasks WHERE status='todo' AND project_id IS NULL AND due='' ORDER BY area, id")])
    lonely = [f'<li><strong>{esc(g["goal"])}</strong> <span class="small muted">({esc(names.get(g["area"], g["area"]))})</span></li>'
              for g in con.execute("SELECT * FROM goals WHERE status='active'")
              if not con.execute("SELECT 1 FROM projects WHERE goal_id=? AND status='active'", (g["id"],)).fetchone()
              and not con.execute(f"SELECT 1 FROM tasks WHERE area=? AND status IN {OPEN_SQL}", (g["area"],)).fetchone()]
    sec("Goals nothing is moving", "A goal with no active project only moves by luck.", lonely)
    sec("People waiting on you", "Reply, or set a date.",
        [f'<li><a class="priv" href="/people/{r["id"]}"><strong>{esc(r["name"])}</strong></a><div class="small muted priv">{esc(r["next_step"])}</div></li>'
         for r in con.execute("SELECT * FROM people WHERE ball='me'")])
    last = con.execute("SELECT MAX(date) FROM weekly").fetchone()[0]
    gap = (t - dt.date.fromisoformat(last)).days if last else None
    sec("Weekly numbers", "Take them from LinkedIn Analytics on Sunday.",
        [] if gap is not None and gap <= 7 else [f'<li>Last taken {fmt_date(last)} ({gap} days ago)</li>'])
    clear = sum(1 for x in secs if 'rv-sec clear' in x)
    body = f'<div class="card"><p class="small muted" style="margin:0 0 4px">{clear} of {len(secs)} clear</p>{"".join(secs)}</div>'
    return page("Weekly review", body, "/review", "Every Sunday, 5 minutes: go down this list together and nothing slips.")


METRICS = [("impressions", "Impressions"), ("reached", "Reached"), ("out_network_pct", "Out of network %"),
           ("reactions", "Reactions"), ("comments", "Comments"), ("reposts", "Reposts"), ("saves", "Saves"),
           ("sends", "Sends"), ("profile_views", "Profile views"), ("followers", "Followers"), ("dms", "DMs"),
           ("connections", "New connections")]


def view_posts(con, q):
    status = q.get("status", "")
    rows = con.execute(
        "SELECT * FROM posts WHERE (?='' OR status=?) ORDER BY COALESCE(NULLIF(posted_date,''), NULLIF(planned_date,''), '9999') DESC, num DESC",
        (status, status)).fetchall()
    filt = '<div class="filters">' + "".join(
        f'<a href="/posts{"?status=" + s if s else ""}" class="{"on" if s == status else ""}">{s.title() or "All"}</a>'
        for s in ["", "posted", "ready", "draft", "on hold"]) + "</div>"
    trs = "".join(
        f'<tr><td class="date">{fmt_date(p["posted_date"] or p["planned_date"])}</td><td><a href="/posts/{p["id"]}">{post_label(p)}</a></td>'
        f'<td>{esc(p["type"])}</td><td>{chip(p["status"])}</td><td class="n">{num(p["impressions"])}</td>'
        f'<td class="n">{num(p["out_network_pct"]) + "%" if p["out_network_pct"] is not None else "–"}</td>'
        f'<td class="n">{num(p["reactions"])}</td><td class="n">{num(p["comments"])}</td><td class="n">{num(p["profile_views"])}</td></tr>'
        for p in rows)
    body = filt + f'''<div class="card scroll"><table><thead><tr><th>Date</th><th>Post</th><th>Type</th><th>Status</th>
<th class="n">Impr.</th><th class="n">Out of net.</th><th class="n">React.</th><th class="n">Comm.</th><th class="n">Profile views</th></tr></thead>
<tbody>{trs}</tbody></table></div><p class="small muted">Numbers are taken about 24 hours after posting.</p>'''
    return page("Posts", body, "/posts", "Every post with its numbers. Click one to read it.")


def view_post(con, pid):
    p = con.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
    if not p:
        return None
    stats = "".join(f'<div class="stat"><b>{num(p[k])}{"%" if k == "out_network_pct" and p[k] is not None else ""}</b><span>{label}</span></div>'
                    for k, label in METRICS if p[k] is not None)
    info = [f'{chip(p["status"])} {chip(p["type"], "")}',
            f'<span class="muted">Posted {fmt_date(p["posted_date"])}</span>' if p["posted_date"] else
            (f'<span class="muted">Planned {fmt_date(p["planned_date"])}</span>' if p["planned_date"] else "")]
    body = f'<p>{" ".join(info)}</p>'
    if p["point"]:
        body += f'<div class="card"><span class="small muted">The point</span><div><strong>{esc(p["point"])}</strong></div></div>'
    if stats:
        body += f'<h2>Numbers{" (taken at " + esc(p["metrics_taken"]) + ")" if p["metrics_taken"] else ""}</h2><div class="stats">{stats}</div>'
    if p["audience"]:
        body += f'<p class="small"><span class="muted">Audience:</span> {esc(p["audience"])}</p>'
    if p["note"]:
        body += f'<p class="small"><span class="muted">Note:</span> {esc(p["note"])}</p>'
    ideas = con.execute("SELECT * FROM ideas WHERE post_id=?", (pid,)).fetchall()
    if ideas:
        body += '<p class="small"><span class="muted">From the idea:</span> ' + "; ".join(esc(i["idea"]) for i in ideas) + "</p>"
    f = safe_path(p["file"]) if p["file"] else None
    if f and f.exists():
        body += f'<h2>The post <span class="small muted" style="font-weight:400">· {link_for(p["file"])}</span></h2>'
        body += f'<div class="doc">{md_to_html(f.read_text(encoding="utf-8", errors="replace"), Path(p["file"]).parent.as_posix())}</div>'
    return page(html.unescape(post_label(p)), body, "/posts")


def view_ideas(con, q):
    status = q.get("status", "")
    rows = con.execute("SELECT i.*, p.num, p.title AS ptitle FROM ideas i LEFT JOIN posts p ON p.id=i.post_id "
                       "WHERE (?='' OR i.status=?) ORDER BY CASE i.status WHEN 'planned' THEN 0 WHEN 'open' THEN 1 WHEN 'used' THEN 2 ELSE 3 END, i.date DESC",
                       (status, status)).fetchall()
    filt = '<div class="filters">' + "".join(
        f'<a href="/ideas{"?status=" + s if s else ""}" class="{"on" if s == status else ""}">{s.title() or "All"}</a>'
        for s in ["", "planned", "open", "used", "parked"]) + "</div>"
    items = "".join(
        f'<li><div class="row-head">{chip(r["status"])} <span>{esc(r["idea"])}</span></div>'
        f'<div class="small muted">{fmt_date(r["date"])}{" · " if r["date"] and r["source"] else ""}{esc(r["source"])}'
        + (f' · became <a href="/posts/{r["post_id"]}">{"post " + str(r["num"]) if r["num"] else esc(r["ptitle"])}</a>' if r["post_id"] else "")
        + (f' · {esc(r["note"])}' if r["note"] else "") + "</div></li>" for r in rows)
    return page("Ideas", filt + f'<div class="card"><ul class="rows">{items}</ul></div>', "/ideas",
                "Post seeds and other ideas. Planned first, then open, used and parked.")


KIND = {"lead": "lead", "partner": "partner", "job": "job contact", "pitch": "pitch", "friend": "friend", "other": "other"}


def view_people(con, q):
    rows = con.execute("SELECT * FROM people ORDER BY ball='me' DESC, ball='closed', last_contact DESC").fetchall()
    trs = "".join(
        f'<tr class="{"faded" if r["ball"] == "closed" else ""}"><td><a class="priv" href="/people/{r["id"]}"><strong>{esc(r["name"])}</strong></a>'
        f'<div class="small muted priv">{esc((r["who"] or "")[:110])}</div></td><td>{chip(KIND.get(r["kind"], r["kind"]), "")}</td>'
        f'<td>{chip("your move", "me") if r["ball"] == "me" else chip("waiting on them", "") if r["ball"] == "them" else chip("closed")}</td>'
        f'<td class="date">{fmt_date(r["last_contact"])}</td><td class="small priv">{esc(r["next_step"])}</td></tr>' for r in rows)
    body = f'<div class="card scroll"><table><thead><tr><th>Person</th><th>Kind</th><th>Ball</th><th>Last contact</th><th>Next step</th></tr></thead><tbody>{trs}</tbody></table></div>'
    return page("People", body, "/people", "My own network: DMs and connections. Your move first.")


def view_person(con, pid):
    r = con.execute("SELECT * FROM people WHERE id=?", (pid,)).fetchone()
    if not r:
        return None
    log = con.execute("SELECT * FROM messages WHERE person_id=? ORDER BY date, id", (pid,)).fetchall()
    msgs = "".join(f'<div class="msg {esc(e["by"])}"><span class="when">{fmt_date(e["date"])} · {esc(e["by"])}</span>{esc(e["text"])}</div>'
                   for e in log)
    facts = [("Who", esc(r["who"])), ("What they want", esc(r["want"])), ("Next step", f'<strong>{esc(r["next_step"])}</strong>' if r["next_step"] else ""),
             ("Follow-up date", fmt_date(r["due"])), ("Channel", esc(r["channel"])), ("First message by", "them" if r["first_by"] == "them" else "me"),
             ("Kind", esc(KIND.get(r["kind"], r["kind"]))), ("Outcome", esc(r["outcome"])),
             ("Link", link_for(r["link"])), ("Notes", esc(r["notes"]))]
    rows = "".join(f'<tr><th>{k}</th><td>{v}</td></tr>' for k, v in facts if v)
    ball = chip("your move", "me") if r["ball"] == "me" else chip("waiting on them", "") if r["ball"] == "them" else chip("closed")
    body = f'<p>{ball} <span class="muted small">Last contact {fmt_date(r["last_contact"])}</span></p><div class="card priv"><table>{rows}</table></div>'
    body += f'<h2>Conversation</h2><div class="card convo priv">{msgs or "<span class=muted>No messages saved.</span>"}</div>'
    return page(r["name"], body, "/people", private_title=True)


def view_weekly(con, q):
    rows = con.execute("SELECT * FROM weekly ORDER BY date DESC").fetchall()
    trs = "".join(f'<tr><td class="date">{fmt_date(r["date"])}</td><td class="n">{num(r["followers"])}</td><td class="n">{num(r["impressions_7d"])}</td>'
                  f'<td class="n">{num(r["profile_viewers_90d"])}</td><td class="n">{num(r["search_appearances"])}</td><td class="small">{esc(r["note"])}</td></tr>' for r in rows)
    body = f'''<div class="card scroll"><table><thead><tr><th>Date</th><th class="n">Followers</th><th class="n">Impressions (7 days)</th>
<th class="n">Profile viewers (90 days)</th><th class="n">Search appearances</th><th>Note</th></tr></thead><tbody>{trs}</tbody></table></div>
<p class="small muted">From LinkedIn Analytics → Overview, taken on Sundays.</p>'''
    return page("Weekly numbers", body, "/weekly", "The LinkedIn dashboard, week by week.")


def view_goals(con, q):
    names = area_name(con)
    rows = con.execute("SELECT * FROM goals ORDER BY status='active' DESC, id").fetchall()
    cards = "".join(
        f'<div class="card"><div class="row-head">{chip(names.get(g["area"], g["area"]), "")} {chip(g["status"])}</div>'
        f'<h2 style="margin:8px 0 4px">{esc(g["goal"])}</h2>' + (f'<div><strong>{esc(g["target"])}</strong></div>' if g["target"] else "")
        + (f'<div class="small muted">By {fmt_date(g["by_date"])}</div>' if g["by_date"] else "")
        + (f'<p class="small muted" style="margin:6px 0 0">{esc(g["note"])}</p>' if g["note"] else "") + "</div>" for g in rows)
    north = con.execute("SELECT decision FROM decisions WHERE decision LIKE 'North star%' AND status='active'").fetchone()
    top = f'<div class="card" style="border-color:var(--accent)"><span class="small muted">North star</span><h2 style="margin:4px 0 0">Understand before you sell.</h2></div>' if north else ""
    return page("Goals", top + f'<div class="grid">{cards}</div>', "/goals", "Where I'm going.")


def view_rules(con, q):
    names = area_name(con)
    out = []
    for slug, name in names.items():
        rs = con.execute("SELECT * FROM rules WHERE area=? AND status='active' ORDER BY id", (slug,)).fetchall()
        if rs:
            items = "".join(f'<li>{esc(r["rule"])}' + (f'<div class="small muted">Why: {esc(r["why"])}</div>' if r["why"] else "") + "</li>" for r in rs)
            out.append(f'<h2>{esc(name)}</h2><div class="card"><ul class="rows">{items}</ul></div>')
    out.append('<p class="small muted">The full writing rules are in the <a href="/file?p=writing-guide.md">writing guide</a>.</p>')
    return page("How we work", "".join(out), "/rules", "The rules Claude follows when working with me.")


def view_files(con, q):
    names = area_name(con)
    described = {r["path"]: r for r in con.execute("SELECT * FROM files")}
    cards = []
    for status, title in (("current", "Current"), ("history", "History"), ("parked", "Parked")):
        rs = [r for r in described.values() if r["status"] == status]
        if rs:
            items = "".join(f'<li><a href="/file?p={quote(r["path"])}"><strong>{esc(r["title"])}</strong></a> {chip(names.get(r["area"], r["area"]), "")}'
                            f'<div class="small muted">{esc(r["description"])}</div></li>' for r in rs)
            cards.append(f'<h2>{title}</h2><div class="card"><ul class="rows">{items}</ul></div>')
    tree = {}
    for f in sorted(FILES.rglob("*")):
        if f.is_file():
            rel = f.relative_to(FILES).as_posix()
            tree.setdefault(str(Path(rel).parent.as_posix()), []).append(rel)
    folders = "".join(
        f'<details {"open" if folder == "." else ""}><summary><strong>{esc("files" if folder == "." else folder)}</strong> <span class="muted small">({len(fs)})</span></summary>'
        f'<ul>{"".join(f"<li><a href=/file?p={quote(x)}>{esc(Path(x).name)}</a></li>" for x in fs)}</ul></details>'
        for folder, fs in sorted(tree.items()))
    cards.append(f'<h2>All files</h2><div class="card">{folders}</div>')
    return page("Library", "".join(cards), "/files", "Every file. Click to open it here.")


def view_area(con, slug):
    a = con.execute("SELECT * FROM areas WHERE slug=?", (slug,)).fetchone()
    if not a:
        return None
    parts = [f'<p>{chip(a["status"])}</p><div class="card">{esc(a["summary"])}</div>']
    ds = con.execute("SELECT * FROM decisions WHERE area=? AND status='active' ORDER BY date DESC", (slug,)).fetchall()
    ts = con.execute(f"SELECT * FROM tasks WHERE area=? AND status IN {OPEN_SQL} ORDER BY due='' , due", (slug,)).fetchall()
    gs = con.execute("SELECT * FROM goals WHERE area=? AND status='active'", (slug,)).fetchall()
    ls = con.execute("SELECT * FROM log WHERE area=? ORDER BY date DESC, id DESC LIMIT 15", (slug,)).fetchall()
    fs = con.execute("SELECT * FROM files WHERE area=?", (slug,)).fetchall()
    rs = con.execute("SELECT * FROM rules WHERE area=? AND status='active'", (slug,)).fetchall()

    def section(title, rows, fn, more=""):
        if rows:
            parts.append(f'<h2>{title}</h2><div class="card"><ul class="rows">{"".join(fn(r) for r in rows)}</ul>{more}</div>')

    section("Goals", gs, lambda g: f'<li><strong>{esc(g["goal"])}</strong> <span class="muted">{esc(g["target"])}</span></li>')
    section("Open tasks", ts, lambda t: f'<li><div class="row-head"><span class="date">{fmt_date(t["due"])}</span>{esc(t["title"])}</div></li>',
            f'<p class="small"><a href="/tasks?area={slug}">All tasks</a></p>')
    section("Active decisions", ds, lambda d: f'<li><div class="row-head"><span class="date">{fmt_date(d["date"])}</span>{esc(d["decision"])}</div></li>',
            f'<p class="small"><a href="/decisions?area={slug}">All decisions</a></p>')
    section("Files", fs, lambda f: f'<li><a href="/file?p={quote(f["path"])}">{esc(f["title"])}</a> <span class="small muted">{esc(f["description"])}</span></li>')
    section("Rules", rs, lambda r: f'<li>{esc(r["rule"])}</li>')
    section("Latest log", ls, lambda r: f'<li><div class="row-head"><span class="date">{fmt_date(r["date"])}</span>{esc(r["title"])}</div></li>',
            f'<p class="small"><a href="/log?area={slug}">Full log</a></p>')
    if slug == "linkedin":
        parts.insert(1, '<p class="small"><a href="/posts">Posts</a> · <a href="/ideas">Ideas</a> · <a href="/people">People</a> · <a href="/weekly">Weekly numbers</a></p>')
    return page(a["name"], "".join(parts), "/area/" + slug)


def view_search(con, q):
    text = q.get("q", "").strip()
    if not text:
        return page("Search", '<p class="muted">Type in the search box.</p>', "/search")
    hits, file_hits = brain.search(con, text)
    names = {"log": "Log", "decisions": "Decisions", "projects": "Projects", "tasks": "Tasks", "posts": "Posts", "ideas": "Ideas", "people": "People",
             "weekly": "Weekly numbers", "goals": "Goals", "rules": "How we work", "files": "Library", "areas": "Areas",
             "messages": "Messages"}
    href = {"posts": "/posts/{id}", "people": "/people/{id}", "projects": "/projects/{id}", "files": None, "areas": None}
    groups = {}
    for table, row in hits:
        groups.setdefault(table, []).append(row)
    out = []
    for table, rows in groups.items():
        items = []
        for row in rows:
            lbl = esc(brain.label(table, row))
            if table == "files":
                link = f'/file?p={quote(row["path"])}'
            elif table == "areas":
                link = f'/area/{row["slug"]}'
            elif table == "messages":
                link = f'/people/{row["person_id"]}'
            elif href.get(table):
                link = href[table].format(id=row["id"])
            else:
                link = f'/{table}'
            items.append(f'<li><a class="{"priv" if table in ("people", "messages") else ""}" href="{link}">{lbl}</a></li>')
        out.append(f'<h2>{names[table]} <span class="muted small">({len(rows)})</span></h2><div class="card"><ul class="rows">{"".join(items)}</ul></div>')
    if file_hits:
        items = "".join(f'<li><a href="/file?p={quote(p)}"><strong>{esc(p)}</strong></a>'
                        + "".join(f'<div class="small muted">line {n}: {esc(t[:180])}</div>' for n, t in lines[:4]) + "</li>" for p, lines in file_hits)
        out.append(f'<h2>In files <span class="muted small">({len(file_hits)})</span></h2><div class="card"><ul class="rows">{items}</ul></div>')
    return page(f'Search: {text}', "".join(out) or '<p class="muted">Nothing found.</p>', "/search")


def safe_path(rel):
    target = (FILES / unquote(rel)).resolve()
    if target != FILES and FILES not in target.parents:
        return None
    return target


def view_file(con, q):
    rel = q.get("p", "")
    f = safe_path(rel)
    if not f or not f.exists() or not f.is_file():
        return page("File not found", f'<p class="muted">{esc(rel)} isn\'t in the files folder.</p>', "/files")
    ext = f.suffix.lower()
    raw = f"/raw/{quote(rel)}"
    if ext == ".md":
        body = f'<div class="doc">{md_to_html(f.read_text(encoding="utf-8", errors="replace"), Path(rel).parent.as_posix())}</div>'
    elif ext in (".html", ".htm"):
        body = f'<p class="small"><a href="{raw}" target="_blank">Open on its own</a></p><iframe class="view" src="{raw}"></iframe>'
    elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"):
        body = f'<img class="view" src="{raw}" alt="{esc(f.name)}">'
    else:
        body = f'<div class="doc"><pre><code>{esc(f.read_text(encoding="utf-8", errors="replace"))}</code></pre></div>'
    return page(f.name, body, "/files", f'<span class="small">{esc(rel)}</span>')


ROUTES = {"/": view_today, "/week": view_week, "/board": view_board, "/projects": view_projects, "/review": view_review, "/activity": view_activity, "/log": view_log, "/decisions": view_decisions, "/tasks": view_tasks, "/posts": view_posts,
          "/ideas": view_ideas, "/people": view_people, "/weekly": view_weekly, "/goals": view_goals, "/rules": view_rules,
          "/files": view_files, "/search": view_search, "/file": view_file}
DETAIL = {"posts": view_post, "people": view_person, "projects": view_project}


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        path = url.path.rstrip("/") or "/"
        try:
            if path.startswith("/raw/"):
                f = safe_path(path[5:])
                if not f or not f.is_file():
                    return self.send(404, "Not found", "text/plain")
                ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                if ctype.startswith("text/"):
                    ctype += "; charset=utf-8"
                return self.send(200, f.read_bytes(), ctype)
            con = brain.connect(readonly=True)
            try:
                parts = path.strip("/").split("/")
                if path in ROUTES:
                    out = ROUTES[path](con, q)
                elif len(parts) == 2 and parts[0] in DETAIL and parts[1].isdigit():
                    out = DETAIL[parts[0]](con, int(parts[1]))
                elif len(parts) == 2 and parts[0] == "area":
                    out = view_area(con, parts[1])
                else:
                    out = None
            finally:
                con.close()
            if out is None:
                return self.send(404, page("Not found", '<p class="muted">That page doesn\'t exist.</p>'))
            self.send(200, out)
        except Exception as e:  # show the error instead of a blank page
            self.send(500, f"<pre>{esc(type(e).__name__)}: {esc(e)}</pre>")
            raise

    def log_message(self, *args):
        pass


def main():
    if not brain.DB.exists():
        sys.exit("brain.db not found. Run setup/seed.py first.")
    brain.backup()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"My Work Brain is running at {url}  (close this window to stop it)")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
