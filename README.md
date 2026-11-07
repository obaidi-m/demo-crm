# Sales CRM demo, built with Claude Code

A small CRM I built to follow my leads, and the migration of its pipeline into Attio. Everything here runs on **made-up data**: 35 leads at 30 fictional companies.

I designed how it works. Claude Code wrote the code.

## What's inside

- **`brain.py`**: the database (SQLite) and the command-line tool Claude uses to read and write it.
- **`server.py`**: a local, read-only website for the CRM (Today page, people, projects, activity).
- **`CLAUDE.md`**: the rules Claude follows to run the CRM: how to log a reply, when to update the next step, how to move the pipeline to Attio.
- **`setup/`**: the made-up data (`pipeline_data.py`, `demo_seed.py`) and the Attio export (`attio_export.py`).

## How it works

Every lead has a stage, a next step, a follow-up date and "who's next" (me or them). When a reply comes in, I paste it to Claude, and Claude saves it word for word and updates the record.

The Today page flags what slipped by itself: follow-up dates that passed, leads who went quiet, and things waiting too long.

## Moving it into Attio

Claude Code moved the whole pipeline into an Attio workspace through the Attio connection: 30 companies, 35 people, 35 deals and one conversation note per person, about $149k in open pipeline.

What I decided:
- **Stages that follow how a deal really moves:** New, Talking, Call Booked, Call Done, Proposal Sent, Won, Lost.
- **Three added fields on Deals:** Next Step, Follow-up Date, Who's Next. Every open deal has a next step and a date, or it gets closed.
- **One note per person** with the whole conversation, so it reads in 30 seconds before a call.
- **Two saved views:** "My move today" and "Gone quiet."

Problems I hit:
- Attio refused the made-up website addresses.
- With reserved test addresses, Attio's auto-fill looked them up and gave every company the same fake "$70M funding, founded 1999". So companies go in without websites.

## Run it

```
python setup/demo_seed.py     # build the demo database
python server.py              # website at http://localhost:8792
python brain.py today         # the morning brief in the terminal
```

Python 3.10+ and no other installs.

## Next

Connecting email, so new replies update the CRM without me pasting them.
