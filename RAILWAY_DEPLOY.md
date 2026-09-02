# NYSS Bakes WhatsApp Bot - Railway Deploy
# 
# Quick deploy:
# 1. Push to GitHub
# 2. Go to railway.app → New Project → Deploy from GitHub
# 3. Add Redis plugin (free)
# 4. Set environment variables
# 5. Done - auto HTTPS, custom domain support

# Environment variables needed in Railway dashboard:
# TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxx
# TWILIO_AUTH_TOKEN=***
# TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886 (sandbox) or your verified number
# OPENAI_API_KEY=***
# BUSINESS_PHONE=+27XXXXXXXXX
# LEAD_EMAIL=orders@nyss-bakes.co.za
# WEBHOOK_BASE_URL=https://your-app.up.railway.app
# REDIS_URL=redis://... (auto-set by Railway Redis plugin)
# PORT=5000 (auto-set by Railway)