# ⚾ Analytic Overview

A baseball betting intelligence dashboard that surfaces the hottest hitters, player matchup data, and ML-powered daily performance predictions. Built with Next.js and FastAPI.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS |
| Backend | Python, FastAPI |
| Data | MLB Stats API, pybaseball |
| Database | PostgreSQL (coming soon) |

---

## Project Structure

```
sports_analytics/
├── frontend/          # Next.js app
└── backend/           # FastAPI app
```

---

## Prerequisites

Make sure you have the following installed before getting started:

- [Node.js](https://nodejs.org/) (v18 or higher)
- [Python](https://www.python.org/) (v3.10 or higher)
- [Git](https://git-scm.com/)

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/your-username/sports_analytics.git
cd sports_analytics
```

---

### 2. Backend setup

Navigate to the backend folder and create a virtual environment:

```bash
cd backend
python -m venv venv
```

Activate the virtual environment:

```bash
# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the backend server:

```bash
uvicorn main:app --reload
```

The API will be running at `http://localhost:8000`.
Visit `http://localhost:8000/docs` to see all available endpoints.

---

### 3. Frontend setup

Open a new terminal and navigate to the frontend folder:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Create a `.env.local` file inside the `frontend/` folder:

```bash
# Windows (PowerShell)
ni .env.local

# Mac / Linux
touch .env.local
```

Add the following line to `.env.local`:

```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Start the frontend development server:

```bash
npm run dev
```

The app will be running at `http://localhost:3000`.

---

## Running the Project

You need both servers running simultaneously. Use two separate terminal windows:

| Terminal | Command | URL |
|---|---|---|
| Backend | `uvicorn main:app --reload` | http://localhost:8000 |
| Frontend | `npm run dev` | http://localhost:3000 |

> **Tip:** Both WebStorm and PyCharm have a built-in terminal panel that supports multiple tabs — use the `+` button to open a second tab so you can keep both servers running without leaving your IDE.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check |
| GET | `/api/leaders` | Returns the top HR, AVG, and OPS hitters over the current season |

Full interactive API docs are available at `http://localhost:8000/docs` when the backend is running.

---

## Environment Variables

### `frontend/.env.local`

| Variable | Description | Example |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL of the FastAPI backend | `http://127.0.0.1:8000` |

> `.env.local` is excluded from version control via `.gitignore`. Never commit this file.

---

## Common Issues

**Port 8000 already in use**

Another process may be using port 8000. Run the backend on a different port:

```bash
uvicorn main:app --reload --port 8001
```

Then update `NEXT_PUBLIC_API_URL` in `frontend/.env.local` to match:

```
NEXT_PUBLIC_API_URL=http://127.0.0.1:8001
```

**Frontend shows "Could not load data"**

- Confirm the backend is running and accessible at `http://localhost:8000/api/leaders`
- Confirm `frontend/.env.local` exists and contains `NEXT_PUBLIC_API_URL`
- Restart `npm run dev` after any changes to `.env.local` — environment variables only load on startup

**`venv\Scripts\activate` not recognized on Windows**

Make sure you are running PowerShell, not Command Prompt. Alternatively, try:

```bash
.\venv\Scripts\activate
```

**FanGraphs 403 error from pybaseball**

FanGraphs blocks automated requests. The project uses the MLB Stats API directly for season stats, which requires no authentication. If you see this error, confirm `services/stats.py` is using `requests` to call `statsapi.mlb.com` and not pybaseball's `batting_stats()` function.

---

## Roadmap

- [x] Backend `/api/leaders` endpoint
- [x] Home page with top HR, AVG, and OPS leader cards
- [ ] Real 7-day sparkline data from MLB Stats API
- [ ] Player profile page
- [ ] Today's game slate
- [ ] Matchup analysis (batter vs. pitcher, L/R splits)
- [ ] Good Day prediction score (ML model)
- [ ] Hamburger navigation menu
- [ ] Football and hockey modules

---

## Data Sources

- **[MLB Stats API](https://statsapi.mlb.com)** — season stats, rosters, schedules, standings. No API key required.
- **[pybaseball](https://github.com/jldbc/pybaseball)** — Statcast pitch-level data including exit velocity, launch angle, and spin rate.

---

## License

MIT
