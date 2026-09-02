# NYSS Bakes WhatsApp Lead Bot
# Requirements: pip install flask twilio openai python-dotenv redis

import os
import json
import re
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict, field

from flask import Flask, request, jsonify
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client as TwilioClient
from openai import OpenAI
from dotenv import load_dotenv
import redis

load_dotenv()

# ─── Config ──────────────────────────────────────────────────────────────
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WA_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
BUSINESS_NAME = os.getenv("BUSINESS_NAME", "NYSS Bakes")
BUSINESS_PHONE = os.getenv("BUSINESS_PHONE")
LEAD_EMAIL = os.getenv("LEAD_EMAIL")
REDIS_URL = os.getenv("REDIS_URL")
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE_URL", "http://localhost:5000")

twilio = TwilioClient(TWILIO_SID, TWILIO_TOKEN) if TWILIO_SID else None
openai = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None
redis_client = redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None

app = Flask(__name__)

# ─── Conversation State Machine ─────────────────────────────────────────
class State(Enum):
    GREETING = "greeting"
    INTEREST = "interest"           # What are they looking for?
    OCCASION = "occasion"           # Wedding, corporate, birthday, etc.
    QUANTITY = "quantity"           # How many pieces/boxes?
    DESIGN = "design"               # Custom design or ready-made?
    TIMELINE = "timeline"           # When needed?
    CONTACT = "contact"             # Capture name, email, location
    QUOTE = "quote"                 # Send quote / handoff to human
    COMPLETE = "complete"

@dataclass
class Lead:
    phone: str
    name: str = ""
    email: str = ""
    location: str = ""
    occasion: str = ""
    product_type: str = ""          # macarons, cakes, cupcakes, cookies, amenity
    quantity: str = ""
    design_type: str = ""           # custom, ready-made, both
    timeline: str = ""
    budget: str = ""
    notes: str = ""
    state: State = State.GREETING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Lead":
        data = data.copy()
        data["state"] = State(data.get("state", "greeting"))
        return cls(**data)

# ─── Session Management ─────────────────────────────────────────────────
SESSION_TTL = 86400 * 3  # 3 days

def get_session(phone: str) -> Lead:
    key = f"lead:{phone}"
    if redis_client:
        data = redis_client.get(key)
        if data:
            return Lead.from_dict(json.loads(data))
    return Lead(phone=phone)

def save_session(lead: Lead):
    lead.updated_at = datetime.now().isoformat()
    key = f"lead:{lead.phone}"
    data = json.dumps(lead.to_dict())
    if redis_client:
        redis_client.setex(key, SESSION_TTL, data)

def clear_session(phone: str):
    if redis_client:
        redis_client.delete(f"lead:{phone}")

# ─── AI Helpers ─────────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are a friendly WhatsApp assistant for {BUSINESS_NAME}, a premium edible printing bakery in South Africa.
We print custom images, logos, photos, quotes onto macarons, cakes, cupcakes, cookies using 100% food-grade edible ink.

Your job: Qualify leads conversationally. Be warm, South African (use 'we', 'our', not 'I'). Keep replies under 160 chars where possible.
Ask ONE question at a time. Never reveal you're an AI.

Products: Macarons (specialty), Cakes, Cupcakes, Cookies, Hotel amenity treats
Occasions: Weddings, Corporate gifting, Baby showers, Birthdays, Brand activations, Holidays
Turnaround: 24-48h typical. Minimum order: 12 macarons / 1 cake / 12 cupcakes.

When lead is qualified (occasion + quantity + timeline + contact), summarize and say a human will follow up with quote within 2 hours."""

def ai_reply(prompt: str, lead: Lead) -> str:
    if not openai:
        return "Thanks! Our team will WhatsApp you shortly with a quote. 🍰"
    
    context = f"""Lead info so far:
- Occasion: {lead.occasion or 'unknown'}
- Product: {lead.product_type or 'unknown'}
- Quantity: {lead.quantity or 'unknown'}
- Design: {lead.design_type or 'unknown'}
- Timeline: {lead.timeline or 'unknown'}
- Location: {lead.location or 'unknown'}
- Name: {lead.name or 'unknown'}

Current state: {lead.state.value}"""
    
    try:
        resp = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": context},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.7
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI error: {e}")
        return "Thanks! Our team will WhatsApp you shortly with a quote. 🍰"

# ─── State Transitions & Extraction ─────────────────────────────────────
OCCASION_KEYWORDS = {
    "wedding": ["wedding", "marriage", "bridal", "engagement"],
    "baby_shower": ["baby shower", "sonogram", "ultrasound", "gender reveal", "pregnancy"],
    "birthday": ["birthday", "bday", "born day"],
    "holiday": ["christmas", "easter", "holiday", "festive", "valentine", "mother's day", "father's day"],
    "activation": ["activation", "conference", "launch", "exhibition", "trade show", "event branding"],
    "corporate": ["corporate", "business", "company", "brand", "logo", "gift", "client", "staff", "gifting"],
}

PRODUCT_KEYWORDS = {
    "macarons": ["macaron", "macarons"],
    "cupcakes": ["cupcake", "cupcakes"],
    "cakes": ["cake", "cakes", "tier"],
    "cookies": ["cookie", "cookies", "biscuit"],
    "amenity": ["amenity", "hotel", "hospitality", "turndown", "mini"],
}

def extract_occasion(text: str) -> Optional[str]:
    text = text.lower()
    for occasion, kws in OCCASION_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return occasion.replace("_", " ").title()
    return None

def extract_product(text: str) -> Optional[str]:
    text = text.lower()
    for prod, kws in PRODUCT_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return prod.title()
    return None

def extract_quantity(text: str) -> Optional[str]:
    # Look for numbers with context
    patterns = [
        r'(\d+)\s*(?:macarons?|cupcakes?|cakes?|cookies?|boxes?|pieces?|units?|people|guests|pax)',
        r'(?:need|want|order|quantity|qty)\D*(\d+)',
        r'\b(\d{1,3})\b',  # standalone 1-3 digit number
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None

def extract_timeline(text: str) -> Optional[str]:
    text = text.lower()
    if any(w in text for w in ["urgent", "asap", "tomorrow", "today", "emergency"]):
        return "Urgent (ASAP)"
    if any(w in text for w in ["week", "7 day", "next week"]):
        return "Within a week"
    if any(w in text for w in ["month", "4 week", "next month"]):
        return "Within a month"
    if any(w in text for w in ["flexible", "whenever", "no rush", "open"]):
        return "Flexible"
    # Specific date
    date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
    if date_match:
        return f"By {date_match.group(1)}"
    return None

def extract_location(text: str) -> Optional[str]:
    # SA suburbs/areas first (more specific), then cities, then provinces
    sa_locations = [
        # Suburbs/areas (more specific - check first)
        "sandton", "rosebank", "fourways", "bryanston", "hyde park", "morningside",
        "cape town cbd", "camps bay", "sea point", "clifton", "constantia", "rondebosch",
        "durban north", "umhlanga", "ballito", "la lucia", "berea",
        "pretoria east", "waterkloof", "brooklyn", "hatfield", "menlyn",
        "centurion", "midrand", "kempton park", "bedfordview", "edenvale",
        "bloemfontein", "polokwane", "nelspruit", "mbombela", "rustenburg",
        "potchefstroom", "klerksdorp", "welkom", "kimberley", "mahikeng",
        # Cities
        "johannesburg", "joburg", "jhb", "pretoria", "tshwane",
        "cape town", "capetown", "cpt", "durban", "dbn", "port elizabeth",
        "pe", "bloemfontein", "polokwane", "nelspruit", "mbombela",
        # Provinces
        "gauteng", "western cape", "kwazulu-natal", "kzn", "free state",
        "limpopo", "mpumalanga", "north west", "northern cape", "eastern cape"
    ]
    text = text.lower()
    for loc in sa_locations:
        if loc in text:
            return loc.title()
    return None

def extract_name(text: str, lead: Lead) -> Optional[str]:
    # If they haven't given name yet, and this looks like a name
    if lead.name:
        return None
    # Skip obvious non-names
    text_lower = text.lower().strip()
    if any(text_lower.startswith(w) for w in ["hi", "hello", "hey", "good", "i'm", "im ", "i am", "my name", "this is"]):
        return None
    if any(w in text_lower for w in ["thanks", "thank you", "ok", "okay", "sure", "yes", "no", "maybe"]):
        return None
    # Simple heuristic: 1-3 words, capitalized, not a sentence
    words = text.strip().split()
    if 1 <= len(words) <= 3 and all(w[0].isupper() for w in words if w):
        # Not a question, not too long, no punctuation
        if not any(c in text for c in "?.!") and len(text) < 30:
            return text.strip().title()
    return None

def extract_email(text: str) -> Optional[str]:
    m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return m.group(0) if m else None

# ─── Message Templates ──────────────────────────────────────────────────
TEMPLATES = {
    State.GREETING: (
        "Hey! Welcome to NYSS Bakes 👋\n"
        "We print *anything* — photos, logos, sonograms, artwork — "
        "in edible ink on macarons, cakes, cupcakes & cookies.\n\n"
        "What's the occasion? 🎂"
    ),
    State.INTEREST: (
        "Love it! What are you looking to have printed?\n"
        "• A photo / sonogram\n"
        "• Company logo / branding\n"
        "• Custom illustration / quote\n"
        "• Something else?"
    ),
    State.OCCASION: (
        "Perfect. What's the occasion?\n"
        "💍 Wedding\n"
        "🏢 Corporate gifting / brand activation\n"
        "👶 Baby shower / gender reveal\n"
        "🎂 Birthday\n"
        "🎄 Holiday / seasonal\n"
        "📅 Other event"
    ),
    State.QUANTITY: (
        "Great choice! How many pieces/boxes do you need?\n"
        "(Minimums: 12 macarons | 1 cake | 12 cupcakes | 24 cookies)"
    ),
    State.DESIGN: (
        "Got it. Do you have a design ready, or would you like us to create a mockup?\n"
        "📸 I have the image/logo ready\n"
        "✏️ Design it for me\n"
        "🤔 Not sure yet"
    ),
    State.TIMELINE: (
        "When do you need them by?\n"
        "⚡ Urgent (1-2 days)\n"
        "📅 Within a week\n"
        "📆 Within a month\n"
        "😌 Flexible"
    ),
    State.CONTACT: (
        "Almost there! To send your quote, I need:\n"
        "1. Your name\n"
        "2. Email address\n"
        "3. Delivery area (e.g. Sandton, Cape Town CBD, etc.)"
    ),
}

# ─── Core Flow ──────────────────────────────────────────────────────────
def process_message(phone: str, body: str) -> str:
    lead = get_session(phone)
    body_clean = body.strip()
    
    # Handle media (images) - user sent a design
    if request.values.get("NumMedia", "0") != "0":
        lead.metadata.setdefault("media", []).append({
            "url": request.values.get("MediaUrl0"),
            "type": request.values.get("MediaContentType0"),
            "at": datetime.now().isoformat()
        })
        if lead.state in [State.DESIGN, State.INTEREST]:
            lead.state = State.TIMELINE
            save_session(lead)
            return "Perfect — got your image! 📸 When do you need the order by?"
    
    # Extract info at every step
    if occasion := extract_occasion(body_clean):
        lead.occasion = occasion
    if product := extract_product(body_clean):
        lead.product_type = product
    if qty := extract_quantity(body_clean):
        lead.quantity = qty
    if timeline := extract_timeline(body_clean):
        lead.timeline = timeline
    if location := extract_location(body_clean):
        lead.location = location
    if name := extract_name(body_clean, lead):
        lead.name = name
    if email := extract_email(body_clean):
        lead.email = email
    
    # State machine
    if lead.state == State.GREETING:
        lead.state = State.OCCASION
        save_session(lead)
        return TEMPLATES[State.OCCASION]
    
    elif lead.state == State.OCCASION:
        if lead.occasion:
            lead.state = State.QUANTITY
            save_session(lead)
            return TEMPLATES[State.QUANTITY]
        return ai_reply(body_clean, lead)
    
    elif lead.state == State.QUANTITY:
        if lead.quantity:
            lead.state = State.DESIGN
            save_session(lead)
            return TEMPLATES[State.DESIGN]
        return ai_reply(body_clean, lead)
    
    elif lead.state == State.DESIGN:
        # Check for design readiness
        text = body_clean.lower()
        if any(w in text for w in ["ready", "have", "sent", "image", "logo", "photo", "file", "attachment"]):
            lead.design_type = "customer_provided"
        elif any(w in text for w in ["design", "create", "mockup", "make", "you do"]):
            lead.design_type = "custom_design"
        else:
            lead.design_type = "undecided"
        
        lead.state = State.TIMELINE
        save_session(lead)
        return TEMPLATES[State.TIMELINE]
    
    elif lead.state == State.TIMELINE:
        if lead.timeline:
            lead.state = State.CONTACT
            save_session(lead)
            return TEMPLATES[State.CONTACT]
        return ai_reply(body_clean, lead)
    
    elif lead.state == State.CONTACT:
        # Check if we have minimum info
        if lead.name and lead.email and lead.location:
            lead.state = State.QUOTE
            save_session(lead)
            return send_quote_summary(lead)
        # Prompt for missing fields
        missing = []
        if not lead.name: missing.append("name")
        if not lead.email: missing.append("email")
        if not lead.location: missing.append("delivery area")
        return f"Just need your {', '.join(missing)} to send the quote! 📝"
    
    elif lead.state == State.QUOTE:
        # Already quoted - offer next steps
        return (
            "Your quote request is with our team! 📋\n"
            "We'll WhatsApp you a detailed quote + mockup within 2 hours.\n\n"
            "Want to:\n"
            "1️⃣ Start another order\n"
            "2️⃣ Speak to a human now\n"
            "3️⃣ See ready-to-order boxes → nyss-bakes.netlify.app"
        )
    
    return ai_reply(body_clean, lead)

def send_quote_summary(lead: Lead) -> str:
    # Build summary for internal team
    summary = f"""🆕 *NEW LEAD - {BUSINESS_NAME}*
    
*Name:* {lead.name}
*Phone:* {lead.phone}
*Email:* {lead.email}
*Location:* {lead.location}
*Occasion:* {lead.occasion}
*Product:* {lead.product_type}
*Quantity:* {lead.quantity}
*Design:* {lead.design_type}
*Timeline:* {lead.timeline}
*Media attached:* {len(lead.metadata.get('media', []))} file(s)
*Received:* {datetime.now().strftime('%d %b %Y %H:%M')}"""

    # Send to business via WhatsApp (if configured)
    if twilio and BUSINESS_PHONE:
        try:
            twilio.messages.create(
                from_=TWILIO_WA_NUMBER,
                to=f"whatsapp:{BUSINESS_PHONE}",
                body=summary
            )
        except Exception as e:
            print(f"Failed to notify business: {e}")
    
    # Also email
    # (add sendgrid/mailgun here if needed)
    
    lead.state = State.QUOTE
    save_session(lead)
    
    return (
        "Thanks! I've sent your details to our team. 🎉\n\n"
        "You'll get a *detailed quote + design mockup* on WhatsApp within **2 hours**.\n\n"
        "Typical turnaround: 24-48h once design approved.\n"
        "Delivery: We courier nationwide 🇿🇦\n\n"
        "Questions? Just reply here — a human will take over."
    )

# ─── Flask Routes ───────────────────────────────────────────────────────
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    phone = request.form.get("From", "").replace("whatsapp:", "")
    body = request.form.get("Body", "")
    
    if not phone:
        return "OK", 200
    
    reply_text = process_message(phone, body)
    
    resp = MessagingResponse()
    resp.message(reply_text)
    return str(resp), 200, {"Content-Type": "application/xml"}

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "business": BUSINESS_NAME})

@app.route("/leads", methods=["GET"])
def list_leads():
    if not redis_client:
        return jsonify({"error": "Redis not configured"}), 500
    keys = redis_client.keys("lead:*")
    leads = []
    for k in keys:
        data = redis_client.get(k)
        if data:
            leads.append(json.loads(data))
    return jsonify({"count": len(leads), "leads": leads})

# ─── Run ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"Starting {BUSINESS_NAME} WhatsApp bot on port {port}")
    print(f"Webhook: {WEBHOOK_BASE}/whatsapp")
    app.run(host="0.0.0.0", port=port, debug=True)