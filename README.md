# SarvoRail

An intelligent Indian train route finder that discovers direct and indirect routes between any two stations, with real-time seat availability.

## Features
- Finds direct + multi-hop connecting routes via A* pathfinding
- Real-time seat availability (SL, 3A, 2A, 1A, CC, EC) from IRCTC
- Smart boarding-point optimizer (book from a different station for better availability)
- Redis caching — static data cached 30 days, availability cached 5 minutes
- Global IRCTC rate limiter to avoid bans across concurrent users

## Tech Stack
- **Backend:** FastAPI + Python 3.11
- **Frontend:** React + Vite
- **Cache:** Redis
- **Scraping:** httpx (IRCTC internal APIs)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:
```
REDIS_URL=redis://localhost:6379
LOG_LEVEL=INFO
MAX_RETRIES=3
```

Run backend:
```bash
uvicorn api.main:app --reload
```

Run frontend:
```bash
cd frontend && npm install && npm run dev
```
