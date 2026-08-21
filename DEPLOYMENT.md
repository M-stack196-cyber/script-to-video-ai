# Deployment

This project deliberately separates the verified local demo from the production AI workflow. Local JSON and media files are development conveniences; they must not be treated as durable storage on a production host.

## Frontend on Vercel

Use these exact project settings:

- Repository: `M-stack196-cyber/script-to-video-ai`
- Root Directory: `frontend`
- Framework Preset: Vite
- Build Command: `npm run build`
- Output Directory: `dist`
- Production environment variable: `VITE_API_BASE_URL=https://<backend-domain>`

`VITE_API_BASE_URL` is a public browser value. Never place credentials, tokens, or other secrets in any `VITE_` variable. The checked-in `frontend/vercel.json` only provides the Vite SPA history fallback.

## Backend requirements

A production backend requires:

- Python 3.12+ and packages from `backend/requirements.txt`
- AWS Bedrock access for the configured text, video, and audio models
- an S3 bucket plus least-privilege read/write permissions
- durable job persistence outside the instance filesystem
- durable media storage and URLs outside the instance filesystem
- FFmpeg in the runtime when server-side composition is enabled
- standard AWS credentials/IAM authentication for Nova Sonic
- explicit environment configuration, including `APP_ENV=production`, `PUBLIC_BASE_URL`, `CORS_ORIGINS`, and provider/model settings

The backend exposes `GET /api/deployment/readiness` for safe, non-networked configuration checks. It returns booleans and blocker messages only; it does not return secrets or verify AWS permissions by making cloud calls.

## Current production blockers

The repository does not yet claim that these are complete:

- a real S3 bucket and its permissions
- a production durable job-store implementation (`JOB_STORE_PROVIDER=local` remains development-only)
- durable production media storage and delivery
- real Nova Sonic bidirectional streaming
- a selected production runtime with FFmpeg available

The API remains available when production storage is incomplete so health, configuration, and readiness endpoints can explain the deployment state.

## Local verified path

The local mock path is separate: the FastAPI `/demo` page uses the mock scene planner, FFmpeg-generated visuals, and local `espeak-ng` narration. It writes jobs and media beneath `backend/output`. Run it only for local development with `APP_ENV=development`, `JOB_STORE_PROVIDER=local`, and `USE_MOCK_SCENE_PLANNER=true`.
