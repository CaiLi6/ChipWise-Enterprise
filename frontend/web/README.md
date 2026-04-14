# ChipWise Enterprise — Vue3 Frontend

## Quick Start

```bash
npm install
npm run dev        # Dev server at http://localhost:5173
npm run build      # Production build → dist/
npm run preview    # Preview production build at http://localhost:4173
```

## Dev Mode

In development (`npm run dev`), the app runs with mock data when the backend is unavailable:
- **Login**: Any credentials work, stores a mock token
- **Query**: Returns simulated streaming responses
- **Compare**: Returns mock chip comparison data

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://localhost:8080` | Backend API base URL |

Files: `.env.development` (local), `.env.production` (deploy).

## Tech Stack

- Vue 3 + TypeScript + Composition API
- Element Plus — UI component library
- Pinia — State management
- Vue Router 4 — Client-side routing
- Axios — HTTP client with JWT interceptor

## Pages

| Route | View | Description |
|-------|------|-------------|
| `/login` | LoginView | Username/password + SSO login |
| `/query` | QueryView | Chat-style query with SSE streaming |
| `/compare` | CompareView | Multi-chip parameter comparison table |
| `/documents` | DocumentsView | Document upload and task status |

## Deployment

```bash
npm run build
# Serve dist/ with nginx, set VITE_API_BASE_URL to FastAPI gateway URL
```
