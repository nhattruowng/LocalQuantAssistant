# LocalQuant Assistant Frontend

React + TypeScript dashboard for the LocalQuant Assistant FastAPI backend.

## Tech Stack

| Area | Library |
| --- | --- |
| App | React, TypeScript, Vite |
| Styling | Tailwind CSS, shadcn/ui-inspired primitives |
| Data fetching | TanStack Query, Axios |
| Local settings | Zustand |
| Charts | Recharts, custom SVG candlestick chart |
| Icons | lucide-react |

## Setup

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

The dev server runs at:

```text
http://localhost:5173
```

## Environment

```env
VITE_API_BASE_URL=http://localhost:8000
```

Make sure the FastAPI backend is running:

```bash
uvicorn src.api.main:app --reload
```

## Pages

- `Dashboard`: latest setup, market snapshot, and quick actions.
- `Market`: candlestick chart, EMA overlays, volume, RSI, and market regime.
- `Signal`: BUY / SELL / WAIT setup, confidence, entry, SL, TP, reasons, and risk notes.
- `Backtest`: metrics, equity curve, and trade history.
- `Model`: metadata, metrics, and feature importance when provided by the API.
- `History`: signal history with simple filters.
- `Settings`: API base URL, default symbol/timeframe, account balance, and risk percent.

## Notes

This frontend is a decision-support interface only. It does not execute real trades and should be used for research, testing, and paper workflows.
