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

Storage providers are configured independently:

- `JOB_STORE_PROVIDER=local` persists job JSON beneath `output/jobs`.
- `MEDIA_STORAGE_PROVIDER=local` stores generated and downloaded media beneath `output`.

The local implementations are intended for development and testing only. Their interfaces allow future durable providers, but no S3, DynamoDB, or other remote job/media storage provider is implemented yet. Unsupported provider values fail explicitly and never fall back to local storage.

The backend exposes `GET /api/deployment/readiness` for safe, non-networked configuration checks. It returns booleans and blocker messages only; it does not return secrets or verify AWS permissions by making cloud calls.

## Docker backend

Build the backend image from the repository root:

```bash
docker build -t script-to-video-ai-backend ./backend
```

Run the safe local fallback on host port 8001:

```bash
docker run --rm \
  --name script-to-video-backend \
  -p 8001:8000 \
  -e APP_ENV=development \
  -e USE_MOCK_SCENE_PLANNER=true \
  -e NARRATION_PROVIDER=local \
  -e CORS_ORIGINS=http://localhost:5173 \
  script-to-video-ai-backend
```

The container listens on port `8000`; `GET /health` is its Docker health check. FFmpeg, `espeak-ng`, and the DejaVu fonts used by the local renderer are included. The application runs as the non-root `app` user, and `/app/output` is writable so generated files remain available through `/output/...`.

For production, inject configuration and secrets at runtime through the hosting platform's secret/environment manager. For example, with non-secret placeholders supplied by the deployment environment:

```bash
docker run --rm -p 8000:8000 \
  -e APP_ENV=production \
  -e PUBLIC_BASE_URL=https://<backend-domain> \
  -e JOB_STORE_PROVIDER=local \
  -e MEDIA_STORAGE_PROVIDER=local \
  -e CORS_ORIGINS=https://<frontend-domain> \
  -e AWS_REGION=<aws-region> \
  -e BEDROCK_TEXT_MODEL_ID=<text-model-id> \
  -e BEDROCK_VIDEO_MODEL_ID=<video-model-id> \
  -e BEDROCK_AUDIO_MODEL_ID=<audio-model-id> \
  -e S3_BUCKET_NAME=<bucket-name> \
  -e NARRATION_PROVIDER=<provider> \
  script-to-video-ai-backend
```

AWS credentials or Bedrock bearer tokens must also be injected by the hosting platform; never bake them into the image or pass real values in checked-in commands. Prefer an attached IAM role where the runtime supports one.

Container-local `/app/output` is ephemeral unless a volume or external storage is configured. The root `docker-compose.yml` mounts a named volume for local QA, but this is not the production durable job/media store. Docker supplies the FFmpeg runtime only; it does not configure AWS permissions, S3, Nova services, or durable production storage. `espeak-ng` is exclusively the local-demo narration fallback.

Supported runtime configuration includes `APP_ENV`, `PUBLIC_BASE_URL`, `JOB_STORE_PROVIDER`, `MEDIA_STORAGE_PROVIDER`, `CORS_ORIGINS`, `AWS_REGION`, `AWS_BEARER_TOKEN_BEDROCK`, `BEDROCK_TEXT_MODEL_ID`, `BEDROCK_VIDEO_MODEL_ID`, `BEDROCK_AUDIO_MODEL_ID`, `USE_MOCK_SCENE_PLANNER`, `S3_BUCKET_NAME`, and `NARRATION_PROVIDER`.

## Current production blockers

The repository does not yet claim that these are complete:

- a real S3 bucket and its permissions
- a production durable job-store implementation (`JOB_STORE_PROVIDER=local` remains development-only)
- durable production media storage and delivery
- real Nova Sonic bidirectional streaming
- a selected production runtime with FFmpeg available

The API remains available when production storage is incomplete so health, configuration, and readiness endpoints can explain the deployment state.

## Local verified path

The local mock path is separate: the FastAPI `/demo` page uses the mock scene planner, FFmpeg-generated visuals, and local `espeak-ng` narration. It writes jobs and media beneath `backend/output`. Run it only for local development with `APP_ENV=development`, `JOB_STORE_PROVIDER=local`, `MEDIA_STORAGE_PROVIDER=local`, and `USE_MOCK_SCENE_PLANNER=true`.
