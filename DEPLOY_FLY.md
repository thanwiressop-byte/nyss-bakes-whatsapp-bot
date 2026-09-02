# Fly.io Deploy Commands for NYSS Bakes WhatsApp Bot

## 1. Install flyctl (Windows)
```powershell
# PowerShell (Admin)
iwr https://fly.io/install.ps1 -useb | iex
# OR: scoop install flyctl
# OR: choco install flyctl
```
Restart terminal after install.

## 2. Login & Launch
```bash
fly auth login          # Opens browser
fly launch --no-deploy  # Creates app, writes fly.toml (already done)
```

## 3. Set Secrets (never in fly.toml!)
```bash
fly secrets set \
  TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxx \
  TWILIO_AUTH_TOKEN=your_token \
  TWILIO_WHATSAPP_NUMBER="whatsapp:+14155238886" \
  OPENAI_API_KEY=sk-xxxxxxxxxxxx \
  BUSINESS_PHONE=+27XXXXXXXXX \
  LEAD_EMAIL=orders@nyss-bakes.co.za \
  WEBHOOK_BASE_URL=https://nyss-bakes-whatsapp.fly.dev
```

## 4. Provision Redis (Free on Fly)
```bash
# Creates a Redis instance, links it, sets REDIS_URL automatically
fly redis create --name nyss-bakes-redis --region jnb --plan free
# Attach to app (sets REDIS_URL secret)
fly redis attach nyss-bakes-redis --app nyss-bakes-whatsapp
```

## 5. Deploy
```bash
fly deploy
# First deploy takes 2-3 min (builds image)
# Subsequent deploys ~30s
```

## 6. Verify & Test
```bash
# Check logs
fly logs

# Test health endpoint
curl https://nyss-bakes-whatsapp.fly.dev/health

# Set Twilio webhook to:
# https://nyss-bakes-whatsapp.fly.dev/whatsapp
```

## 7. Custom Domain (optional)
```bash
fly certs create nyss-bakes.raisingalphas.co.za
# Add CNAME: nyss-bakes.raisingalphas.co.za → nyss-bakes-whatsapp.fly.dev
# Update WEBHOOK_BASE_URL secret
fly secrets set WEBHOOK_BASE_URL=https://nyss-bakes.raisingalphas.co.za
```

## Useful Commands
```bash
fly status              # App status, machines, IPs
fly ssh console         # SSH into running container
fly scale count 1       # Ensure 1 machine running (free tier)
fly scale memory 256    # Adjust if needed
fly volumes list        # If using persistent volume
fly secrets list        # Verify secrets set
fly releases            # Deploy history
fly apps destroy nyss-bakes-whatsapp  # Cleanup
```

## Free Tier Limits (Fly)
- 3 shared-cpu-1x VMs (256MB each) = free forever
- 160GB outbound bandwidth/month
- 3GB persistent volume storage
- 1GB Docker registry storage

Your bot: ~50MB image, 256MB RAM, 1 VM = **well within free tier**.

## Twilio Sandbox → Production
1. Test with sandbox number (`+1 415 523 8886`)
2. Apply for WhatsApp Business API at business.whatsapp.com
3. Once verified, update `TWILIO_WHATSAPP_NUMBER` secret to your verified number
4. No code changes needed