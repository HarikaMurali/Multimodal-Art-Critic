# Multimodal Art Critic Chatbot - Execution Guide

## What Has Been Executed Already

1. Extracted a backend API from the UI logic into `api_server.py`.
2. Added a full workflow endpoint that supports:
	 - image or text input
	 - persona-based critique tone
	 - prompt control sliders
	 - generated image output URL
	 - session turn persistence in `data/sessions/`
3. Added static serving for generated images from `data/outputs/`.

## Step 1 - Run The API Now

Use your project virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
python -m uvicorn api_server:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```powershell
curl http://127.0.0.1:8000/api/v1/health
```

## Step 2 - Test Full Analysis Endpoint

With PowerShell:

```powershell
curl -Method Post "http://127.0.0.1:8000/api/v1/workflows/full-analysis" `
	-Form @{ \
		image=Get-Item "sample.jpg"; \
		description="What if chess pawns were alive and talking?"; \
		persona="curator"; \
		stylization="0.8"; \
		drama="0.7"; \
		texture="0.6"; \
		warmth="0.5" \
	}
```

## Step 3 - Session History

From the previous response, copy `session_id`, then:

```powershell
curl http://127.0.0.1:8000/api/v1/sessions/<session_id>
```

## Step 4 - Build React Frontend (Next)

Create frontend app:

```powershell
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install axios tailwindcss @tailwindcss/vite
```

Run frontend:

```powershell
npm run dev
```

Frontend is now scaffolded in `frontend/` and wired to the API workflow endpoint.

Run it:

```powershell
cd frontend
copy .env.example .env.local
npm run dev
```

From the project root (`C:\Chatbot`), you can now also run:

```powershell
npm run dev
```

## Step 5 - API Contract To Use In React

`POST /api/v1/workflows/full-analysis`

Form fields:
- `image` (optional file)
- `description` (optional string)
- `persona` (string)
- `stylization`, `drama`, `texture`, `warmth` (0.0 to 1.0)
- `session_id` (optional string)

Response keys:
- `session_id`
- `caption`
- `analysis.style`
- `analysis.emotion`
- `analysis.composition`
- `critique`
- `generation.positive_prompt`
- `generation.negative_prompt`
- `generation.edit_suggestion`
- `generation.generated_image_url`

## Step 6 - Advanced Features Queue

1. Persona critics UI with presets and custom persona text.
2. Prompt sliders and live prompt preview.
3. Multi-image comparison endpoint and board view.
4. Session timeline with progress deltas.
5. Export report as PDF.

## Implemented Now

The following are now implemented:

1. Login/Register authentication (JWT-like bearer token):
	- `POST /api/v1/auth/register`
	- `POST /api/v1/auth/login`
	- `GET /api/v1/auth/me`
2. Protected workflows and session endpoints (auth required).
3. Multi-image comparison workflow:
	- `POST /api/v1/workflows/compare-analysis` (2 to 4 images)
4. Session report export:
	- `GET /api/v1/sessions/{session_id}/export` (markdown download)
5. Frontend login page, compare mode toggle, export report button, and improved responsive breakpoints.

## Quick Test Flow

1. Start backend:

```powershell
python -m uvicorn api_server:app --reload --host 127.0.0.1 --port 8000
```

2. Start frontend from root:

```powershell
npm run dev
```

3. In UI:
	- Register user
	- Login
	- Run single analysis
	- Switch to compare mode and upload 2 images
	- Export report from active session

## Notes

- Existing Gradio app remains available in `app.py`.
- New API path for migration starts in `api_server.py`.
