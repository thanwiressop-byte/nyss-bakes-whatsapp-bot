# NYSS Bakes WhatsApp Bot — Quick Start

## 1. Prerequisites
- Python 3.10+
- Twilio account (free trial works)
- OpenAI API key
- ngrok (for local webhook testing)

## 2. Setup

```bash
# Clone / navigate
cd nyss-bakes-whatsapp-bot

# Create virtual env
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install deps
pip install -r requirements.txt

# Copy env template
cp .env.example .env
# Edit .env with your keys (see below)
```

## 3. Configure `.env`

```bash
# Required
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886  # Sandbox number
OPENAI_API_KEY=sk-xxxxxxxxxxxx

# Business (update these)
BUSINESS_PHONE=+27XXXXXXXXX  # Your SA WhatsApp number for handoff
LEAD_EMAIL=orders@nyss-bakes.co.za

# Optional (for production)
REDIS_URL=redis://localhost:6379
WEBHOOK_BASE_URL=https://your-domain.com
```

### Get Twilio Sandbox Credentials
1. Go to [Twilio Console → Messaging → Try it out → WhatsApp](https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn)
2. Note your `Account SID` and `Auth Token`
3. Sandbox number is `+1 415 523 8886` (join by sending "join <code>" to it)

## 4. Run Locally

```bash
# Terminal 1: Start bot
python app.py

# Terminal 2: Expose webhook
ngrok http 5000
# Copy the https://xxxx.ngrok-free.app URL
```

## 5. Configure Twilio Webhook
1. In Twilio Console → Messaging → Try it out → WhatsApp
2. Set **Webhook URL** to: `https://YOUR-NGROK-URL.ngrok-free.app/whatsapp`
3. Method: `POST`
4. Save

## 6. Test
1. Send "join <your-sandbox-code>" to `+1 415 523 8886` on WhatsApp
2. Send "Hi" — bot should reply with occasion options
3. Walk through the flow

## 7. Production Deploy

### Option A: Render (free tier)
1. Push to GitHub
2. Connect repo on [Render](https://render.com)
3. Build: `pip install -r requirements.txt`
4. Start: `gunicorn app:app`
5. Add env vars in Render dashboard
6. Update Twilio webhook to Render URL

### Option B: Railway / Fly.io / VPS
Similar — just need a public HTTPS URL.

### Option C: Twilio Functions (serverless)
- Paste `app.py` logic into a Twilio Function
- No server management
- Limited to 10s execution time

## 8. Go Live (Exit Sandbox)
1. Apply for [WhatsApp Business API](https://business.whatsapp.com/)
2. Verify business (Meta Business Manager)
3. Port/buy a number
4. Update `TWILIO_WHATSAPP_NUMBER` to your verified number
5. Remove sandbox join requirement

## 9. Customize for NYSS Bakes

Edit `app.py`:
- `SYSTEM_PROMPT` — tweak tone, add FAQs
- `TEMPLATES` — change questions/order
- `OCCASION_KEYWORDS` / `PRODUCT_KEYWORDS` — add synonyms
- Minimums/pricing in `TEMPLATES[State.QUANTITY]`
- Add media handling for design uploads

## 10. Monitor Leads

```bash
# View all leads (requires Redis)
curl http://localhost:5000/leads
```

Or check Twilio Conversations inbox for full chat history.

## Support
- Twilio WhatsApp docs: https://www.twilio.com/docs/whatsapp
- Meta WhatsApp Business API: https://developers.facebook.com/docs/whatsapp
- Issues? Check logs: `python app.py` output