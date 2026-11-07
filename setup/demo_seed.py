"""Rebuild the demo brain with made-up data. Safe to run again: it wipes the demo database first.

Run from D:\\brain-demo:  python setup/demo_seed.py   (or double-click reset-demo.bat)
Dates are set relative to today, so the Today page always looks current.
"""
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if ROOT.name != "brain-demo":
    sys.exit("This script only runs inside the brain-demo folder.")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "setup"))
import brain  # noqa: E402
import pipeline_data  # noqa: E402

T = dt.date.today()


def d(days):
    return (T + dt.timedelta(days=days)).isoformat()


for f in [brain.DB, *brain.BACKUPS.glob("*.db")] if brain.BACKUPS.exists() else [brain.DB]:
    if f.exists():
        f.unlink()

con = brain.connect()
S = lambda table, item: brain.save(con, table, item)  # noqa: E731

with con:
    con.execute("DELETE FROM areas")
    for i, (slug, name, summary) in enumerate([
        ("general", "General", "Rules and decisions that apply to everything."),
        ("linkedin", "LinkedIn", "Posts about sales and how people decide. Where most leads come from."),
        ("sales", "Sales", "My pipeline: founders and teams who want help with selling."),
        ("learning", "Learning", "Books and notes on selling and negotiation."),
        ("brain", "Second brain", "This system: the database, the website, and how Claude uses them."),
    ]):
        S("areas", {"slug": slug, "name": name, "summary": summary, "sort": i})

    for area, rule, why in [
        ("general", "One answer, not a menu. When I ask \"what should I do\", give one recommendation.", ""),
        ("general", "Claude does the data entry. I share things in chat; Claude records them.", "I don't want data-entry chores."),
        ("general", "US English everywhere.", ""),
        ("general", "Active voice always: someone does the action.", ""),
        ("brain", "Log only when I say \"log this\".", ""),
        ("brain", "A decision goes into Decisions only after I say yes. Claude can suggest; I decide.", ""),
        ("brain", "At the end of every session, Claude lists everything we discussed that isn't in the brain yet, and I say yes or no to each.", "So nothing we talk about gets lost."),
        ("general", "When Claude gets something wrong, it says so plainly and fixes it, without excuses.", ""),
    ]:
        S("rules", {"area": area, "rule": rule, "why": why, "date": d(-30)})

    g1 = S("goals", {"area": "sales", "goal": "5 new clients this quarter", "target": "5", "by_date": d(55), "note": "1 won so far (Tom Becker)."})
    g2 = S("goals", {"area": "linkedin", "goal": "Reach 1,500 followers", "target": "1,500", "by_date": d(80), "note": "About 1,120 now."})

    p1 = S("projects", {"name": "Q4 pipeline", "area": "sales", "goal_id": g1, "outcome": "5 signed clients, every lead has a next step and a date.", "due": d(55)})
    p2 = S("projects", {"name": "Post 3 times a week", "area": "linkedin", "goal_id": g2, "outcome": "12 posts out this month, numbers logged for each.", "due": d(24)})
    p3 = S("projects", {"name": "Brain v2: email connection", "area": "brain", "outcome": "New emails from leads show up on their page by themselves."})

    for t in [
        {"project_id": p1, "title": "Send Kitebridge the proposal", "due": d(0), "priority": "high", "details": "Daniel asked for scope and price after the call."},
        {"project_id": p1, "title": "Prepare questions for the Northwind call", "due": d(1)},
        {"project_id": p1, "title": "Halcyon: answer on the pricing", "status": "waiting", "waiting_on": "Priya Raman", "waiting_since": d(-6)},
        {"project_id": p1, "title": "Weekly pipeline review", "due": d(0), "recurring": "weekly:fri"},
        {"project_id": p1, "title": "Kickoff notes for Tom's team", "status": "done", "done_date": d(-3)},
        {"project_id": p2, "title": "Finish draft 14 (the cold call that worked)", "due": d(-2)},
        {"project_id": p2, "title": "Sunday numbers: followers and impressions", "due": d(2), "recurring": "weekly:sun"},
        {"project_id": p3, "title": "Set up a test Gmail account", "status": "doing"},
        {"project_id": p3, "title": "Decide which emails count (only people already in the brain?)", "status": "inbox"},
        {"area": "general", "title": "Renew phone plan", "status": "inbox"},
    ]:
        S("tasks", t)

    for date, area, decision, why in [
        (d(-25), "sales", "Every lead gets a next step and a date, or gets closed.", "Leads with no next step go quiet."),
        (d(-14), "sales", "Send pricing only after a call, never in the first message.", "Price without context gets no reply."),
        (d(-5), "brain", "Connect email directly to Google, no extra tools in between.", "Fewer moving parts."),
    ]:
        S("decisions", {"date": date, "area": area, "decision": decision, "why": why})

    for num, title, typ, status, day, point, nums in [
        (10, "The meeting that ended in 4 minutes", "Moment", "posted", -12, "A no can be the most useful answer.", (4210, 2980, 61, 14, 3)),
        (11, "Three questions before any pitch", "Value", "posted", -9, "Ask what changed, what it costs, what they tried.", (6890, 4520, 98, 27, 6)),
        (12, "My first sale was a bicycle", "Human interest", "posted", -5, "Trust comes before price.", (5120, 3610, 77, 19, 2)),
        (13, "Why prospects go quiet", "Value", "posted", -2, "Silence usually means a missing next step.", (3340, 2410, 45, 11, 1)),
    ]:
        imp, reach, react, com, rep = nums
        S("posts", {"num": num, "title": title, "type": typ, "status": status, "posted_date": d(day), "point": point,
                    "impressions": imp, "reached": reach, "reactions": react, "comments": com, "reposts": rep, "metrics_taken": "7d"})
    S("posts", {"num": 14, "title": "The cold call that worked", "type": "Moment", "status": "draft", "planned_date": d(1),
                "file": "posts/drafts/14-cold-call.md", "point": "Asking one honest question beat the script."})
    S("posts", {"num": 15, "title": "Price is rarely the real reason", "type": "Value", "status": "idea"})

    for idea, src in [
        ("What a taxi ride taught me about listening", "own story"),
        ("The follow-up that's too polite", "a DM this week"),
        ("Why 'just checking in' gets no reply", "comment thread"),
    ]:
        S("ideas", {"date": d(-4), "area": "linkedin", "idea": idea, "source": src})

    for wk, fol, imp in [(-21, 980, 9800), (-14, 1035, 12400), (-7, 1088, 14100), (0, 1121, 15300)]:
        S("weekly", {"date": d(wk), "followers": fol, "impressions_7d": imp})

    # Leads. Sarah is the one for the live demo: she hasn't replied yet (ball = them).
    S("people", {
        "name": "Sarah Lin", "who": "Head of Growth at Northwind Labs (Singapore, 40 people).", "channel": "linkedin", "first_by": "them",
        "kind": "lead", "want": "Help setting up a sales process for her team.", "ball": "them",
        "next_step": "Wait for her to pick a time for a call.", "due": d(2),
        "log_add": [
            {"d": d(-3), "by": "them", "t": "Hi Mohammed, loved your post on why prospects go quiet. That's us right now. Could we talk?"},
            {"d": d(-2), "by": "me", "t": "Hey Sarah, thanks! sure... what does your follow-up look like today?"},
        ]})
    S("people", {
        "name": "Daniel Okafor", "who": "Founder of Kitebridge, a logistics startup (12 people).", "channel": "email", "first_by": "me",
        "kind": "lead", "want": "Training for his first two sales hires.", "ball": "me",
        "next_step": "Send the proposal: scope and price.", "due": d(-1),
        "log_add": [
            {"d": d(-7), "by": "me", "t": "Hey Daniel, saw you're hiring your first sales people... curious how you'll train them?"},
            {"d": d(-6), "by": "them", "t": "Good question. I was going to have them shadow me for a month."},
            {"d": d(-6), "by": "me", "t": "shadowing helps, but they'll copy your habits too 😄 call this week?"},
            {"d": d(-5), "by": "them", "t": "Sure, Tuesday at 2."},
            {"d": d(-4), "by": "note", "t": "Call: 2 new hires start next month. Wants a 4-week plan. Budget around USD 4,500."},
            {"d": d(-4), "by": "them", "t": "Great call. Send me the proposal when you can."},
        ]})
    S("people", {
        "name": "Priya Raman", "who": "COO at Halcyon Group (Kuala Lumpur).", "channel": "email", "first_by": "them",
        "kind": "lead", "want": "Workshop for 8 account managers.", "ball": "them",
        "next_step": "She's checking the price with her CEO.", "due": d(-2),
        "log_add": [
            {"d": d(-9), "by": "them", "t": "Hi Mohammed, a friend sent me your profile. Do you run workshops for teams?"},
            {"d": d(-9), "by": "me", "t": "Hey Priya, I do 😄 what's going on with the team?"},
            {"d": d(-8), "by": "them", "t": "8 account managers. Great at service, weak at upselling."},
            {"d": d(-8), "by": "me", "t": "got it... quick call so I can understand the accounts?"},
            {"d": d(-7), "by": "them", "t": "Sure, tomorrow 10am KL time."},
            {"d": d(-6), "by": "note", "t": "Call: Halcyon, 8 account managers. Renewals are fine, upsells almost zero. Wants a 1-day workshop + a follow-up session. Budget around USD 8,000."},
            {"d": d(-6), "by": "me", "t": "Hey Priya, here's the outline and price, happy to adjust for 8 people."},
            {"d": d(-5), "by": "them", "t": "Thanks! Checking with our CEO and I'll come back to you."},
        ]})
    S("people", {
        "name": "Aisha Rahman", "who": "Founder of a design studio, referred by Tom.", "channel": "linkedin", "first_by": "them",
        "kind": "lead", "want": "One-to-one coaching on closing bigger clients.", "ball": "me",
        "next_step": "Reply to her question about start dates.", "due": d(1),
        "log_add": [
            {"d": d(-1), "by": "them", "t": "Tom said you helped his team a lot. When could we start?"},
            {"d": d(-1), "by": "them", "t": "I want to close bigger clients this year. Right now most projects are under $3k."},
        ]})
    S("people", {
        "name": "Lucas Moreau", "who": "Founder of Brightpath, an online course business.", "channel": "linkedin", "first_by": "me",
        "kind": "lead", "want": "Fix his sales calls (low close rate).", "ball": "them",
        "next_step": "Went quiet after the call. One nudge, then close.", "due": d(-3),
        "log_add": [
            {"d": d(-12), "by": "me", "t": "Hey Lucas, liked your post about sales calls... what's the hardest part right now?"},
            {"d": d(-12), "by": "them", "t": "People love the free call, then ghost me when I mention the price."},
            {"d": d(-11), "by": "me", "t": "that's fixable... 20 min call tomorrow? I'll show you where it usually breaks"},
            {"d": d(-11), "by": "them", "t": "Sure, 4pm Melbourne time."},
            {"d": d(-10), "by": "note", "t": "Call: close rate around 10%. Price comes up before he knows their problem. Said he'd think about it."},
            {"d": d(-9), "by": "me", "t": "Thanks for the chat Lucas! the 3 questions we talked about are below... happy to help you put them into your calls"},
        ]})
    S("people", {
        "name": "Tom Becker", "who": "Founder of Fieldnote, a B2B software company (Berlin).", "channel": "whatsapp", "first_by": "me",
        "kind": "lead", "ball": "closed", "outcome": "client",
        "log_add": [
            {"d": d(-24), "by": "me", "t": "Tom! long time... how's the sales team doing?"},
            {"d": d(-24), "by": "them", "t": "Growing, but messy. 3 new reps and nobody follows up the same way."},
            {"d": d(-23), "by": "me", "t": "ha that's the most common one... want to jump on a call this week? I can show you what I'd change"},
            {"d": d(-23), "by": "them", "t": "Thursday 10am Berlin time?"},
            {"d": d(-20), "by": "note", "t": "Call: 3 new reps, no shared follow-up process, deals stall after the demo. Wants a 2-day workshop + 4 weeks of check-ins. Budget about USD 7,500."},
            {"d": d(-19), "by": "me", "t": "Hey Tom, here's the proposal from our call: workshop + 4 weekly check-ins. Any questions, just shout"},
            {"d": d(-17), "by": "them", "t": "Looks good. Can we start the workshop on the 1st?"},
            {"d": d(-16), "by": "me", "t": "Yes 😄 the 1st works"},
            {"d": d(-15), "by": "them", "t": "Let's do it. Send the invoice."},
        ]})
    S("people", {
        "name": "Maya Chen", "who": "Marketing lead at a large retail brand.", "channel": "linkedin", "first_by": "them",
        "kind": "lead", "ball": "closed", "outcome": "nofit",
        "log_add": [
            {"d": d(-11), "by": "them", "t": "Do you do paid ads?"},
            {"d": d(-11), "by": "me", "t": "Not me sorry... but I can point you to someone good 😄"},
        ]})

    # The rest of the pipeline, from setup/pipeline_data.py. Each stage gets the messages a real lead at that stage would have.
    for (name, role, ck, channel, first_by, want, stage, value, ago, fu, first) in pipeline_data.LEADS:
        cname, _, industry, size, city = pipeline_data.COMPANIES[ck]
        first_name = name.split()[0]
        msgs = [{"d": d(-ago), "by": first_by, "t": first}]
        later = lambda n: d(-max(ago - n, 0))  # noqa: E731
        ball, outcome, nxt = "me", "", ""
        if stage == "New":
            ball = "me" if first_by == "them" else "them"
            nxt = "Reply: ask what isn't working today." if ball == "me" else "Wait for a reply."
        elif stage == "Talking":
            if first_by == "them":
                msgs.append({"d": later(1), "by": "me", "t": f"Hey {first_name}, thanks for reaching out! what does it look like today?"})
            else:
                msgs.append({"d": later(1), "by": "them", "t": "Honestly, slower than we hoped. Why do you ask?"})
                msgs.append({"d": later(2), "by": "me", "t": "I help founders with exactly that... open to a quick call?"})
            ball, nxt = "them", "Wait for their reply about a call."
        elif stage in ("Call booked", "Call done", "Proposal sent", "Won", "Lost"):
            if first_by == "them":
                msgs.append({"d": later(1), "by": "me", "t": f"Hey {first_name}, happy to help... quick call this week?"})
            else:
                msgs.append({"d": later(1), "by": "them", "t": "Yes, it's been a struggle. Let's talk."})
            msgs.append({"d": later(2), "by": "them", "t": "Sure, send me a time."})
            if stage == "Call booked":
                ball, nxt = "me", f"Call on {d(fu)}: prepare three questions."
            else:
                if stage != "Lost" or value:
                    msgs.append({"d": later(4), "by": "note", "t": f"Call: {want} Budget around USD {value:,}."})
                if stage == "Call done":
                    ball, nxt = "me", "Send the proposal."
                elif stage == "Proposal sent":
                    msgs.append({"d": later(6), "by": "me", "t": f"Hey {first_name}, here's the proposal we talked about... any questions, just shout"})
                    ball, nxt = "them", "Waiting on their answer to the proposal."
                elif stage == "Won":
                    msgs.append({"d": later(6), "by": "me", "t": f"Hey {first_name}, here's the proposal 😄"})
                    msgs.append({"d": later(8), "by": "them", "t": "Looks good. Let's go ahead."})
                    ball, outcome = "closed", "client"
                elif stage == "Lost":
                    if value:
                        msgs.append({"d": later(8), "by": "them", "t": "We'll pass for now, timing isn't right."})
                    ball, outcome = "closed", ("quiet" if value else "nofit")
        if stage == "Lost" and not value:
            msgs = [msgs[0], {"d": later(1), "by": "me", "t": "Not something I do sorry... hope you find someone good 😄"}]
        if name in pipeline_data.CONVOS:
            msgs = [{"d": d(o), "by": b, "t": x} for o, b, x in pipeline_data.CONVOS[name]]
        S("people", {
            "name": name, "who": f"{role} at {cname} ({city}, {size} people, {industry}).", "channel": channel,
            "first_by": first_by, "kind": "lead", "want": want, "ball": ball, "outcome": outcome,
            "next_step": nxt, "due": d(fu) if ball != "closed" else "", "log_add": msgs})

    for date, area, title, details in [
        (d(-15), "sales", "Won Tom Becker (Fieldnote)", "First client this quarter. Came from a WhatsApp catch-up."),
        (d(-9), "linkedin", "Post 11 did best so far", "6,890 impressions. Two leads came from it."),
        (d(-6), "brain", "Added projects and tasks to the brain", ""),
    ]:
        S("log", {"date": date, "area": area, "title": title, "details": details})

    S("files", {"path": "about-me.md", "area": "general", "title": "About me", "description": "Who I am, schedule, how I work."})
    S("files", {"path": "writing-guide.md", "area": "linkedin", "title": "Writing guide", "description": "How my posts sound."})
    S("files", {"path": "posts/drafts/14-cold-call.md", "area": "linkedin", "title": "Draft 14: The cold call that worked", "description": "Next post."})

    # Spread the setup history over the past days, so the live change in the video is the newest line.
    ids = [r[0] for r in con.execute("SELECT id FROM activity ORDER BY id")]
    start = dt.datetime.combine(T, dt.time(9)) - dt.timedelta(days=10)
    for i, aid in enumerate(ids):
        at = start + dt.timedelta(minutes=int(i * 10 * 24 * 60 * 0.9 / max(len(ids), 1)))
        con.execute("UPDATE activity SET at=? WHERE id=?", (at.isoformat(timespec="seconds"), aid))

print(f"Demo brain rebuilt at {brain.DB}")
