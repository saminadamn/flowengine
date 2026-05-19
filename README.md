
# FlowEngine 
> Distributed Job Queue & Scheduler — FastAPI · Celery · Redis · PostgreSQL

## What It Does
- Submit async jobs with 4 priority levels (critical / high / normal / low)
- Token-bucket **rate limiting** per IP (60 req/min default)
- **Surge detection** — auto-flags traffic spikes via Celery Beat
- **WebSocket live feed** — real-time job status updates
- **JWT auth** with admin role separation
- **Metrics API** — latency, throughput, Redis cache stats

## Routing Map
| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| POST | `/auth/register` | ❌ | Create account |
| POST | `/auth/login` | ❌ | Get JWT token |
| GET | `/auth/me` | ✅ | Current user |
| POST | `/jobs/submit` | ✅ | Submit a job |
| GET | `/jobs/submit` | ✅ | List your jobs |
| GET | `/jobs/{id}/status` | ✅ | Job status |
| DELETE | `/jobs/{id}` | ✅ | Cancel job |
| GET | `/metrics/throughput` | ✅ | Jobs/sec stats |
| GET | `/metrics/surge` | ✅ | Surge state |
| GET | `/metrics/latency` | ✅ | Latency by job type |
| GET | `/metrics/cache-stats` | ✅ | Redis hit/miss |
| POST | `/admin/flush` | 🔐 | Drain all queues |
| GET | `/admin/jobs` | 🔐 | All jobs (admin) |
| GET | `/admin/audit-logs` | 🔐 | Audit log |
| WS | `/ws/feed?token=` | ✅ | Live job feed |
| WS | `/ws/job/{id}?token=` | ✅ | Single job feed |

## Quick Start

### 1. Clone & configure
```bash
git clone <your-repo>
cd flowengine
cp .env.example .env   # edit SECRET_KEY at minimum
```

### 2. Run everything
```bash
docker-compose up --build
```

### 3. Services
| Service | URL |
|---------|-----|
| API + Swagger | http://localhost:8000/docs |
| Flower (Celery monitor) | http://localhost:5555 |
| Redis | localhost:6379 |
| PostgreSQL | localhost:5432 |

### 4. Test the flow
```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"samina","email":"s@test.com","password":"secret123"}'

# Login → get token
curl -X POST http://localhost:8000/auth/login \
  -d "username=samina&password=secret123"

# Submit a job
curl -X POST http://localhost:8000/jobs/submit \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-report","job_type":"report","priority":"high"}'

# Watch live via WebSocket
wscat -c "ws://localhost:8000/ws/feed?token=<token>"
```

## Tech Stack
- **FastAPI** — async REST API
- **Celery** — distributed task queue with 4 priority queues
- **Redis** — broker + result backend + rate limiter + pub/sub
- **PostgreSQL** — persistent job + user storage
- **Flower** — Celery monitoring dashboard
- **Docker Compose** — one-command local setup

## Resume Bullet
> Built a distributed job scheduler (FlowEngine) with priority queues, token-bucket rate limiting, surge detection, and WebSocket live status streaming — deployed via Docker with FastAPI, Celery, Redis, and PostgreSQL
