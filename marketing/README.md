# Inventory Clearance Agent

**Production-Grade Autonomous AI Agent for Shopify Inventory Clearance &
Customer Reactivation**

## Stack

- **Backend:** Python 3.11 + FastAPI
- **Database:** PostgreSQL 15 + Redis 7
- **Queue:** Celery (for background agents)
- **Frontend:** Next.js 14 (coming soon)
- **Hosting:** Render.com

## Quick Start

### 1. Prerequisites

- Docker & Docker Compose
- Shopify Partner Account
- Shopify Development Store

### 2. Setup

```bash
# Clone the repo
cd cephly_mul

# Copy environment file
cp backend/.env.example backend/.env

# Edit .env with your credentials:
# - SHOPIFY_API_KEY (from Shopify Partners)
# - SHOPIFY_API_SECRET
# - ANTHROPIC_API_KEY
# - Generate a SECRET_KEY

# Start services
docker-compose up -d

# View logs
docker-compose logs -f backend
```

### 3. Connect Your Store

1. Go to `http://localhost:8000/api/auth/install?shop=YOUR-STORE.myshopify.com`
2. Complete Shopify OAuth
3. System will sync your products, customers, and orders

### 4. Agents Run Autonomously

- **Observer Agent:** Runs daily at 2 AM UTC (detects dead stock)
- **Matchmaker Agent:** Runs daily at 3 AM UTC (segments customers)
- **Strategy Agent:** (Module 3) Recommends clearance strategies
- **Execution Agent:** (Module 4) Deploys campaigns

## API Endpoints

| Endpoint                               | Description          |
| -------------------------------------- | -------------------- |
| `GET /health`                          | Health check         |
| `GET /api/auth/install?shop=X`         | Initiate OAuth       |
| `GET /api/inbox?merchant_id=X`         | List agent proposals |
| `POST /api/inbox/{id}/approve`         | Approve proposal     |
| `GET /api/products?merchant_id=X`      | List products        |
| `GET /api/products/dead-stock-summary` | Dead stock stats     |

## Project Structure

```
cephly_mul/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app
│   │   ├── config.py         # Settings
│   │   ├── database.py       # SQLAlchemy async
│   │   ├── models.py         # All models
│   │   ├── worker.py         # Celery config
│   │   ├── routers/
│   │   │   ├── auth.py       # Shopify OAuth
│   │   │   ├── webhooks.py   # Real-time sync
│   │   │   ├── inbox.py      # Agent proposals
│   │   │   ├── products.py   # Product API
│   │   │   └── merchants.py  # Merchant API
│   │   └── tasks/
│   │       ├── sync.py       # Initial data import
│   │       ├── observer.py   # Dead stock detection
│   │       ├── matchmaker.py # RFM segmentation
│   │       └── execution.py  # Campaign deployment
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # (Module 4)
├── docker-compose.yml
└── README.md
```

## Module Status

| Module        | Status      | Description                       |
| ------------- | ----------- | --------------------------------- |
| 1. Foundation | ✅ Complete | OAuth, Webhooks, Database, Agents |
| 2. Detection  | ✅ Complete | Observer + Matchmaker Agents      |
| 3. Strategy   | 🚧 Pending  | Strategy selection, pricing, copy |
| 4. Execution  | 🚧 Pending  | Campaign deployment               |
| 5. Networked  | 🚧 Pending  | Dark Pool B2B liquidation         |

## License

Proprietary - All Rights Reserved
