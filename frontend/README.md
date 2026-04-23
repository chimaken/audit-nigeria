# AuditNigeria Dashboard (Next.js 14)

Dark, mobile-first command center for FastAPI `/results/*` data.

## Setup

```bash
cd frontend
cp .env.local.example .env.local
# set NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

### Windows: `ENOTEMPTY`, `EPERM`, or “Access denied” on `npm install`

That usually means **`node_modules` is half-installed** and something still has files open (often **`next dev`**, another terminal, or **Windows Defender** scanning `.node` binaries).

1. **Stop** any `npm run dev` / `next dev` and close extra terminals pointed at `frontend`.
2. In **Task Manager**, end stray **`Node.js`** processes if any.
3. Delete the folder from **File Explorer** or an elevated prompt:
   - PowerShell (from `frontend`):  
     `Remove-Item -Recurse -Force node_modules`  
     If it still fails, reboot once, then delete again.
4. Optionally remove a bad lockfile: `del package-lock.json` (then npm will regenerate it).
5. Run **`npm install`** again from `frontend`.

If delete always fails, add an **exclusion** for `audit-nigeria-mvp\frontend\node_modules` in Windows Security → Virus & threat protection, then repeat step 3.

### If `npm install` ends with `TAR_ENTRY_ERROR ENOENT` / `next/dist` / broken `typescript` folder

That means extraction **stopped mid-way** (disk, Defender, another Node process, or a bad partial folder). A normal `npm install` on top of that will keep failing.

**Nuclear reset (run from `frontend` in an elevated or plain `cmd.exe` if PowerShell struggles):**

```bat
taskkill /F /IM node.exe 2>nul
rmdir /s /q node_modules
del package-lock.json 2>nul
npm cache clean --force
npm install
```

Use **one** canonical project path. If npm logs show `...\ed-projects\...` but your repo lives under `...\ed-projects\...` (or the reverse), fix the typo or `cd` so installs never cross two trees.

Open [http://localhost:3000](http://localhost:3000). Ensure the API has CORS enabled (repo `main.py` allows `localhost:3000`).

## Routes

| Path | Purpose |
|------|---------|
| `/` | National leaderboard + Lagos demo map + `?view=senate` senatorial grouping |
| `/state/[stateId]` | State drill-down + LGA map (Lagos demo) |
| `/state/[stateId]/lga/[lgaId]` | Polling units + map focus |
| `/evidence/[puId]?election_id=1` | Trust anchor: totals + proof gallery + pinch zoom |

Shareable query params: `election_id`, `view=senate`.

## Stack

Next.js 14 App Router, Tailwind, TanStack Query, Framer Motion, React-Leaflet (Carto dark basemap), `react-quick-pinch-zoom` on EC8A images.

## Map note

LGA positions use demo centroids in `lib/lagos-lga-points.ts`. Swap in real Nigeria TopoJSON/GeoJSON when you have licensed boundaries.
