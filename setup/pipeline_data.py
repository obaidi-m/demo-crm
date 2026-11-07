"""Made-up companies and leads for the demo pipeline.

The demo seed loads these into the brain. The Attio import reads COMPANIES and DEALS from here too,
so both always agree. Domains are NOT sent to Attio: Attio looks up any website and fills in data about it (example.com got "$70M funding, founded 1999"). Companies go in by name only.
"""

# key: (name, domain, industry, employees, city)
COMPANIES = {
    "northwind": ("Northwind Labs", "northwindlabs.example.com", "B2B software", 40, "Singapore"),
    "kitebridge": ("Kitebridge", "kitebridge.example.com", "Logistics", 12, "Jakarta"),
    "halcyon": ("Halcyon Group", "halcyongroup.example.com", "Professional services", 120, "Kuala Lumpur"),
    "studio_rahman": ("Rahman Studio", "rahmanstudio.example.com", "Design agency", 9, "Singapore"),
    "brightpath": ("Brightpath", "brightpath.example.com", "Online education", 15, "Melbourne"),
    "fieldnote": ("Fieldnote", "fieldnote.example.com", "B2B software", 35, "Berlin"),
    "maya_retail": ("Coastline Retail", "coastlineretail.example.com", "Retail", 600, "Sydney"),
    "tidepool": ("Tidepool Analytics", "tidepool.example.com", "Data and analytics", 25, "Sydney"),
    "lumen": ("Lumen Health", "lumenhealth.example.com", "Health tech", 60, "Singapore"),
    "orchard": ("Orchard Freight", "orchardfreight.example.com", "Logistics", 80, "Bangkok"),
    "kopi": ("Kopi Works", "kopiworks.example.com", "Food and beverage", 30, "Jakarta"),
    "paperkite": ("Paperkite", "paperkite.example.com", "Marketing agency", 18, "Auckland"),
    "ironbark": ("Ironbark Build", "ironbarkbuild.example.com", "Construction", 150, "Brisbane"),
    "seabright": ("Seabright Properties", "seabright.example.com", "Real estate", 45, "Bali"),
    "nimbus": ("Nimbus Pay", "nimbuspay.example.com", "Fintech", 70, "Singapore"),
    "terra": ("Terra Goods", "terragoods.example.com", "E-commerce", 22, "Ho Chi Minh City"),
    "quillon": ("Quillon Legal", "quillonlegal.example.com", "Legal", 40, "Hong Kong"),
    "stackyard": ("Stackyard", "stackyard.example.com", "B2B software", 14, "Manila"),
    "bluegum": ("Bluegum Clinics", "bluegum.example.com", "Healthcare", 200, "Perth"),
    "solace": ("Solace Hotels", "solacehotels.example.com", "Hospitality", 300, "Phuket"),
    "verdant": ("Verdant Energy", "verdantenergy.example.com", "Clean energy", 55, "Sydney"),
    "mosaic": ("Mosaic Learning", "mosaiclearning.example.com", "Online education", 28, "Kuala Lumpur"),
    "anchor": ("Anchor Recruitment", "anchorrecruit.example.com", "Recruitment", 35, "Melbourne"),
    "pixelmint": ("Pixelmint", "pixelmint.example.com", "Design agency", 11, "Bangkok"),
    "copperline": ("Copperline Manufacturing", "copperline.example.com", "Manufacturing", 250, "Surabaya"),
    "harbor": ("Harbor Insurance Brokers", "harborbrokers.example.com", "Insurance", 65, "Auckland"),
    "fernway": ("Fernway Travel", "fernway.example.com", "Travel", 40, "Dubai"),
    "granite": ("Granite Security", "granitesec.example.com", "Cybersecurity", 30, "Singapore"),
    "ember": ("Ember Coffee Roasters", "embercoffee.example.com", "Food and beverage", 16, "Melbourne"),
    "atlas": ("Atlas HR", "atlashr.example.com", "HR software", 48, "London"),
}

# The 7 hand-written leads in demo_seed.py: name -> (company key, deal value USD, stage)
CORE = {
    "Sarah Lin": ("northwind", 6000, "Talking"),
    "Daniel Okafor": ("kitebridge", 4500, "Call done"),
    "Priya Raman": ("halcyon", 8000, "Proposal sent"),
    "Aisha Rahman": ("studio_rahman", 2500, "New"),
    "Lucas Moreau": ("brightpath", 3000, "Call done"),
    "Tom Becker": ("fieldnote", 7500, "Won"),
    "Maya Chen": ("maya_retail", 0, "Lost"),
}

STAGES = ["New", "Talking", "Call booked", "Call done", "Proposal sent", "Won", "Lost"]

# More leads: (name, role, company key, channel, first_by, want, stage, value, started days ago, follow-up day offset, first message)
# Follow-up offset is days from today (negative = already passed, which makes the Today flags show up).
LEADS = [
    ("James Whitfield", "CEO", "tidepool", "linkedin", "them", "Sales process for a 3-person sales team.", "New", 5000, 1, 0,
     "Hey Mohammed, Wei told me about the coaching you did with him. Do you also work with small sales teams?"),
    ("Nurul Hidayah", "Founder", "kopi", "whatsapp", "them", "Train café managers to sell catering deals.", "New", 2000, 2, -1,
     "Hi, a friend gave me your number. We want to sell more catering to offices. Can you help?"),
    ("Ben Carter", "Sales Director", "ironbark", "email", "them", "Fix a long sales cycle on big projects.", "New", 9000, 0, 1,
     "Mohammed, our deals take 9 months to close. Is that something you look at?"),
    ("Mei Tan", "Head of Partnerships", "nimbus", "linkedin", "them", "Partner sales playbook.", "New", 6500, 3, 2,
     "Thanks for connecting, Mohammed. I read your post about first calls. Happy to chat sometime."),
    ("Rafael Santos", "Founder", "stackyard", "linkedin", "them", "First sales hire onboarding.", "New", 3500, 1, 1,
     "Hey! Hiring my first salesperson next month. No idea how to train them lol. Thoughts?"),

    ("Grace Liu", "COO", "lumen", "email", "them", "Sales training for 6 account managers.", "Talking", 7000, 6, 2,
     "Hi Mohammed, we're looking for someone to run sales training for our clinic partnerships team."),
    ("Arjun Mehta", "Founder", "terra", "linkedin", "me", "Wholesale sales to retailers.", "Talking", 3000, 8, -2,
     "Hey Arjun, saw Terra just started selling to shops... how are those first conversations going?"),
    ("Olivia Brooks", "Managing Director", "paperkite", "linkedin", "them", "Help the team close bigger retainers.", "Talking", 4000, 5, 1,
     "Our team is great at the work and terrible at selling it 😅 Is that your thing?"),
    ("Hiro Tanaka", "Country Manager", "orchard", "email", "them", "Sales process for a new Thai office.", "Talking", 8500, 7, -1,
     "Hello Mohammed, we're opening a sales team in Bangkok and need a process from day one."),
    ("Sofia Rossi", "Head of Sales", "verdant", "linkedin", "them", "Coaching for 4 new reps.", "Talking", 6000, 4, 3,
     "Hi, I lead sales at Verdant. Your 'three questions before any pitch' post is now on our wall."),
    ("Kevin Ng", "Founder", "granite", "linkedin", "me", "Founder-led sales coaching.", "Talking", 3500, 9, -3,
     "Hey Kevin, congrats on the funding round... are you still doing all the sales yourself?"),

    ("Emma Wilson", "CEO", "anchor", "email", "them", "Workshop on discovery calls.", "Call booked", 5500, 10, 2,
     "Mohammed, our recruiters jump to the pitch too fast. Could you run a workshop?"),
    ("Putu Wirawan", "Owner", "seabright", "whatsapp", "them", "Sales scripts for villa agents.", "Call booked", 3000, 6, 1,
     "Halo Mohammed, my agents lose buyers after the first viewing. Can we talk?"),
    ("Chloe Martin", "Head of Growth", "mosaic", "linkedin", "me", "Sales process for school partnerships.", "Call booked", 4500, 12, 3,
     "Hey Chloe, saw Mosaic is working with schools now... who's doing those deals?"),
    ("Daniel Reyes", "VP Sales", "harbor", "email", "them", "Training for 10 brokers.", "Call booked", 9500, 8, 4,
     "Hi Mohammed, Grace from Lumen recommended you. We have 10 brokers who need help."),

    ("Lina Haddad", "Founder", "fernway", "linkedin", "them", "Selling group tours to companies.", "Call done", 4000, 14, -2,
     "Hi Mohammed, we want to sell team trips to companies, not just tourists. Ideas?"),
    ("Marcus Lee", "Sales Manager", "bluegum", "email", "them", "Referral program with GPs.", "Call done", 6500, 13, 1,
     "Mohammed, can we talk about how we get more referrals from doctors?"),
    ("Aroha Parata", "Founder", "pixelmint", "linkedin", "me", "Pricing and proposal coaching.", "Call done", 2500, 11, 0,
     "Hey Aroha, your portfolio is lovely... how do you usually price projects?"),

    ("Tom Nguyen", "COO", "copperline", "email", "them", "Sales process for export clients.", "Proposal sent", 12000, 20, -4,
     "Hello Mohammed, we sell to buyers in Japan and Korea and our follow-up is a mess."),
    ("Isabelle Fournier", "CEO", "quillon", "linkedin", "them", "Business development training for partners.", "Proposal sent", 8000, 18, 2,
     "Our partners hate selling. Can you make it feel less like selling?"),
    ("Sam Patel", "Founder", "ember", "linkedin", "them", "Wholesale sales to cafés.", "Proposal sent", 2500, 15, -1,
     "Hey mate, we want to get our beans into more cafés. You help with that?"),
    ("Rachel Kim", "Head of Sales", "atlas", "email", "them", "Coaching for an 8-person team.", "Proposal sent", 9000, 16, 3,
     "Hi Mohammed, our win rate dropped this quarter. Looking for outside help."),

    ("Nina Volkova", "Founder", "solace", "email", "them", "Corporate booking sales.", "Won", 7000, 30, 0,
     "Hi Mohammed, we want more corporate retreats booked. Can you train our sales team?"),
    ("Wei Zhang", "Co-founder", "tidepool", "linkedin", "me", "Founder sales coaching.", "Won", 4000, 28, 0,
     "Hey Wei, loved your talk on data teams... how do you find your clients today?"),
    ("Hannah Schmidt", "Sales Lead", "fieldnote", "email", "them", "Follow-up training for the team.", "Won", 3500, 5, 0,
     "Hi Mohammed, I lead sales at Fieldnote. Tom said the workshop was great. Could we add a session on follow-ups?"),

    ("Oscar Diaz", "Marketing staff", "kopi", "linkedin", "them", "Social media ads.", "Lost", 0, 21, 0,
     "Do you do Instagram ads?"),
    ("Priscilla Ong", "Marketing Manager", "nimbus", "email", "them", "Lead generation lists.", "Lost", 0, 19, 0,
     "Hi, can you send us a list of 1,000 leads?"),
    ("Jack Turner", "Co-founder", "stackyard", "linkedin", "me", "Sales coaching.", "Lost", 3000, 24, 0,
     "Hey Jack, saw you're hiring in sales... how's the team going?"),
]


# Full conversation for each lead above: (days from today, who, exact message). "note" = my own note after a call.
CONVOS = {
    "James Whitfield": [
        (-1, "them", "Hey Mohammed, Wei told me about the coaching you did with him. Do you also work with small sales teams?"),
        (-1, "them", "We're 3 people selling analytics to retailers. Lots of demos, few signed deals."),
    ],
    "Nurul Hidayah": [
        (-2, "them", "Hi, a friend gave me your number. We want to sell more catering to offices. Can you help?"),
        (-2, "them", "We have 4 outlets in Jakarta. Offices order once and then never again 😅"),
    ],
    "Ben Carter": [
        (0, "them", "Mohammed, our deals take 9 months to close. Is that something you look at?"),
        (0, "them", "For context: commercial fit-outs, deals are $200k+, and 5 or 6 people sign off on each one."),
    ],
    "Mei Tan": [
        (-3, "them", "Thanks for connecting, Mohammed. I read your post about first calls. Happy to chat sometime."),
        (-3, "them", "We're building a partner channel this quarter and nobody here has done it before."),
    ],
    "Rafael Santos": [
        (-1, "them", "Hey! Hiring my first salesperson next month. No idea how to train them lol. Thoughts?"),
    ],

    "Grace Liu": [
        (-6, "them", "Hi Mohammed, we're looking for someone to run sales training for our clinic partnerships team."),
        (-5, "me", "Hey Grace, thanks for reaching out! how many people are on the team, and what do they find hardest?"),
        (-4, "them", "Six account managers. Great with clinics we already work with, but they freeze when they have to open a new one."),
        (-4, "me", "that's a really common one... a cold conversation needs a different start. would a 30 min call next week work?"),
    ],
    "Arjun Mehta": [
        (-8, "me", "Hey Arjun, saw Terra just started selling to shops... how are those first conversations going?"),
        (-7, "them", "Honestly, slower than we hoped. Shops say they love the products, then don't order."),
        (-7, "me", "ha the classic 'love it' with no order... usually the first order feels too risky for them. quick call?"),
    ],
    "Olivia Brooks": [
        (-5, "them", "Our team is great at the work and terrible at selling it 😅 Is that your thing?"),
        (-4, "me", "Hey Olivia, very much my thing 😄 what happens today when a client asks about a retainer?"),
        (-3, "them", "We send a deck and pray. The last 3 went cold after the deck."),
        (-3, "me", "sounds like the deck is doing the selling for you... want to walk me through the last one on a call?"),
    ],
    "Hiro Tanaka": [
        (-7, "them", "Hello Mohammed, we're opening a sales team in Bangkok and need a process from day one."),
        (-6, "me", "Hey Hiro, congrats on the new office! how many people are you hiring, and who will they sell to?"),
        (-5, "them", "Four people to start. Selling to manufacturers who already use another freight company."),
        (-5, "me", "getting people to switch is its own game... happy to share how I'd set it up. call this week?"),
    ],
    "Sofia Rossi": [
        (-4, "them", "Hi, I lead sales at Verdant. Your 'three questions before any pitch' post is now on our wall."),
        (-3, "me", "Hey Sofia, that made my day 😄 what made it land for your team?"),
        (-3, "them", "Our 4 new reps pitch solar panels in the first minute. Customers tune out."),
        (-2, "me", "yeah they're excited about the product... the questions fix that. want me to show you how I'd coach it? 20 min call?"),
    ],
    "Kevin Ng": [
        (-9, "me", "Hey Kevin, congrats on the funding round... are you still doing all the sales yourself?"),
        (-8, "them", "Ha, yes. Every single deal. The board wants a sales team by Q2."),
        (-8, "me", "that's a big shift... the hard part is getting what's in your head into theirs. open to a quick call about it?"),
    ],

    "Emma Wilson": [
        (-10, "them", "Mohammed, our recruiters jump to the pitch too fast. Could you run a workshop?"),
        (-9, "me", "Hey Emma, happy to! how many recruiters, and is it with candidates or clients?"),
        (-8, "them", "12 of them. Clients mostly. They hear 'we're hiring' and start selling our fees."),
        (-8, "me", "got it... let's do a call so I can hear a real example. what works for you?"),
        (-7, "them", "Booked a slot in your calendar. Looking forward to it."),
    ],
    "Putu Wirawan": [
        (-6, "them", "Halo Mohammed, my agents lose buyers after the first viewing. Can we talk?"),
        (-6, "me", "Halo Pak Putu! sure... what happens after a viewing today?"),
        (-5, "them", "They send photos and the price on WhatsApp. Then nothing."),
        (-5, "me", "I think I see it already 😄 let's do a call and you can show me some of those chats"),
        (-4, "them", "OK, I booked the time in your calendar."),
    ],
    "Chloe Martin": [
        (-12, "me", "Hey Chloe, saw Mosaic is working with schools now... who's doing those deals?"),
        (-11, "them", "Me, mostly! And it's slow. Schools have so many people involved."),
        (-10, "me", "yeah schools are a different game... principal, IT, finance, and the parents in the background 😄 compare notes on a call?"),
        (-9, "them", "Yes please. Sent you an invite."),
    ],
    "Daniel Reyes": [
        (-8, "them", "Hi Mohammed, a friend at another brokerage recommended you. We have 10 brokers who need help."),
        (-7, "me", "Hey Daniel, nice to meet you 😄 what do your brokers struggle with most?"),
        (-6, "them", "Renewals. Clients shop around every year and we lose about a third of them."),
        (-6, "me", "a third is a lot... I'd love to hear how a renewal call goes. can we do a call first?"),
        (-5, "them", "Works. It's in the calendar, and I'll bring two of the brokers."),
    ],

    "Lina Haddad": [
        (-14, "them", "Hi Mohammed, we want to sell team trips to companies, not just tourists. Ideas?"),
        (-13, "me", "Hey Lina, love that idea... who would buy it inside a company? HR? the founder?"),
        (-12, "them", "That's the problem, we don't know! We've been emailing HR and nobody answers."),
        (-12, "me", "let's figure it out together... quick call this week?"),
        (-11, "them", "Sure, Wednesday morning works."),
        (-9, "note", "Call: Fernway sells group trips. HR doesn't own the budget, team leads do. Wants a plan to reach team leads + scripts. Budget around USD 4,000."),
        (-9, "them", "Great call. Can you send me the plan and the price?"),
    ],
    "Marcus Lee": [
        (-13, "them", "Mohammed, can we talk about how we get more referrals from doctors?"),
        (-12, "me", "Hey Marcus, sure... how do referrals come in today?"),
        (-12, "them", "Mostly luck. A GP likes one of our physios and sends people over. No system at all."),
        (-11, "me", "luck is a great start, we just need to make it repeatable 😄 call this week?"),
        (-10, "them", "Thursday works. I'll invite our clinic manager too."),
        (-8, "note", "Call: Bluegum has 12 clinics. Referrals come from about 20 GPs, nobody follows up after the first one. Wants a simple GP visit routine + training for 5 people. Budget around USD 6,500."),
    ],
    "Aroha Parata": [
        (-11, "me", "Hey Aroha, your portfolio is lovely... how do you usually price projects?"),
        (-10, "them", "Thank you! Honestly, I guess. And I always guess low."),
        (-10, "me", "ha you're not alone... want to look at your last few quotes together?"),
        (-9, "them", "Yes please, that would help a lot."),
        (-7, "note", "Call: Pixelmint, 11 people. Prices by the hour, clients push back on every quote. Wants help moving to fixed packages. Budget around USD 2,500."),
        (-6, "them", "That call already changed how I think about pricing. Send me the proposal?"),
    ],

    "Tom Nguyen": [
        (-20, "them", "Hello Mohammed, we sell to buyers in Japan and Korea and our follow-up is a mess."),
        (-19, "me", "Hey Tom, export deals need patience... what does follow-up look like now?"),
        (-19, "them", "Each salesperson keeps their own Excel. When someone leaves, their buyers are gone too."),
        (-18, "me", "ouch... that's fixable. call this week?"),
        (-17, "them", "Yes. Wednesday afternoon."),
        (-15, "note", "Call: Copperline, 6 export salespeople, no shared records, long gaps between follow-ups. Wants a shared process + 3 training days. Budget around USD 12,000."),
        (-13, "me", "Hey Tom, here's the proposal from our call: shared follow-up process + 3 training days. any questions, just shout"),
        (-12, "them", "Thanks. I'll share it with our director."),
    ],
    "Isabelle Fournier": [
        (-18, "them", "Our partners hate selling. Can you make it feel less like selling?"),
        (-17, "me", "Hey Isabelle, ha yes... most lawyers I meet feel the same. what do they do today when a client calls?"),
        (-16, "them", "They answer the legal question for free and never mention fees."),
        (-16, "me", "so they're already helping, they just stop too early 😄 call?"),
        (-15, "them", "Friday at 11, Hong Kong time."),
        (-13, "note", "Call: Quillon, 8 partners. Great at advice, never ask for the next step. Wants a half-day session + 1:1 coaching for 3 partners. Budget around USD 8,000."),
        (-11, "me", "Hey Isabelle, here's the proposal: half-day session + coaching for 3 partners. happy to adjust"),
        (-10, "them", "Thanks! The partners meet next week, I'll come back to you after."),
    ],
    "Sam Patel": [
        (-15, "them", "Hey mate, we want to get our beans into more cafés. You help with that?"),
        (-14, "me", "Hey Sam, sure... how do you approach cafés now?"),
        (-14, "them", "Walk in with a free bag. They say thanks and keep their supplier."),
        (-13, "me", "ha the free bag... let's chat, I think the order of things is off"),
        (-12, "them", "Tomorrow 3pm?"),
        (-11, "note", "Call: Ember, 16 people. Wholesale is 10 cafés, wants 40. Walk-ins with samples, no follow-up. Wants a visit routine + 2 sessions for Sam and 1 rep. Budget around USD 2,500."),
        (-9, "me", "Hey Sam, here's the proposal we talked about... any questions, just shout"),
    ],
    "Rachel Kim": [
        (-16, "them", "Hi Mohammed, our win rate dropped this quarter. Looking for outside help."),
        (-15, "me", "Hey Rachel, thanks for reaching out... dropped from what to what?"),
        (-15, "them", "From 28% to 17%. Same team, same product."),
        (-14, "me", "that's a big drop with nothing changed... call to look at a few lost deals?"),
        (-13, "them", "Yes. I'll pull 5 lost deals before we talk."),
        (-11, "note", "Call: Atlas, 8 reps. Lost deals stall after the demo, no clear next step. Wants 6 weeks of team coaching. Budget around USD 9,000."),
        (-9, "me", "Hey Rachel, here's the proposal: 6 weeks of coaching, starting with your 5 lost deals. any questions, just shout"),
        (-8, "them", "Got it, thank you. Going through it with our CEO."),
    ],

    "Nina Volkova": [
        (-30, "them", "Hi Mohammed, we want more corporate retreats booked. Can you train our sales team?"),
        (-29, "me", "Hey Nina, sounds fun 😄 who's on the team and who do they sell to?"),
        (-28, "them", "Three people, selling to HR teams in Singapore and Hong Kong."),
        (-28, "me", "nice... let's do a call and I'll ask a lot of questions"),
        (-26, "note", "Call: Solace, 3 salespeople. Lots of inquiries, few bookings, quotes go out with no follow-up. Wants a 2-day training. Budget around USD 7,000."),
        (-24, "me", "Hey Nina, here's the proposal for the 2-day training 😄"),
        (-21, "them", "Looks good. Let's go ahead. Can we do it on the 15th?"),
        (-21, "me", "the 15th works... see you then!"),
    ],
    "Wei Zhang": [
        (-28, "me", "Hey Wei, loved your talk on data teams... how do you find your clients today?"),
        (-27, "them", "Mostly referrals. Which is great until it isn't."),
        (-27, "me", "ha exactly... want to talk about building something steadier?"),
        (-26, "them", "Sure. Monday?"),
        (-24, "note", "Call: Tidepool, Wei sells everything himself. Wants weekly coaching for 6 weeks to build an outbound routine. Budget around USD 4,000."),
        (-22, "me", "Hey Wei, here's the proposal for the 6 weeks"),
        (-20, "them", "Perfect. Let's start next week."),
    ],
    "Hannah Schmidt": [
        (-5, "them", "Hi Mohammed, I lead sales at Fieldnote. Tom said the workshop was great. Could we add a session on follow-ups?"),
        (-5, "me", "Hey Hannah, so glad it helped 😄 sure... same group of 3?"),
        (-4, "them", "Yes, plus our new hire."),
        (-4, "me", "easy... I'll send a short proposal"),
        (-3, "me", "Here it is: one half-day session on follow-ups for 4 people"),
        (-2, "them", "Approved. Let's book it."),
    ],

    "Oscar Diaz": [
        (-21, "them", "Do you do Instagram ads?"),
        (-20, "me", "Hey Oscar, not something I do sorry... hope you find someone good 😄"),
    ],
    "Priscilla Ong": [
        (-19, "them", "Hi, can you send us a list of 1,000 leads?"),
        (-18, "me", "Hey Priscilla, I don't sell lists sorry... I help teams with the conversations after the list 😄"),
        (-18, "them", "Ah ok, not what we need right now. Thanks!"),
    ],
    "Jack Turner": [
        (-24, "me", "Hey Jack, saw you're hiring in sales... how's the team going?"),
        (-23, "them", "Early days. Just me and Rafael selling for now."),
        (-22, "me", "that's the best time to set things up... want to chat?"),
        (-21, "them", "Sure, Friday?"),
        (-19, "note", "Call: Stackyard, 14 people, the founders sell. Interested in a sales playbook before the first hire. Budget around USD 3,000."),
        (-17, "me", "Hey Jack, here's the proposal for the playbook"),
        (-16, "them", "We'll pass for now, timing isn't right. Maybe after we raise."),
    ],
}
