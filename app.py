#!/usr/bin/env python3
"""WebWhizzy WhatsApp Bot v1 - AI + Contact Form + Live Human Agent"""

import os, json, re, urllib.request, urllib.error, logging
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP    = os.getenv("TWILIO_WHATSAPP", "")
ADMIN_WHATSAPP     = os.getenv("ADMIN_WHATSAPP", "")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None

IDLE="idle"; FORM_FIRST="ff"; FORM_LAST="fl"; FORM_EMAIL="fe"
FORM_BIZ="fb"; FORM_PLAN="fp"; FORM_NOTE="fn"; HUMAN_WAIT="hw"; ADMIN_REPLY="ar"
sessions: dict = {}

SYSTEM_PROMPT = """You are the WebWhizzy WhatsApp assistant. WebWhizzy builds AI-powered agents for SMS and Telegram.
Use WhatsApp formatting (*bold*, emojis). Keep replies concise and friendly.

SERVICES: SMS Agents + Telegram Agents. Both in Standard ($750 one-time) or Premium ($1,500 + $250/mo).
Standard: template workflow, 1-week delivery, 30-day support.
Premium: custom AI, advanced automation, Google Sheets logging, admin alerts, monthly updates, priority support.
HOW IT WORKS: Discovery Call -> Design & Build -> Test & Refine -> Deploy & Monitor.

Suggest CONTACT for quote form, HUMAN for live agent. Never make up info."""

MENU = ("👋 *Welcome to WebWhizzy!*\n\nWe build AI agents for SMS & Telegram - 24/7 customer conversations.\n\n"
        "💬 *SERVICES* - What we build\n💰 *PRICING* - Plans & costs\n🛠 *HOW* - How it works\n"
        "📬 *CONTACT* - Free quote\n🙋 *HUMAN* - Talk to our team\n\nOr just ask me anything! 🤖")

PLANS = {"1":"SMS Standard ($750 one-time)","2":"SMS Premium ($1,500 + $250/mo)",
         "3":"Telegram Standard ($750 one-time)","4":"Telegram Premium ($1,500 + $250/mo)","5":"Not sure yet"}

FB = {
    "pricing": ("💰 *WebWhizzy Pricing*\n\n📦 *Standard - $750* (one-time, no monthly fees)\n"
                "✓ Template workflow · SMS or Telegram · 1-week delivery\n\n"
                "⭐ *Premium - $1,500 + $250/mo*\n"
                "✓ Custom AI · Advanced automation · Google Sheets · Admin alerts · Priority support\n\n"
                "Reply *CONTACT* for a free quote! 🚀"),
    "services": ("🤖 *What We Build*\n\n💬 *SMS Agents* - Auto-replies, lead capture, follow-ups\n\n"
                 "✈️ *Telegram Agents* - Rich media, buttons, group management\n\nBoth in Standard ($750) or Premium ($1,500) 👆"),
    "how": ("🛠 *How It Works*\n\n*01.* Discovery Call\n*02.* Design & Build\n*03.* Test & Refine\n*04.* Deploy & Monitor\n\n"
            "Ready in as little as *1 week* ⚡\n\nReply *CONTACT* to start!"),
    "about": "🤖 *About WebWhizzy*\n\nSmart always-on AI agents for SMS & Telegram, 24/7.\n\n🌐 www.webwhizzy.com",
    "default": "Not sure about that! Try: SERVICES, PRICING, HOW, CONTACT, or HUMAN 😊",
}

KW = {"price|cost|how much|pricing|plan|package":"pricing",
      "service|sms|telegram|build|offer|create|what do":"services",
      "how|process|work|step|setup|timeline":"how",
      "about|who|webwhizzy|company":"about",
      "hi|hello|hey|start|menu|help":"greeting",
      "stop|unsubscribe|quit":"stop"}

def get_sess(phone):
    if phone not in sessions:
        sessions[phone]={"state":IDLE,"contact":{},"history":[],"live_client":None}
    return sessions[phone]

def wa_out(to, body):
    if not twilio_client: logger.warning(f"[NO TWILIO] {body[:60]}"); return
    to_wa = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
    try: twilio_client.messages.create(to=to_wa, from_=TWILIO_WHATSAPP, body=body[:4096])
    except Exception as e: logger.error(f"WA fail: {e}")

def twiml(text):
    r=MessagingResponse(); r.message(text[:4096])
    return Response(str(r), mimetype="text/xml")

def empty():
    return Response(str(MessagingResponse()), mimetype="text/xml")

def ask_claude(text, history):
    # Claude AI disabled - no API credits. Re-enable by restoring API call here.
    return None

def kw_match(text):
    t=text.lower()
    for pat,intent in KW.items():
        if any(k in t for k in pat.split("|")): return intent
    return None

@app.route("/whatsapp",methods=["POST"])
def webhook():
    from_raw=request.form.get("From","").strip()
    body=request.form.get("Body","").strip()
    if not from_raw or not body: return empty()
    from_num=from_raw.replace("whatsapp:","")
    sess=get_sess(from_num)
    cmd=body.upper().strip()
    admin_plain=ADMIN_WHATSAPP.replace("whatsapp:","") if ADMIN_WHATSAPP else ""
    logger.info(f"WA|{from_num[:9]}***|{sess['state']}|{body[:50]}")

    if from_num==admin_plain:
        if cmd.startswith("REPLYTO "):
            parts=body.strip().split(" ",2)
            if len(parts)>=3:
                cnum,msg=parts[1].strip(),parts[2].strip()
                wa_out(cnum,f"👤 *WebWhizzy Agent:*\n{msg}")
                sess["state"]=ADMIN_REPLY; sess["live_client"]=cnum
                if cnum in sessions: sessions[cnum]["state"]=HUMAN_WAIT
                return twiml(f"✅ Sent to {cnum}\nYou are in reply mode. Keep messaging.\nSend *DONE* to close.")
            return twiml("Usage: REPLYTO <number> <message>")
        if cmd.startswith("CLOSE "):
            parts=body.strip().split(" ",1)
            if len(parts)==2:
                cnum=parts[1].strip()
                wa_out(cnum,"✅ *Chat ended*\n\nThanks for reaching out to WebWhizzy! Message us anytime 😊")
                if cnum in sessions: sessions[cnum]["state"]=IDLE
                sess["state"]=IDLE; sess["live_client"]=None
                return twiml(f"✅ Session with {cnum} closed.")
        if cmd=="DONE":
            cnum=sess.get("live_client")
            if cnum:
                wa_out(cnum,"✅ *Chat ended by agent*\n\nThanks for chatting with WebWhizzy! 🤖")
                if cnum in sessions: sessions[cnum]["state"]=IDLE
            sess["state"]=IDLE; sess["live_client"]=None
            return twiml("✅ Session closed.")
        if sess["state"]==ADMIN_REPLY:
            cnum=sess.get("live_client")
            if cnum: wa_out(cnum,f"👤 *WebWhizzy Agent:*\n{body}"); return twiml("✅ Sent! Keep replying or send *DONE* to close.")
            sess["state"]=IDLE; return twiml("No active session. Use REPLYTO <number> <message>.")

    if cmd in("START","MENU","HELP","OPTIONS"): sess["state"]=IDLE; sess["history"]=[]; return twiml(MENU)
    if cmd in("STOP","UNSUBSCRIBE","QUIT"): sess["state"]=IDLE; return twiml("Unsubscribed. Message anytime 👋")
    if cmd=="CANCEL": sess["state"]=IDLE; return twiml("No problem! Send *MENU* anytime or just ask me anything 😊")

    if cmd=="CONTACT":
        sess["state"]=FORM_FIRST; sess["contact"]={}
        return twiml("📬 *Let's get you connected!*\n\nWhat is your *first name*?")

    if cmd=="HUMAN":
        sess["state"]=HUMAN_WAIT
        c=sess["contact"]; name=f"{c.get('first_name','')} {c.get('last_name','')}".strip() or "Someone"
        if admin_plain:
            wa_out(admin_plain,f"🔔 *Human agent request!*\n\n👤 *{name}*\n📱 {from_num}\n\n*Reply:* REPLYTO {from_num} your message\n*Close:* CLOSE {from_num}")
        return twiml("🙋 *Connecting you to our team!*\n\nAn agent has been notified and will join shortly.\n\nType your message now! 💬\n\n_(Type CANCEL to return to AI)_")

    if cmd in("SERVICES","SERVICE"): return twiml(FB["services"])
    if cmd=="PRICING": return twiml(FB["pricing"])
    if cmd in("HOW","HOWITWORKS"): return twiml(FB["how"])
    if cmd=="ABOUT": return twiml(FB["about"])

    state=sess["state"]
    if state==FORM_FIRST:
        sess["contact"]["first_name"]=body.strip(); sess["state"]=FORM_LAST
        return twiml(f"Nice to meet you, *{body.strip()}*! 👋\n\nWhat is your *last name*?")
    if state==FORM_LAST:
        sess["contact"]["last_name"]=body.strip(); sess["state"]=FORM_EMAIL
        return twiml("What is your *email address*? ✉️")
    if state==FORM_EMAIL:
        if not re.match(r"[^@]+@[^@]+\.[^@]+",body.strip()): return twiml("That does not look right. Please double-check your email 🙏")
        sess["contact"]["email"]=body.strip(); sess["state"]=FORM_BIZ
        return twiml("What is your *business name*? 🏢")
    if state==FORM_BIZ:
        sess["contact"]["business"]=body.strip(); sess["state"]=FORM_PLAN
        return twiml("Which plan interests you?\n\n1️⃣ SMS Standard ($750)\n2️⃣ SMS Premium ($1,500+)\n3️⃣ Telegram Standard ($750)\n4️⃣ Telegram Premium ($1,500+)\n5️⃣ Not sure yet\n\nReply 1-5")
    if state==FORM_PLAN:
        sess["contact"]["plan"]=PLANS.get(body.strip(),body.strip()); sess["state"]=FORM_NOTE
        return twiml("Almost done! 🎉\n\nAny details about your business or automation needs?\n_(Reply SKIP to leave blank)_")
    if state==FORM_NOTE:
        note="" if body.upper().strip()=="SKIP" else body.strip()
        sess["contact"]["note"]=note
        c=sess["contact"]
        first,last=c.get("first_name",""),c.get("last_name","")
        email,biz,plan=c.get("email",""),c.get("business",""),c.get("plan","")
        confirm=(f"✅ *All done, {first}!*\n\n👤 *Name:* {first} {last}\n✉️ *Email:* {email}\n"
                 f"🏢 *Business:* {biz}\n📦 *Plan:* {plan}\n")
        if note: confirm+=f"💬 *Note:* {note}\n"
        confirm+="\nWe will be in touch within *24 hours*. 🚀"
        sess["state"]=IDLE
        logger.info(f"LEAD|{first} {last}|{email}|{biz}|{plan}|{from_num}")
        if admin_plain:
            amsg=f"🔔 *New Lead!*\n\n👤 {first} {last}\n✉️ {email}\n🏢 {biz}\n📦 {plan}\n"
            if note: amsg+=f"💬 {note}\n"
            amsg+=f"📱 {from_num}\n\n*Reply:* REPLYTO {from_num} your message"
            wa_out(admin_plain,amsg)
        sess["contact"]={}; return twiml(confirm)
    if state==HUMAN_WAIT:
        c=sess["contact"]; name=f"{c.get('first_name','')} {c.get('last_name','')}".strip() or from_num
        if admin_plain:
            wa_out(admin_plain,f"📩 *Msg from {name}*\n📱 {from_num}\n\n_{body}_\n\n*Reply:* REPLYTO {from_num} your message\n*Close:* CLOSE {from_num}")
        return twiml("📨 Message sent to our team! They will reply shortly 🙋")

    ai=ask_claude(body,sess["history"])
    if ai:
        sess["history"].append({"role":"user","content":body})
        sess["history"].append({"role":"assistant","content":ai})
        if len(sess["history"])>16: sess["history"]=sess["history"][-16:]
        return twiml(ai)
    intent=kw_match(body)
    if intent=="greeting": sess["history"]=[]; return twiml(MENU)
    if intent=="stop": return twiml("Unsubscribed. Message anytime 👋")
    if intent and intent in FB: return twiml(FB[intent])
    return twiml(FB["default"])

@app.route("/",methods=["GET"])
def health():
    active=sum(1 for s in sessions.values() if s["state"]!=IDLE)
    return f"WebWhizzy WhatsApp Bot running | Active sessions: {active}", 200

if __name__=="__main__":
    port=int(os.getenv("PORT",5000))
    logger.info(f"Starting on port {port}")
    app.run(host="0.0.0.0",port=port)
