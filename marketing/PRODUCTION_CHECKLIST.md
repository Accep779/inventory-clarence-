# Production Deployment Checklist

> **Last Updated**: 2026-01-22\
> **Status**: In Progress

Check off items as you complete them. All items must be checked before going
live.

---

## External Services Required

### ✅ Essential (Must Have)

- [ ] **Shopify Partner Account**
  - URL: https://partners.shopify.com
  - Cost: Free
  - Actions:
    - [ ] Create production app
    - [ ] Get `SHOPIFY_API_KEY`
    - [ ] Get `SHOPIFY_API_SECRET`
    - [ ] Configure OAuth callback URL:
          `https://your-domain.com/api/auth/callback`
    - [ ] Register webhook topics (products, orders, customers, app/uninstalled)

- [ ] **LLM API Key** (at least ONE required)
  - [ ] **Anthropic Claude** (Recommended)
    - URL: https://console.anthropic.com
    - Cost: ~$3/1M input tokens, $15/1M output tokens
    - Get `ANTHROPIC_API_KEY`
  - [ ] **OpenAI GPT-4** (Fallback)
    - URL: https://platform.openai.com
    - Cost: ~$5-30/1M tokens depending on model
    - Get `OPENAI_API_KEY`
  - [ ] **Google Gemini** (Fallback)
    - URL: https://makersuite.google.com/app/apikey
    - Cost: Free tier available
    - Get `GOOGLE_API_KEY`

- [ ] **Hosting Platform**
  - Choose ONE:
    - [ ] **Render.com** (Recommended)
      - URL: https://render.com
      - Cost: ~$7/service/month
      - Deploy: backend, worker, scheduler, frontend
    - [ ] **Railway**
      - URL: https://railway.app
      - Cost: ~$5/service/month
    - [ ] **Self-hosted VPS**
      - Cost: ~$10-20/month

---

### 🔶 Recommended (Improve Reliability)

- [ ] **Managed PostgreSQL** (instead of Docker)
  - [ ] **Supabase** (Recommended)
    - URL: https://supabase.com
    - Cost: Free tier (500MB), then $25/month
    - Get `DATABASE_URL`
  - [ ] **Neon**
    - URL: https://neon.tech
    - Cost: Free tier available
  - [ ] **AWS RDS**
    - Cost: ~$15/month minimum

- [ ] **Managed Redis** (instead of Docker)
  - [ ] **Upstash**
    - URL: https://upstash.com
    - Cost: Free tier (10K requests/day)
    - Get `REDIS_URL`
  - [ ] **Redis Cloud**
    - URL: https://redis.com/try-free/
    - Cost: Free tier (30MB)

- [ ] **Sentry** (Error Monitoring)
  - URL: https://sentry.io
  - Cost: Free tier (5K events/month)
  - Get `SENTRY_DSN`

---

### 🔷 Optional (Enhanced Features)

- [ ] **Klaviyo** (Email Campaigns)
  - URL: https://www.klaviyo.com
  - Cost: Free up to 250 contacts
  - Get `KLAVIYO_API_KEY`
  - Note: Email execution will be disabled without this

- [ ] **Twilio** (SMS Campaigns)
  - URL: https://www.twilio.com
  - Cost: ~$1/month + $0.0075/SMS
  - Get:
    - `TWILIO_ACCOUNT_SID`
    - `TWILIO_AUTH_TOKEN`
    - `TWILIO_PHONE_NUMBER`
  - Note: SMS execution will be disabled without this

---

## Environment Variables Checklist

Once you have the external services, update your `.env` file:

```bash
# === REQUIRED ===
DEBUG=false
SECRET_KEY=<generate-32-byte-random-string>
HOST=https://your-production-domain.com
FRONTEND_URL=https://your-frontend-domain.com
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
REDIS_URL=redis://user:pass@host:6379

# Shopify
SHOPIFY_API_KEY=<from-shopify-partners>
SHOPIFY_API_SECRET=<from-shopify-partners>

# Token Security
TOKEN_ENCRYPTION_KEY=<generate-fernet-key>
USE_TOKEN_VAULT=true

# LLM (at least one)
ANTHROPIC_API_KEY=<from-anthropic>

# === RECOMMENDED ===
SENTRY_DSN=<from-sentry>
OPENAI_API_KEY=<from-openai>
GOOGLE_API_KEY=<from-google>

# === OPTIONAL ===
KLAVIYO_API_KEY=<from-klaviyo>
TWILIO_ACCOUNT_SID=<from-twilio>
TWILIO_AUTH_TOKEN=<from-twilio>
TWILIO_PHONE_NUMBER=<from-twilio>
```

---

## Key Generation Commands

Run these to generate required secrets:

```bash
# Generate SECRET_KEY (32 random bytes)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate TOKEN_ENCRYPTION_KEY (Fernet key)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Final Deployment Steps

After all external services are configured:

- [ ] Update `.env` with all production values
- [ ] Run database migrations: `alembic upgrade head`
- [ ] Test OAuth flow with Shopify dev store
- [ ] Test email via Klaviyo (if configured)
- [ ] Test SMS via Twilio (if configured)
- [ ] Verify LLM responses working
- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Deploy using `docker-compose -f docker-compose.prod.yml up -d`
- [ ] Verify `/health` endpoint responds
- [ ] Submit Shopify app for review (if public app)

---

## Cost Estimate (Monthly)

| Tier              | Services                      | Estimated Cost |
| ----------------- | ----------------------------- | -------------- |
| **Minimum**       | Hosting + LLM                 | ~$30-50/month  |
| **Recommended**   | + Managed DB + Redis + Sentry | ~$50-75/month  |
| **Full Featured** | + Klaviyo + Twilio            | ~$60-100/month |

_LLM costs vary significantly based on usage. Monitor first week closely._
