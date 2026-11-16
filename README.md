# portfolio-rag-api

The FastAPI backend for the "Ask About Me" RAG assistant on https://abhay-bhardwaj.netlify.app. It runs on Vercel.

**Stack:**
- FastAPI on Vercel Python functions
- G4F as the LLM
- Qdrant Cloud as the vector store, with Cloud Inference for embeddings
- DynamoDB for metadata (documents, jobs, conversations, admin)

## Status

| Step | Scope | State |
|---|---|---|
| 1a | Skeleton, config, CORS, `GET /api/v1/health` with live checks | ✅ |
| 1b | Ingestion: DynamoDB tables, chunking, Qdrant upserts, GitHub (multi-owner) | next |
| 1c | `POST /api/v1/chat` with citations | |
| 1d | Admin login (JWT) and admin endpoints | |
| 1e | Deploy and test against the live URL | |

## Layout

```
api/index.py            Vercel entrypoint (vercel.json rewrites every path here)
app/main.py             App factory: CORS, routers, safe 500 handler
app/config.py           Settings from env vars / .env
app/schemas.py          Response models (match the frontend's zod schemas)
app/routers/health.py   GET /api/v1/health[?deep=true]
app/services/clients.py Cached Qdrant and DynamoDB clients
app/services/health.py  Live dependency checks
app/services/llm.py     G4F wrapper (thread + timeout, no fallback)
tests/                  pytest suite (no network needed)
```

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # fill in real values; .env is git-ignored
pytest                             # runs offline
uvicorn app.main:app --reload      # http://127.0.0.1:8000/docs
```

## Health endpoint

`GET /api/v1/health` checks Qdrant and DynamoDB with real calls:

```json
{
  "status": "degraded",
  "version": "0.1.0",
  "environment": "production",
  "components": {
    "qdrant":   { "status": "degraded", "detail": "Cluster reachable; collection 'portfolio_kb' not created yet ...", "latency_ms": 180 },
    "dynamodb": { "status": "degraded", "detail": "Credentials work in us-east-1; table 'portfolio-rag-documents' not created yet.", "latency_ms": 95 }
  }
}
```

The response above is the expected result until 1b runs. A `degraded` status with those messages means the credentials, IAM policy and region are all correct.

`?deep=true` also makes one live G4F call and adds an `llm` component. It's slow, and in 1d it will be limited to admins.

The frontend maps each status like this:
- `ok` → online
- `degraded` → degraded
- `down` or `not_configured` → offline

## Deploy to Vercel

1. Vercel → Add New → Project → import `portfolio-rag-api`. Set **Framework Preset: Other** and leave the build settings empty.
2. In Settings → Functions, set the region to **Washington, D.C. (iad1)**, close to us-east-1 and Qdrant US East.
3. In Settings → Environment Variables (Production and Preview), add:
   - `APP_ENV=production`
   - `ALLOWED_ORIGINS=https://abhay-bhardwaj.netlify.app`
   - `QDRANT_URL`, `QDRANT_API_KEY`
   - `DDB_ACCESS_KEY_ID`, `DDB_SECRET_ACCESS_KEY`, `DDB_REGION=us-east-1`
4. Redeploy after you change any env vars.
5. Verify:
   ```bash
   curl https://<project>.vercel.app/api/v1/health
   curl "https://<project>.vercel.app/api/v1/health?deep=true"
   ```

Vercel reserves `AWS_*` variable names, which is why the DynamoDB keys use the `DDB_` prefix.

## GitHub sources

Your repos live under two owners (orgs), and a fine-grained PAT can target only one owner. So create one token per owner and give them all to the app in `GITHUB_TOKENS` as one-line JSON:

```
GITHUB_TOKENS={"<ai-ml-org>":"github_pat_...","<other-org>":"github_pat_..."}
```

Ingestion (1b) picks the token by the repo's owner.
