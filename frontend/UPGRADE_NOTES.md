# Combined React frontend update (Steps 14–16)

Updated resident profile presentation, approved-connection selection for bill generation, searchable operator resident list, connection ID display, loading indicator, and improved styles. Existing API routes, login, complaint updates, simulated payments, and AI assistant are preserved.

## Run on Windows
1. Keep your existing FastAPI backend running on `http://127.0.0.1:8000`.
2. Extract this ZIP to a separate directory. Do not copy `node_modules` from an older installation.
3. In the extracted `frontend` folder run `npm install`, then `npm run dev`.
4. Visit `http://127.0.0.1:5173`.
5. Sign in as operator, open Generate Bills, select an approved connection and generate a bill. Sign in as the matching resident and refresh Water Bills.

## Notes
- Connection selection depends on `GET /operator/connections` returning `connection_id`, `status`, and ideally `full_name`.
- Resident Connection IDs are obtained from `/resident/connections`; operator Residents tab also uses `/operator/connections` as a fallback when resident records do not include `connection_id`.
- No SQL records or MongoDB collections are modified by this frontend update.
- The project was inspected and updated, but a Linux production build could not be run in this environment because the uploaded dependencies contain Windows-native Rollup binaries and installing Linux packages was unavailable. Run `npm install && npm run build` on your Windows machine to verify.
