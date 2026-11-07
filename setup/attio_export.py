"""Turn the demo brain into Attio-ready rows, for Claude to send with the Attio connection.

Usage (from D:\brain-demo):  python -X utf8 setup/attio_export.py . companies|people|deals|notes
Prints one record per line. The Attio IDs Claude gets back link people to companies and deals to both."""
import json
import sqlite3
import sys
from pathlib import Path

demo = Path(sys.argv[1])
what = sys.argv[2]
sys.path.insert(0, str(demo / "setup"))
import pipeline_data as P  # noqa: E402

# The Attio workspace owner's email lives in setup/local_settings.json (not in git): {"owner_email": "you@company.com"}
_settings = Path(__file__).with_name("local_settings.json")
OWNER = json.loads(_settings.read_text(encoding="utf-8"))["owner_email"] if _settings.exists() else "owner@example.com"

COUNTRY = {"Singapore": "Singapore", "Jakarta": "Indonesia", "Kuala Lumpur": "Malaysia", "Melbourne": "Australia",
           "Berlin": "Germany", "Sydney": "Australia", "Bangkok": "Thailand", "Auckland": "New Zealand",
           "Brisbane": "Australia", "Bali": "Indonesia", "Ho Chi Minh City": "Vietnam", "Hong Kong": "Hong Kong",
           "Manila": "Philippines", "Perth": "Australia", "Phuket": "Thailand", "Surabaya": "Indonesia",
           "Dubai": "United Arab Emirates", "London": "United Kingdom"}
CATEGORY = {"Online education": "Education", "Health tech": "Health Care", "Healthcare": "Health Care",
            "Retail": "Retail", "E-commerce": "Retail", "Marketing agency": "Marketing & Advertising",
            "Design agency": "Marketing & Advertising"}
STAGE = {"New": "New", "Talking": "Talking", "Call booked": "Call Booked", "Call done": "Call Done",
         "Proposal sent": "Proposal Sent", "Won": "Won 🎉", "Lost": "Lost"}
CORE_ROLE = {"Sarah Lin": "Head of Growth", "Daniel Okafor": "Founder", "Priya Raman": "COO", "Aisha Rahman": "Founder",
             "Lucas Moreau": "Founder", "Tom Becker": "Founder", "Maya Chen": "Marketing Lead"}
DEAL_NAME = {"Maya Chen": "Paid ads (no fit)", "Oscar Diaz": "Instagram ads (no fit)",
             "Priscilla Ong": "Lead lists (no fit)", "Jack Turner": "Sales playbook before the first hire"}
PERSON_NOTE = {"Maya Chen": "Asked about paid ads (not something I do).", "Oscar Diaz": "Asked about Instagram ads (not something I do).",
               "Priscilla Ong": "Asked for lead lists (not something I do).", "Jack Turner": "Sales playbook before the first hire."}
SKIP = set()       # names already in Attio, if a run is resumed
SKIP_CO = set()


def size_range(n):
    return "1-10" if n <= 10 else "11-50" if n <= 50 else "51-250" if n <= 250 else "251-1K"


lead = {}
for name, (ck, value, stage) in P.CORE.items():
    lead[name] = {"role": CORE_ROLE[name], "ck": ck, "value": value, "stage": stage}
for (name, role, ck, ch, fb, want, stage, value, *_rest) in P.LEADS:
    lead[name] = {"role": role, "ck": ck, "value": value, "stage": stage}

con = sqlite3.connect(demo / "brain.db")
con.row_factory = sqlite3.Row
people = con.execute("SELECT * FROM people WHERE kind='lead' ORDER BY id").fetchall()

if what == "companies":
    used = {lead[p["name"]]["ck"] for p in people}
    for ck in [k for k in P.COMPANIES if k in used and k not in SKIP_CO]:
        name, _, ind, size, city = P.COMPANIES[ck]
        v = {"name": name, "description": f"{ind}. {size} people. {city}.", "employee_range": size_range(size),
             "primary_location": f"{city}, {COUNTRY[city]}"}
        if ind in CATEGORY:
            v["categories"] = [CATEGORY[ind]]
        print(ck, json.dumps(v, ensure_ascii=False))
elif what == "people":
    for p in people:
        if p["name"] in SKIP:
            continue
        L = lead[p["name"]]
        first, last = p["name"].split(" ", 1)
        how = "They reached out first" if p["first_by"] == "them" else "I reached out first"
        v = {"name": [{"first_name": first, "last_name": last, "full_name": p["name"]}], "job_title": L["role"],
             "description": PERSON_NOTE.get(p["name"], p["want"]) + f" {how}, " + {"email": "by email", "whatsapp": "on WhatsApp", "linkedin": "on LinkedIn"}.get(p["channel"], "")+"."}
        print(L["ck"], json.dumps(v, ensure_ascii=False))
elif what == "deals":
    for p in people:
        if p["name"] in SKIP:
            continue
        L = lead[p["name"]]
        v = {"name": f"{P.COMPANIES[L['ck']][0]}: " + DEAL_NAME.get(p["name"], p["want"].rstrip(".")), "stage": STAGE[L["stage"]], "owner": OWNER}
        if L["value"]:
            v["value"] = L["value"]
        if p["ball"] in ("me", "them"):
            v["who_s_next"] = "Me" if p["ball"] == "me" else "Them"
            if p["next_step"]:
                v["next_step"] = p["next_step"]
            if p["due"]:
                v["follow_up_date"] = p["due"]
        print(p["name"], "|", L["ck"], json.dumps(v, ensure_ascii=False))
elif what == "notes":
    for p in people:
        if p["name"] in SKIP:
            continue
        first = p["name"].split()[0]
        ch = {"linkedin": "LinkedIn", "whatsapp": "WhatsApp", "email": "Email"}.get(p["channel"], p["channel"])
        lines = []
        for m in con.execute("SELECT date, by, text FROM messages WHERE person_id=? ORDER BY date, id", (p["id"],)):
            who = f"Me ({ch})" if m["by"] == "me" else first if m["by"] == "them" else "Note"
            lines.append(f"- **{m['date']} · {who}:** {m['text']}")
        print("###", p["name"])
        print("\n".join(lines))
