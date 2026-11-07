"""My Work Brain: the database, and the command-line tool Claude uses to read and write it.

Run from this folder:
  python brain.py today                         the morning brief (what's due, flags, latest log)
  python brain.py add TABLE DATA                create one record or a list. DATA is JSON, @file.json, or - for stdin
  python brain.py update TABLE ID DATA          change some fields of one record
  python brain.py get TABLE ID                  print one record
  python brain.py list TABLE [field=value ...]  print records, optionally filtered
  python brain.py search TEXT                   search every table and every file
  python brain.py log AREA "title" ["details"] ["link"]   quick log entry, dated today
  python brain.py tables                        list tables and their fields
  python brain.py activity [N]                  the last N changes (default 30), newest first

People: "log_add": [{"d": "2026-10-27", "by": "me|them|note", "t": "exact message"}] adds messages to the conversation
(stored in the messages table, one row per message; last_contact updates itself).
Posts drive their own reminders: no tasks for "post N" or "log post N numbers" (Today flags them).

Projects and tasks (like ClickUp/Basecamp):
  projects: name, area, goal_id, status (active|paused|done|dropped), outcome ("done looks like"), due
  tasks:    status inbox|todo|doing|waiting|done|dropped, priority high|normal|low, project_id, parent_id (subtask),
            recurring (daily | weekly:sun | weekly:mon,wed,fri | monthly:15 | every:14d), waiting_on
  Marking a recurring task done creates the next one. "waiting" stamps waiting_since. "done" stamps done_date.
The website (server.py) only reads. All writing goes through this file.
Every add and update is recorded automatically in the activity table (the website's Activity page).
"""
import datetime as dt
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "brain.db"
FILES = ROOT / "files"
BACKUPS = ROOT / "backups"
KEEP_BACKUPS = 30

STAMPS = "created_at TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT ''"
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS areas (
  id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active', summary TEXT DEFAULT '', sort INTEGER DEFAULT 0, {STAMPS});
CREATE TABLE IF NOT EXISTS log (
  id INTEGER PRIMARY KEY, date TEXT NOT NULL, area TEXT NOT NULL, title TEXT NOT NULL,
  details TEXT DEFAULT '', link TEXT DEFAULT '', {STAMPS});
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY, date TEXT NOT NULL, area TEXT NOT NULL, decision TEXT NOT NULL,
  why TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'active', replaced_by INTEGER,
  link TEXT DEFAULT '', {STAMPS});
CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, area TEXT NOT NULL, goal_id INTEGER,
  status TEXT NOT NULL DEFAULT 'active', outcome TEXT DEFAULT '', due TEXT DEFAULT '',
  note TEXT DEFAULT '', sort INTEGER DEFAULT 0, {STAMPS});
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY, area TEXT NOT NULL, title TEXT NOT NULL, details TEXT DEFAULT '',
  due TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'todo', done_date TEXT DEFAULT '',
  link TEXT DEFAULT '', project_id INTEGER, parent_id INTEGER, priority TEXT NOT NULL DEFAULT 'normal',
  recurring TEXT DEFAULT '', waiting_on TEXT DEFAULT '', waiting_since TEXT DEFAULT '', {STAMPS});
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY, num INTEGER, title TEXT NOT NULL, type TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'draft', planned_date TEXT DEFAULT '', posted_date TEXT DEFAULT '',
  file TEXT DEFAULT '', point TEXT DEFAULT '',
  impressions INTEGER, reached INTEGER, out_network_pct INTEGER, reactions INTEGER, comments INTEGER,
  reposts INTEGER, saves INTEGER, sends INTEGER, profile_views INTEGER, followers INTEGER,
  dms INTEGER, connections INTEGER, audience TEXT DEFAULT '', metrics_taken TEXT DEFAULT '',
  note TEXT DEFAULT '', {STAMPS});
CREATE TABLE IF NOT EXISTS ideas (
  id INTEGER PRIMARY KEY, date TEXT DEFAULT '', area TEXT NOT NULL, idea TEXT NOT NULL,
  source TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'open', post_id INTEGER, note TEXT DEFAULT '', {STAMPS});
CREATE TABLE IF NOT EXISTS people (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, who TEXT DEFAULT '', link TEXT DEFAULT '',
  channel TEXT NOT NULL DEFAULT 'linkedin', first_by TEXT NOT NULL DEFAULT 'them',
  kind TEXT NOT NULL DEFAULT 'other', want TEXT DEFAULT '',
  ball TEXT NOT NULL DEFAULT 'me', outcome TEXT DEFAULT '', next_step TEXT DEFAULT '',
  due TEXT DEFAULT '', last_contact TEXT DEFAULT '', notes TEXT DEFAULT '', {STAMPS});
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY, person_id INTEGER NOT NULL, date TEXT NOT NULL, by TEXT NOT NULL,
  text TEXT NOT NULL DEFAULT '', {STAMPS});
CREATE INDEX IF NOT EXISTS messages_person ON messages(person_id, date);
CREATE TABLE IF NOT EXISTS weekly (
  id INTEGER PRIMARY KEY, date TEXT NOT NULL, followers INTEGER, impressions_7d INTEGER,
  profile_viewers_90d INTEGER, search_appearances INTEGER, note TEXT DEFAULT '', {STAMPS});
CREATE TABLE IF NOT EXISTS goals (
  id INTEGER PRIMARY KEY, area TEXT NOT NULL, goal TEXT NOT NULL, target TEXT DEFAULT '',
  by_date TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'active', note TEXT DEFAULT '', {STAMPS});
CREATE TABLE IF NOT EXISTS rules (
  id INTEGER PRIMARY KEY, area TEXT NOT NULL, rule TEXT NOT NULL, why TEXT DEFAULT '',
  date TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'active', {STAMPS});
CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, area TEXT NOT NULL, title TEXT NOT NULL,
  description TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'current', {STAMPS});
CREATE TABLE IF NOT EXISTS activity (
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, action TEXT NOT NULL, tbl TEXT NOT NULL,
  record_id INTEGER, label TEXT DEFAULT '', changes TEXT NOT NULL DEFAULT '[]');
"""

TABLES = ["areas", "log", "decisions", "projects", "tasks", "posts", "ideas", "people", "messages", "weekly", "goals", "rules", "files"]

CHOICES = {
    ("areas", "status"): {"active", "paused", "parked", "closed"},
    ("decisions", "status"): {"active", "replaced", "dropped"},
    ("tasks", "status"): {"inbox", "todo", "doing", "waiting", "done", "dropped"},
    ("tasks", "priority"): {"high", "normal", "low"},
    ("projects", "status"): {"active", "paused", "done", "dropped"},
    ("posts", "type"): {"", "Moment", "Value", "Human interest", "Collaboration"},
    ("posts", "status"): {"idea", "draft", "ready", "posted", "on hold", "dropped"},
    ("ideas", "status"): {"open", "planned", "used", "parked", "dropped"},
    ("people", "channel"): {"linkedin", "whatsapp", "email", "in person", "other"},
    ("people", "first_by"): {"them", "me"},
    ("people", "kind"): {"lead", "partner", "job", "pitch", "friend", "other"},
    ("people", "ball"): {"me", "them", "closed"},
    ("people", "outcome"): {"", "client", "nofit", "quiet", "done"},
    ("messages", "by"): {"me", "them", "note"},
    ("goals", "status"): {"active", "reached", "dropped"},
    ("rules", "status"): {"active", "dropped"},
    ("files", "status"): {"current", "history", "parked"},
}
DATE_FIELDS = {"date", "due", "done_date", "planned_date", "posted_date", "by_date", "last_contact", "waiting_since"}
OPEN = ("inbox", "todo", "doing", "waiting")
OPEN_SQL = "('inbox','todo','doing','waiting')"
WAIT_DAYS = 5
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def today():
    return dt.date.today()


def connect(readonly=False):
    if readonly:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    else:
        con = sqlite3.connect(DB)
        con.executescript(SCHEMA)
    con.row_factory = sqlite3.Row
    if not readonly:
        migrate_messages(con)
        migrate_tasks(con)
        backfill_activity(con)
    return con


def migrate_tasks(con):
    """Once: give the old tasks table the project fields, and rename status 'open' to 'todo'."""
    cols = columns(con, "tasks")
    if "priority" in cols:
        return
    backup()
    for col, ddl in [("project_id", "INTEGER"), ("parent_id", "INTEGER"), ("priority", "TEXT NOT NULL DEFAULT 'normal'"),
                     ("recurring", "TEXT DEFAULT ''"), ("waiting_on", "TEXT DEFAULT ''"), ("waiting_since", "TEXT DEFAULT ''")]:
        if col not in cols:
            con.execute(f"ALTER TABLE tasks ADD COLUMN {col} {ddl}")
    with con:
        n = con.execute("UPDATE tasks SET status='todo' WHERE status='open'").rowcount
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='activity'").fetchone():
            record_activity(con, "updated", "tasks", None, "All tasks",
                            [{"f": "fields", "to": "added project, priority, subtasks, recurring, waiting on"},
                             {"f": "status", "from": "open", "to": f"todo ({n} tasks)"}])


def migrate_messages(con):
    """Once: move each person's conversation out of people.log into the messages table, and drop unused fields."""
    cols = columns(con, "people")
    if "log" not in cols:
        return
    backup()
    moved = 0
    with con:
        for r in con.execute("SELECT id, log, created_at FROM people").fetchall():
            for e in json.loads(r["log"] or "[]"):
                con.execute("INSERT INTO messages (person_id, date, by, text, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                            (r["id"], e["d"], e["by"], e.get("t", ""), r["created_at"], r["created_at"]))
                moved += 1
    con.execute("ALTER TABLE people DROP COLUMN log")
    if "topics" in cols:
        con.execute("ALTER TABLE people DROP COLUMN topics")
    with con:
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='activity'").fetchone():
            record_activity(con, "updated", "people", None, "All people",
                            [{"f": "conversations", "to": f"moved {moved} messages into their own table"},
                             {"f": "topics", "from": "field", "to": "removed (never used)"}])


# ---------- activity: an automatic record of every change ----------
# Written only here, inside the same transaction as the change itself, so nothing slips past it.
# Separate from the log table, which stays the user's own journal ("log this").

def short(v, n=300):
    v = "" if v is None else str(v)
    return v if len(v) <= n else v[:n] + "…"


def record_activity(con, action, table, rid, row_label, changes=(), at=None):
    con.execute("INSERT INTO activity (at, action, tbl, record_id, label, changes) VALUES (?,?,?,?,?,?)",
                (at or now(), action, table, rid, row_label, json.dumps(list(changes), ensure_ascii=False)))


def diff(table, old, new_fields):
    out = []
    for k, v in new_fields.items():
        if k in ("created_at", "updated_at"):
            continue
        before = old[k]
        if (before if before is not None else "") == (v if v is not None else ""):
            continue
        out.append({"f": k, "from": short(before), "to": short(v)})
    return out


def backfill_activity(con):
    """Once: turn what's already stored into 'created' events, so the Activity page has a past."""
    if con.execute("SELECT 1 FROM activity LIMIT 1").fetchone():
        return
    backup()
    with con:
        for table in TABLES:
            for r in con.execute(f"SELECT * FROM {table}").fetchall():
                row = dict(r)
                created = row.get("created_at") or "2026-10-27T00:00:00"
                record_activity(con, "created", table, row["id"], label(table, row), at=created)
                if row.get("updated_at") and row["updated_at"] != created:
                    record_activity(con, "updated", table, row["id"], label(table, row),
                                    [{"f": "note", "to": "changed (field details weren't recorded before Oct 31, 2026)"}],
                                    at=row["updated_at"])


def backup():
    """One copy of the database per day, made before the first write of that day."""
    if not DB.exists():
        return
    BACKUPS.mkdir(exist_ok=True)
    target = BACKUPS / f"brain-{today().isoformat()}.db"
    if not target.exists():
        shutil.copy2(DB, target)
    for old in sorted(BACKUPS.glob("brain-*.db"))[:-KEEP_BACKUPS]:
        old.unlink()


def columns(con, table):
    return [r["name"] for r in con.execute(f"PRAGMA table_info({table})")]


def check_table(table):
    if table not in TABLES:
        sys.exit(f"Unknown table {table!r}. Tables: {', '.join(TABLES)}")


def area_slugs(con):
    return {r["slug"] for r in con.execute("SELECT slug FROM areas")}


def clean(con, table, item, creating):
    cols = set(columns(con, table)) - {"id", "created_at", "updated_at"}
    out = {}
    for key, value in item.items():
        if key in ("id", "log_add"):
            continue
        if key not in cols:
            sys.exit(f"{table} has no field {key!r}. Fields: {', '.join(sorted(cols))}")
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False)
        if isinstance(value, str):
            value = value.strip()
        allowed = CHOICES.get((table, key))
        if allowed is not None and value not in allowed:
            sys.exit(f"{table}.{key} must be one of {sorted(allowed)}, got {value!r}")
        if key in DATE_FIELDS and value and not DATE_RE.fullmatch(str(value)):
            sys.exit(f"{table}.{key} must look like 2026-10-27, got {value!r}")
        if key == "person_id" and not con.execute("SELECT 1 FROM people WHERE id=?", (value,)).fetchone():
            sys.exit(f"No person with id {value!r}")
        if key == "area" and table != "areas" and value not in area_slugs(con):
            sys.exit(f"Unknown area {value!r}. Areas: {', '.join(sorted(area_slugs(con)))}")
        out[key] = value
    if creating and table == "log" and not out.get("date"):
        out["date"] = today().isoformat()
    return out


DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
RECUR_RE = re.compile(r"daily|weekly:(mon|tue|wed|thu|fri|sat|sun)(,(mon|tue|wed|thu|fri|sat|sun))*|monthly:([1-9]|[12]\d|3[01])|every:\d+d")


def next_due(rule, after):
    """The next date after `after` that matches a recurring rule."""
    if rule == "daily":
        return after + dt.timedelta(days=1)
    if rule.startswith("every:"):
        return after + dt.timedelta(days=int(rule[6:-1]))
    if rule.startswith("weekly:"):
        days = {DAYS.index(d) for d in rule[7:].split(",")}
        d = after + dt.timedelta(days=1)
        while d.weekday() not in days:
            d += dt.timedelta(days=1)
        return d
    if rule.startswith("monthly:"):
        day = int(rule[8:])
        y, m = after.year, after.month
        for _ in range(3):
            try:
                d = dt.date(y, m, day)
                if d > after:
                    return d
            except ValueError:
                pass
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    raise ValueError(rule)


def task_rules(con, fields, old):
    """The rules that make tasks behave like a real task tool. Returns a follow-up task to create, if any."""
    status = fields.get("status", old["status"] if old else "todo")
    was = old["status"] if old else None
    rule = fields.get("recurring", old["recurring"] if old else "")
    if rule and not RECUR_RE.fullmatch(rule):
        sys.exit("tasks.recurring must be daily, weekly:sun, weekly:mon,wed,fri, monthly:15 or every:14d")
    for key, table in (("project_id", "projects"), ("parent_id", "tasks")):
        if fields.get(key) and not con.execute(f"SELECT 1 FROM {table} WHERE id=?", (fields[key],)).fetchone():
            sys.exit(f"No {table} record with id {fields[key]}")
    if fields.get("project_id") and "area" not in fields and not old:
        fields["area"] = con.execute("SELECT area FROM projects WHERE id=?", (fields["project_id"],)).fetchone()["area"]
    if status == "waiting" and was != "waiting" and not fields.get("waiting_since"):
        fields["waiting_since"] = today().isoformat()
    if status != "waiting" and was == "waiting":
        fields.setdefault("waiting_since", "")
    if status == "done" and was != "done" and not fields.get("done_date"):
        fields["done_date"] = today().isoformat()
    if status == "done" and was != "done" and rule:
        base_due = fields.get("due", old["due"] if old else "")
        base = dt.date.fromisoformat(base_due) if base_due else today()
        nxt = next_due(rule, max(base, today() - dt.timedelta(days=1)))
        src = {**(dict(old) if old else {}), **fields}
        return {k: src.get(k) for k in ("area", "title", "details", "link", "project_id", "parent_id", "priority", "recurring")
                if src.get(k) not in (None, "")} | {"due": nxt.isoformat(), "status": "todo"}
    return None


def sync_last_contact(con, pid, ts):
    """last_contact = the newest real message (notes don't count). Returns the change, if any."""
    row = con.execute("SELECT last_contact FROM people WHERE id=?", (pid,)).fetchone()
    new = con.execute("SELECT MAX(date) FROM messages WHERE person_id=? AND by!='note'", (pid,)).fetchone()[0] or ""
    if not row or not new or (row["last_contact"] or "") == new:
        return None
    con.execute("UPDATE people SET last_contact=?, updated_at=? WHERE id=?", (new, ts, pid))
    return {"f": "last_contact", "from": row["last_contact"] or "", "to": new}


def row_label(con, table, row):
    if table == "messages":
        who = con.execute("SELECT name FROM people WHERE id=?", (row.get("person_id"),)).fetchone()
        return f'{who["name"] if who else "?"} · {row.get("by")}: {short(row.get("text"), 80)}'
    return label(table, row)


def save(con, table, item, record_id=None):
    creating = record_id is None
    fields = clean(con, table, item, creating)
    new_msgs = item.get("log_add", []) if table == "people" else []
    old_task = con.execute("SELECT * FROM tasks WHERE id=?", (record_id,)).fetchone() if table == "tasks" and record_id else None
    if table == "tasks" and creating and "area" not in fields and "project_id" not in fields:
        sys.exit("A task needs an area or a project_id")
    if table == "tasks" and creating:
        fields.setdefault("status", "todo")  # the old table still carries 'open' as its default
        fields.setdefault("priority", "normal")
    follow_up = task_rules(con, fields, old_task) if table == "tasks" else None
    for e in new_msgs:
        if not DATE_RE.fullmatch(str(e.get("d", ""))) or e.get("by") not in ("me", "them", "note"):
            sys.exit(f"Bad conversation entry: {e!r}")
    ts = now()
    changes, old = [], None
    if creating:
        fields["created_at"] = fields["updated_at"] = ts
        keys = list(fields)
        cur = con.execute(
            f"INSERT INTO {table} ({','.join(keys)}) VALUES ({','.join('?' * len(keys))})",
            [fields[k] for k in keys])
        rid = cur.lastrowid
    else:
        rid = record_id
        old = con.execute(f"SELECT * FROM {table} WHERE id=?", (rid,)).fetchone()
        if not old:
            sys.exit(f"No {table} record with id {rid}")
        changes = diff(table, old, fields)
        if changes:
            fields["updated_at"] = ts
            con.execute(f"UPDATE {table} SET {', '.join(k + '=?' for k in fields)} WHERE id=?", [*fields.values(), rid])
    for e in sorted(new_msgs, key=lambda e: e["d"]):
        text = str(e.get("t", "")).strip()
        con.execute("INSERT INTO messages (person_id, date, by, text, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                    (rid, e["d"], e["by"], text, ts, ts))
        changes.append({"f": "message", "to": short(f'{e["by"]}: {text}', 200)})
    if new_msgs and not creating:
        con.execute("UPDATE people SET updated_at=? WHERE id=?", (ts, rid))
    pid = None
    if table == "people" and new_msgs:
        pid = rid
    elif table == "messages":
        pid = fields.get("person_id") or (old["person_id"] if old else None)
    if pid:
        c = sync_last_contact(con, pid, ts)
        if c and table == "people":
            changes.append(c)
    row = {**(dict(old) if old else {}), **fields, "id": rid}
    if creating:
        record_activity(con, "created", table, rid, row_label(con, table, row), changes, at=ts)
    elif changes:
        record_activity(con, "updated", table, rid, row_label(con, table, row), changes, at=ts)
    if follow_up and (creating or changes):
        save(con, "tasks", follow_up)  # the next one of a recurring task
    return rid


def read_data(arg):
    if arg == "-":
        text = sys.stdin.buffer.read().decode("utf-8-sig")  # always UTF-8, so emojis survive on Windows
    elif arg.startswith("@"):
        text = Path(arg[1:]).read_text(encoding="utf-8")
    else:
        text = arg
    return json.loads(text)


# ---------- what the brief and the home page show ----------

def week_bounds(day=None):
    day = day or today()
    start = day - dt.timedelta(days=day.weekday())
    return start, start + dt.timedelta(days=6)


def quoted(title):
    title = title or ""
    return title if title.startswith('"') else f'"{title}"'


def flags(con):
    """Things that slipped. The chief of staff points them out; the user decides."""
    t = today()
    out = []
    for p in con.execute("SELECT * FROM posts WHERE status='posted' AND impressions IS NULL AND posted_date!=''"):
        if dt.date.fromisoformat(p["posted_date"]) <= t - dt.timedelta(days=1):
            out.append(("posts", p["id"], f"Post {p['num'] or ''} {quoted(p['title'])} has no numbers yet (posted {p['posted_date']})"))
    for p in con.execute("SELECT * FROM posts WHERE status IN ('draft','ready') AND planned_date=?", (t.isoformat(),)):
        out.append(("posts", p["id"], f"Post {p['num'] or ''} {quoted(p['title'])} is planned for today"))
    last = con.execute("SELECT MAX(date) FROM weekly").fetchone()[0]
    days = (t - dt.date.fromisoformat(last)).days if last else None
    if t.weekday() == 6 and (days is None or days >= 6):
        out.append(("weekly", None, "Sunday: time for this week's dashboard numbers (followers, impressions 7d, profile viewers 90d, search appearances)"))
    elif days is None or days > 7:
        out.append(("weekly", None, f"Weekly numbers: last taken {last} ({days} days ago). Next chance: Sunday"))
    for p in con.execute("SELECT * FROM posts WHERE status IN ('draft','ready') AND planned_date!='' AND planned_date<?", (t.isoformat(),)):
        out.append(("posts", p["id"], f"Post {p['num'] or ''} {quoted(p['title'])} was planned for {p['planned_date']} but isn't marked posted"))
    for r in con.execute(f"SELECT * FROM tasks WHERE status IN {OPEN_SQL} AND due!='' AND due<? ORDER BY due", (t.isoformat(),)):
        out.append(("tasks", r["id"], f"Overdue since {r['due']}: {r['title']}"))
    for r in con.execute(f"SELECT * FROM tasks WHERE status IN {OPEN_SQL} AND due=? ORDER BY priority='high' DESC", (t.isoformat(),)):
        out.append(("tasks", r["id"], f"Due today: {r['title']}"))
    for r in con.execute("SELECT * FROM tasks WHERE status='waiting' AND waiting_since!='' AND waiting_since<=? ORDER BY waiting_since",
                         ((t - dt.timedelta(days=WAIT_DAYS)).isoformat(),)):
        n = (t - dt.date.fromisoformat(r["waiting_since"])).days
        out.append(("tasks", r["id"], f"Waiting {n} days{' on ' + r['waiting_on'] if r['waiting_on'] else ''}: {r['title']}. Chase it, or drop it?"))
    inbox = con.execute("SELECT COUNT(*) FROM tasks WHERE status='inbox'").fetchone()[0]
    if inbox:
        out.append(("review", None, f"{inbox} {'item' if inbox == 1 else 'items'} in the inbox to sort"))
    for pr in con.execute("SELECT * FROM projects WHERE status='active' ORDER BY sort, id"):
        if not con.execute(f"SELECT 1 FROM tasks WHERE project_id=? AND status IN ('todo','doing','waiting')", (pr["id"],)).fetchone():
            out.append(("projects", pr["id"], f"Project \"{pr['name']}\" has no next step"))
        elif pr["due"] and pr["due"] < t.isoformat():
            out.append(("projects", pr["id"], f"Project \"{pr['name']}\" was due {pr['due']}"))
    for r in con.execute("SELECT * FROM people WHERE ball='me' AND due!='' AND due<? ORDER BY due", (t.isoformat(),)):
        out.append(("people", r["id"], f"{r['name']}: your move, follow-up date {r['due']} has passed"))
    quiet = [r["name"] for r in con.execute(
        "SELECT name FROM people WHERE ball='them' AND due!='' AND due<? ORDER BY due", (t.isoformat(),))]
    if quiet:
        out.append(("people", None, f"{len(quiet)} people haven't replied by their follow-up date: {', '.join(quiet)}. Let them rest, or close them?"))
    return out


def brief(con):
    t = today()
    ws, we = week_bounds()
    soon = (t + dt.timedelta(days=7)).isoformat()
    return {
        "today": t,
        "week_posts": con.execute(
            "SELECT * FROM posts WHERE (posted_date BETWEEN ? AND ?) OR (planned_date BETWEEN ? AND ?) "
            "ORDER BY COALESCE(NULLIF(posted_date,''), planned_date)",
            (ws.isoformat(), we.isoformat(), ws.isoformat(), we.isoformat())).fetchall(),
        "tasks": con.execute(
            f"SELECT * FROM tasks WHERE status IN {OPEN_SQL} AND due!='' AND due<=? ORDER BY due, priority='high' DESC", (soon,)).fetchall(),
        "undated": con.execute(
            f"SELECT * FROM tasks WHERE status IN {OPEN_SQL} AND due='' ORDER BY area, id").fetchall(),
        "doing": con.execute("SELECT * FROM tasks WHERE status='doing' ORDER BY priority='high' DESC, id").fetchall(),
        "projects": con.execute("SELECT * FROM projects WHERE status='active' ORDER BY sort, id").fetchall(),
        "my_move": con.execute(
            "SELECT * FROM people WHERE ball='me' ORDER BY COALESCE(NULLIF(due,''),'9999'), last_contact").fetchall(),
        "flags": flags(con),
        "log": con.execute("SELECT * FROM log ORDER BY date DESC, id DESC LIMIT 10").fetchall(),
        "decisions": con.execute(
            "SELECT * FROM decisions WHERE status='active' ORDER BY date DESC, id DESC LIMIT 5").fetchall(),
    }


def search(con, text):
    like = f"%{text}%"
    hits = []
    for table in TABLES:
        cols = [c for c in columns(con, table) if c not in ("id", "created_at", "updated_at")]
        where = " OR ".join(f"CAST({c} AS TEXT) LIKE ?" for c in cols)
        for row in con.execute(f"SELECT * FROM {table} WHERE {where}", [like] * len(cols)):
            hits.append((table, dict(row)))
    file_hits = []
    if FILES.exists():
        low = text.lower()
        for f in sorted(FILES.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".md", ".txt", ".html", ".css", ".json"):
                try:
                    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    continue
                found = [(i + 1, ln.strip()) for i, ln in enumerate(lines) if low in ln.lower()]
                if found:
                    file_hits.append((f.relative_to(FILES).as_posix(), found))
    return hits, file_hits


def label(table, row):
    if table == "messages":
        return f'{row.get("by")}: {short(row.get("text"), 80)}'
    for key in ("title", "decision", "idea", "name", "goal", "rule", "path", "slug"):  # projects use name
        if row.get(key):
            return str(row[key])
    return f"{table} #{row['id']}"


# ---------- command line ----------

def print_json(obj):
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(obj, indent=1, ensure_ascii=False, default=str))


def cmd_today(con):
    sys.stdout.reconfigure(encoding="utf-8")
    b = brief(con)
    t = b["today"]
    print(f"TODAY: {t:%A %Y-%m-%d}\n")
    print("Posts this week:")
    for p in b["week_posts"]:
        when = p["posted_date"] or p["planned_date"]
        print(f"  {when} [{p['status']}] {p['num'] or ''} {p['title']}")
    print("\nFlags:")
    for _, _, msg in b["flags"] or [(0, 0, "none")]:
        print(f"  ! {msg}")
    print("\nTasks due in the next 7 days:")
    for r in b["tasks"]:
        print(f"  {r['due']} [{r['area']}] {r['title']} (#{r['id']})")
    print(f"\nOpen tasks with no date: {len(b['undated'])}")
    print("\nPeople waiting on you:")
    for r in b["my_move"]:
        print(f"  {r['name']}: {r['next_step'][:110]}")
    print("\nLatest log:")
    for r in b["log"][:5]:
        print(f"  {r['date']} [{r['area']}] {r['title']}")


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd = argv[1]
    if cmd == "today":
        cmd_today(connect())
        return
    if cmd == "tables":
        con = connect()
        for t in TABLES:
            print(f"{t}: {', '.join(columns(con, t))}")
        return
    if cmd == "activity":
        con = connect()
        n = int(argv[2]) if len(argv) > 2 else 30
        sys.stdout.reconfigure(encoding="utf-8")
        for r in con.execute("SELECT * FROM activity ORDER BY at DESC, id DESC LIMIT ?", (n,)):
            print(f"{r['at'].replace('T', ' ')[:16]}  {r['action']:<7} {r['tbl']:<9} {r['label'][:60]}")
            for c in json.loads(r["changes"]):
                print(f"      {c['f']}: " + (f"{c.get('from', '')!s:.60} → " if "from" in c else "") + f"{c['to']!s:.80}")
        return
    if cmd == "search":
        con = connect()
        hits, file_hits = search(con, " ".join(argv[2:]))
        print_json({"records": [{"table": t, "id": r["id"], "label": label(t, r)} for t, r in hits],
                    "files": [{"path": p, "lines": f[:5]} for p, f in file_hits]})
        return
    if cmd in ("add", "update", "get", "list"):
        table = argv[2]
        check_table(table)
        con = connect()
        if cmd == "get":
            row = con.execute(f"SELECT * FROM {table} WHERE id=?", (int(argv[3]),)).fetchone()
            print_json(dict(row) if row else None)
            return
        if cmd == "list":
            filters = [a.split("=", 1) for a in argv[3:]]
            where = " AND ".join(f"{k}=?" for k, _ in filters) or "1"
            rows = con.execute(f"SELECT * FROM {table} WHERE {where} ORDER BY id", [v for _, v in filters])
            print_json([dict(r) for r in rows])
            return
        backup()
        if cmd == "add":
            data = read_data(argv[3])
            items = data if isinstance(data, list) else [data]
            with con:
                ids = [save(con, table, item) for item in items]
            print_json({"added": table, "ids": ids})
        else:
            rid = int(argv[3])
            with con:
                save(con, table, read_data(argv[4]), rid)
            print_json({"updated": table, "id": rid})
        return
    if cmd == "log":
        con = connect()
        backup()
        item = {"area": argv[2], "title": argv[3]}
        if len(argv) > 4:
            item["details"] = argv[4]
        if len(argv) > 5:
            item["link"] = argv[5]
        with con:
            rid = save(con, "log", item)
        print_json({"added": "log", "id": rid})
        return
    sys.exit(f"Unknown command {cmd!r}. Run: python brain.py help")


if __name__ == "__main__":
    main(sys.argv)
