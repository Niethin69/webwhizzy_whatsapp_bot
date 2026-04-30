#!/usr/bin/env python3
"""
WebWhizzy WhatsApp Bot - Professional Edition
Powered by Claude AI + Twilio WhatsApp
"""

import os, json, re, urllib.request, logging
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP    = os.getenv("TWILIO_WHATSAPP", "whatsapp:+14155238886")
ADMIN_WHATSAPP     = os.getenv("ADMIN_WHATSAPP", "")
ADMIN_WHATSAPP_2   = os.getenv("ADMIN_WHATSAPP_2", "")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None

IDLE="idle"; FORM_FIRST="ff"; FORM_LAST="fl"; FORM_EMAIL="fe"
FORM_BIZ="fb"; FORM_PLAN="fp"; FORM_NOTE="fn"; HUMAN_WAIT="hw"; ADMIN_REPLY="ar"
sessions: dict = {}

SYSTEM_PROMPT = """You are the WebWhizzy virtual assistant - professional, warm, and knowledgeable.

WebWhizzy builds custom AI-powered agents for WhatsApp, SMS, and Telegram that handle customer conversations, automate workflows, and grow businesses 24/7.

SERVICES: WhatsApp Agents (queries, media, leads, follow-ups), SMS Agents (no app required, reach everyone), Telegram Agents (rich media, buttons, groups, automation).

CAPABILITIES: Sub-second responses 24/7, context-aware AI, workflow automation (CRM/email/Sheets), lead qualification, admin alerts and daily summaries (Premium), monthly updates and priority support (Premium).

PRICING:
Standard $750 one-time: Custom bot, rule-based workflows, auto-replies, FAQs, lead collection, 1-week delivery, 30-day support.
Premium $1,500 + $250/month: Everything in Standard plus AI NLU, sentiment analysis, human handoff, smart fallback, admin alerts, logs, monthly updates, priority support.

HOW IT WORKS: 01 Discovery Call > 02 Design & Build > 03 Test & Refine > 04 Deploy & Monitor. Delivery in 1 week.

Use WhatsApp formatting (*bold*, emojis). Keep replies professional and concise.
Suggest CONTACT for a free quote or HUMAN to speak with the team.
Website: www.webwhizzy.com | Email: info@webwhizzy.com"""

WELCOME = ("*Welcome to WebWhizzy!*\n\n"
    "We build AI-powered agents for WhatsApp, SMS, and Telegram that handle your customer conversations 24/7.\n\n"
    "How can I help you today?\n\n"
    "SERVICES - What we build\n"
    "PRICING - Plans & investment\n"
    "HOW - Our process\n"
    "CONTACT - Get a free quote\n"
    "HUMAN - Speak with our team\n\n"
    "_Or just ask me anything._")

SERVICES = ("*What WebWhizzy Builds*\n\n"
    "*WhatsApp Agents*\nHandle queries, rich media, lead capture & follow-ups inside the world's most-used messaging app.\n\n"
    "*SMS Agents*\nReach every customer - no app required. Inquiries, updates & lead capture via native texting.\n\n"
    "*Telegram Agents*\nRich media, inline buttons, group management & deep automation.\n\n"
    "All available in *Standard ($750)* or *Premium ($1,500 + $250/mo)*.")

PRICING = ("*WebWhizzy Pricing*\n\n"
    "Standard - $750\n_One-time setup, no monthly fees_\n"
    "Fully customised bot, rule-based workflows, auto-replies, FAQs & lead collection, 1-week delivery, 30-day support.\n\n"
    "Premium - $1,500 + $250/mo\n_Most popular_\n"
    "Everything in Standard plus: AI natural language understanding, sentiment analysis, human handoff, admin alerts & logs, monthly updates & priority support.\n\n"
    "_All prices in USD. Setup includes deployment, testing & onboarding._")

HOW = ("*How It Works*\n\n"
    "*01 - Discovery Call*\nWe learn about your business, customers & workflows.\n\n"
    "*02 - Design & Build*\nYour custom agent is built to your exact use case.\n\n"
    "*03 - Test & Refine*\nRigorous testing before going live.\n\n"
    "*04 - Deploy & Monitor*\nYour agent goes live. Premium clients get ongoing monitoring & updates.\n\n"
    "_Typical delivery: 1 week from kickoff._")

PLANS = {"1":"WhatsApp - Standard ($750 one-time)","2":"WhatsApp - Premium ($1,500 + $250/mo)",
         "3":"SMS - Standard ($750 one-time)","4":"SMS - Premium ($1,500 + $250/mo)",
         "5":"Telegram - Standard ($750 one-time)","6":"Telegram - Premium ($1,500 + $250/mo)","7":"Not sure yet - help me decide"}

PLAN_MENU = ("Which plan interests you?\n\n"
    "1. WhatsApp Standard ($750)\n2. WhatsApp Premium ($1,500+)\n"
    "3. SMS Standard ($750)\n4. SMS Premium ($1,500+)\n"
    "5. Telegram Standard ($750)\n6. Telegram Premium ($1,500+)\n"
    "7. Not sure yet\n\nReply with a number (1-7)")

def get_admin_numbers():
    admins = []
    if ADMIN_WHATSAPP: admins.append(ADMIN_WHATSAPP.replace("whatsapp:","").strip())
    if ADMIN_WHATSAPP_2: admins.append(ADMIN_WHATSAPP_2.replace("whatsapp:","").strip())
    return admins

def is_admin(phone): return phone in get_admin_numbers()

def get_sess(phone):
    if phone not in sessions:
        sessions[phone]={"state":IDLE,"contact":{},"history":[],"live_client":None}
    return sessions[phone]

def wa_out(to, body):
    if not twilio_client: logger.warning(f"[NO TWILIO] {body[:60]}"); return
    to_wa = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
    try: twilio_client.messages.create(to=to_wa, from_=TWILIO_WHATSAPP, body=body[:4096])
    except Exception as e: logger.error(f"WA fail: {e}")

def alert_admins(msg):
    for admin in get_admin_numbers(): wa_out(admin, msg)

def twiml(text):
    r=MessagingResponse(); r.message(text[:4096])
    return Response(str(r), mimetype="text/xml")

def empty(): return Response(str(MessagingResponse()), mimetype="text/xml")

def ask_claude(text, history):
    if not ANTHROPIC_API_KEY: return None
    msgs=history[-8:]+[{"role":"user","content":text}]
    payload=json.dumps({"model":"claude-haiku-4-5-20251001","max_tokens":350,"system":SYSTEM_PROMPT,"messages":msgs}).encode()
    req=urllib.request.Request("https://api.anthropic.com/v1/messages",data=payload,
        headers={"Content-Type":"application/json","x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=15) as r: return json.loads(r.read())["content"][0]["text"].strip()
    except Exception as e: logger.error(f"Claude: {e}"); return None

def kw(text,*words): return any(w in text.lower() for w in words)

@app.route("/whatsapp",methods=["POST"])
def webhook():
    from_raw=request.form.get("From","").strip()
    body=request.form.get("Body","").strip()
    if not from_raw or not body: return empty()
    from_num=from_raw.replace("whatsapp:","")
    sess=get_sess(from_num); cmd=body.upper().strip()
    logger.info(f"WA|{from_num[:9]}***|{sess['state']}|{body[:60]}")

    if is_admin(from_num):
        if cmd.startswith("REPLYTO "):
            parts=body.strip().split(" ",2)
            if len(parts)>=3:
                cnum,msg=parts[1].strip(),parts[2].strip()
                wa_out(cnum,f"*WebWhizzy Team:*\n{msg}")
                sess["state"]=ADMIN_REPLY; sess["live_client"]=cnum
                if cnum in sessions: sessions[cnum]["state"]=HUMAN_WAIT
                return twiml(f"Sent to {cnum}. Reply mode active. Send DONE to close.")
            return twiml("Usage: REPLYTO <number> <message>")
        if cmd.startswith("CLOSE "):
            parts=body.strip().split(" ",1)
            if len(parts)==2:
                cnum=parts[1].strip()
                wa_out(cnum,"*Session Ended*\n\nThank you for reaching out to WebWhizzy. Feel free to message us anytime.")
                if cnum in sessions: sessions[cnum]["state"]=IDLE
                sess["state"]=IDLE; sess["live_client"]=None
                return twiml(f"Session with {cnum} closed.")
        if cmd=="DONE":
            cnum=sess.get("live_client")
            if cnum:
                wa_out(cnum,"*Chat Ended*\n\nThank you for chatting with WebWhizzy! We look forward to working with you.")
                if cnum in sessions: sessions[cnum]["state"]=IDLE
            sess["state"]=IDLE; sess["live_client"]=None
            return twiml("Session closed.")
        if sess["state"]==ADMIN_REPLY:
            cnum=sess.get("live_client")
            if cnum: wa_out(cnum,f"*WebWhizzy Team:*\n{body}"); return twiml("Delivered. Keep replying or DONE to close.")
            sess["state"]=IDLE; return twiml("No active session. Use REPLYTO <number> <message>.")

    if cmd in("START","MENU","HELP","HI","HELLO","HEY"): sess["state"]=IDLE; sess["history"]=[]; return twiml(WELCOME)
    if cmd in("STOP","UNSUBSCRIBE"): sess["state"]=IDLE; return twiml("You've been unsubscribed. Message us anytime to reconnect.")
    if cmd=="CANCEL": sess["state"]=IDLE; return twiml("No problem. Send MENU to see your options or ask me anything.")
    if cmd=="SERVICES": return twiml(SERVICES)
    if cmd=="PRICING": return twiml(PRICING)
    if cmd in("HOW","PROCESS"): return twiml(HOW)

    if cmd=="CONTACT":
        sess["state"]=FORM_FIRST; sess["contact"]={}
        return twiml("*Let's Get You a Free Quote*\n\nI'll collect a few details so our team can reach out within 24 hours.\n\nWhat is your *first name*?")

    if cmd=="HUMAN":
        sess["state"]=HUMAN_WAIT
        c=sess["contact"]; name=f"{c.get('first_name','')} {c.get('last_name','')}".strip() or "A visitor"
        alert_admins(f"*New Human Handoff Request*\n\nName: {name}\nNumber: {from_num}\n\nReply: REPLYTO {from_num} <message>\nClose: CLOSE {from_num}")
        return twiml("*Connecting You to Our Team*\n\nA WebWhizzy team member has been notified and will join shortly.\n\nType your message now.\n_(Type CANCEL to return to AI)_")

    state=sess["state"]
    if state==FORM_FIRST:
        sess["contact"]["first_name"]=body.strip(); sess["state"]=FORM_LAST
        return twiml(f"Nice to meet you, *{body.strip()}*!\n\nWhat is your *last name*?")
    if state==FORM_LAST:
        sess["contact"]["last_name"]=body.strip(); sess["state"]=FORM_EMAIL
        return twiml("What is your *email address*?\n_We'll use this to send you our proposal._")
    if state==FORM_EMAIL:
        if not __import__("re").match(r"[^@]+@[^@]+\.[^@]+",body.strip()): return twiml("That doesn't look valid. Please check and try again:")
        sess["contact"]["email"]=body.strip(); sess["state"]=FORM_BIZ
        return twiml("What is your *business name*?")
    if state==FORM_BIZ:
        sess["contact"]["business"]=body.strip(); sess["state"]=FORM_PLAN
        return twiml(PLAN_MENU)
    if state==FORM_PLAN:
        sess["contact"]["plan"]=PLANS.get(body.strip(),body.strip()); sess["state"]=FORM_NOTE
        return twiml("Almost there!\n\nAny details about your business or what you'd like to automate?\n_(Reply SKIP to leave blank)_")
    if state==FORM_NOTE:
        note="" if body.upper().strip()=="SKIP" else body.strip()
        sess["contact"]["note"]=note
        c=sess["contact"]; first,last=c.get("first_name",""),c.get("last_name","")
        email,biz,plan=c.get("email",""),c.get("business",""),c.get("plan","")
        confirm=(f"*All Done, {first}!*\n\nEnquiry summary:\n\nName: {first} {last}\nEmail: {email}\nBusiness: {biz}\nPlan: {plan}\n")
        if note: confirm+=f"Notes: {note}\n"
        confirm+="\nOur team will be in touch within *24 hours* with a tailored proposal. Thank you for choosing WebWhizzy!"
        sess["state"]=IDLE; logger.info(f"LEAD|{first} {last}|{email}|{biz}|{plan}|{from_num}")
        amsg=(f"*New Lead - WebWhizzy*\n\n{first} {last}\n{email}\n{biz}\n{plan}\n"+(f"{note}\n" if note else "")+f"{from_num}\n\nREPLYTO {from_num} <message>")
        alert_admins(amsg); sess["contact"]={}; return twiml(confirm)
    if state==HUMAN_WAIT:
        c=sess["contact"]; name=f"{c.get('first_name','')} {c.get('last_name','')}".strip() or from_num
        alert_admins(f"*Message from {name}*\n{from_num}\n\n_{body}_\n\nREPLYTO {from_num} <message>\nCLOSE {from_num}")
        return twiml("Message received. Our team will reply shortly. Thank you for your patience.")

    if kw(body,"price","cost","how much","pricing","plan"): return twiml(PRICING)
    if kw(body,"service","what do you","offer","build"): return twiml(SERVICES)
    if kw(body,"how does","process","how do you"): return twiml(HOW)
    if kw(body,"hi","hello","hey","start"): sess["history"]=[]; return twiml(WELCOME)

    ai=ask_claude(body,sess["history"])
    if ai:
        sess["history"].append({"role":"user","content":body}); sess["history"].append({"role":"assistant","content":ai})
        if len(sess["history"])>16: sess["history"]=sess["history"][-16:]
        return twiml(ai)
    return twiml("I'm not sure how to help with that. Reply MENU to see options, CONTACT for a quote, or HUMAN to speak with us.")

@app.route("/",methods=["GET"])
def health():
    active=sum(1 for s in sessions.values() if s["state"]!=IDLE)
    return f"WebWhizzy WhatsApp Bot | Active sessions: {active}", 200

if __name__=="__main__":
    port=int(os.getenv("PORT",5000))
    logger.info(f"WebWhizzy WhatsApp Bot starting on port {port}")
    app.run(host="0.0.0.0",port=port)
