# Multimodal Art Critic Chatbot

A multimodal art critic that analyzes images and text, generates critiques in different persona voices, and produces a generated image for each analysis. The project provides a FastAPI backend that wraps model calls (image captioning, classification, LLM critique, and text-to-image generation) and a React + Vite frontend for interactive use.

## Key Features
- Single-analysis workflow: accept image or text, produce caption, critique, and a generated image
- Persona-driven critiques (curator, critic, playful, academic, etc.)
- Prompt-control sliders (stylization, drama, texture, warmth)
- Multi-image compare workflow (2–4 images)
- Session persistence and export (markdown report)
- Authentication (register/login) with per-session ownership

## Quickstart (Development)
Prerequisites:
- Python 3.10+ and virtual environment
- Node.js 18+ and npm
- A Hugging Face API token stored in an environment variable `HF_TOKEN`

1. Create and activate a virtual environment

```powershell
python -m venv .\venv
.\venv\Scripts\Activate.ps1
```

2. Install Python dependencies

```powershell
pip install -r requirements.txt
```

3. Set environment variables (example for Windows PowerShell)

```powershell
$env:HF_TOKEN = "<your-hf-token>"
copy .env.example .env
```

4. Start the backend API

```powershell
python -m uvicorn api_server:app --reload --host 127.0.0.1 --port 8000
```

5. Install and run the frontend (from project root)

```powershell
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

Open the frontend URL printed by Vite (usually http://localhost:5173).

## API Overview
Base: `http://127.0.0.1:8000/api/v1`

- GET `/health` — service health
- POST `/auth/register` — register a user
- POST `/auth/login` — login -> returns bearer token
- GET `/auth/me` — get current user
- POST `/workflows/full-analysis` — single analysis (image or text)
  - form fields: `image` (file, optional), `description` (string), `persona` (string), `stylization`, `drama`, `texture`, `warmth` (floats 0.0–1.0), `session_id` (optional)
  - response: `session_id`, `caption`, `analysis` object, `critique`, `generation` object (includes `generated_image_url`)
- POST `/workflows/compare-analysis` — compare multiple images (2–4)
- GET `/sessions/{session_id}` — retrieve session
- GET `/sessions/{session_id}/export` — download markdown export

Authentication: send `Authorization: Bearer <token>` for protected routes.

## Configuration
Edit `config/settings.py` to change model IDs and model-related settings. Important environment variables:
- `HF_TOKEN` — Hugging Face API token used by `src/api_clients/hf_client.py`

Outputs and data directories:
- `data/uploads/` — uploaded files
- `data/outputs/` — generated images and artifacts (served statically)
- `data/sessions/` — session JSONL persistence

## Project Structure (selected)
- `api_server.py` — FastAPI application and endpoints
- `app.py` — legacy Gradio demo (kept for reference)
- `src/api_clients/hf_client.py` — Hugging Face wrappers (captioning, classification, text-to-image)
- `src/analysis/` — analysis modules (style, emotion, composition, critique)
- `src/generation/prompt_builder.py` — builds prompts for generation
- `frontend/` — React + Vite frontend

## Testing
- `test_caption.py` — quick script used to validate image captioning fallback
- `test_env.py` — prints/checks required environment variables

Run tests (simple examples):

```powershell
python test_caption.py
python test_env.py
```

## Development Notes & Recommendations
- Use the project virtual environment to avoid ModuleNotFoundError.
- Hugging Face inference endpoints can change; a fallback strategy (classification labels) is implemented in `hf_client.py`.
- For production: replace custom token generation with a standard JWT provider, enable HTTPS, add rate limiting, and secure the static file serving.

## Contributing
If you want to contribute:

1. Fork the repository and create a new branch
2. Implement changes and add tests where applicable
3. Open a pull request describing the change

## License
This repository does not currently include an explicit license file. Add a license (e.g., MIT) if you intend to open-source the project.

## Acknowledgements
- Uses Hugging Face inference APIs and community models for captioning and generation.

If you'd like, I can also:
- add a short `Getting Started` GIF and sample screenshots in `assets/`
- add a LICENSE file and CI workflows for linting and tests

