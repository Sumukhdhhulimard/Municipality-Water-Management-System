# Jalapura Water Management — React frontend

This frontend replaces the old `index.html`, `app.js`, and `style.css`. It uses the **existing FastAPI backend**, not a new database. Resident and operator navigation are independent React views.

## Requirements
- Node.js 20.19+ or 22.12+
- Existing FastAPI backend running on http://127.0.0.1:8000

## Start on Windows (VS Code terminal)
```powershell
cd jalapura-react
npm install
copy .env.example .env
npm run dev
```
Open the local address printed by Vite (usually http://127.0.0.1:5173).

Run FastAPI in a **separate** terminal using your existing backend instructions (typically `uvicorn main:app --reload --port 8000` from the backend folder).

## Backend CORS
Your FastAPI app must permit the React dev origin, e.g.:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
Add this **once**, after `app = FastAPI(...)`; if CORS is already configured, update that configuration instead of duplicating it.

## API routes expected
- `GET /locations`, `POST /register`, `POST /login`
- Resident: `GET /resident/dashboard`, `/resident/connections`, `/resident/bills`, `/resident/payments`, `/resident/complaints`; `POST /resident/connections`, `/resident/complaints`, `/resident/bills/{id}/pay`
- Operator: `GET /operator/dashboard`, `/operator/connections`, `/operator/bills`, `/operator/complaints`, `/operator/payments`, `/operator/zones`, `/operator/residents`; `PATCH /operator/connections/{id}`, `/operator/complaints/{id}`; `POST /operator/generate-bill`
- AI: `POST /ai/ask` with `{ "question": "..." }`

The above endpoints were copied from the supplied old `app.js`. Their live responses could not be checked because the FastAPI source/server was not supplied. Backend response schemas must match the old frontend contract.

## Verification
1. Run `npm run build` to check the React bundle.
2. Login as resident: visit each tab; try an unpaid bill and a complaint.
3. Login as operator: visit each tab; approve a pending connection, generate a bill, update a complaint.
4. Ask the AI a question and check the response.
5. Use DevTools Network tab if any endpoint fails; error messages are displayed independently per section.

**Important:** Payments are simulated; no real payment gateway is included. Tokens are held in sessionStorage, as in the original app. For production, improve token handling and authentication security.
