import os
import hmac
import json
import base64
import hashlib
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.api_clients.hf_client import (
    generate_chat_response,
    generate_image_caption,
    generate_image_from_prompt,
)
from src.analysis.critique_engine import build_critique
from src.generation.prompt_builder import build_sd_prompt

UPLOAD_DIR = Path("data/uploads")
OUTPUT_DIR = Path("data/outputs")
SESSION_DIR = Path("data/sessions")
DB_PATH = Path("data/app.db")
SECRET_KEY = os.getenv("APP_SECRET_KEY", "change-me-in-production")
TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "24"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Multimodal Art Critic API", version="1.0.0")
auth_scheme = HTTPBearer(auto_error=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


class AuthRequest(BaseModel):
    email: str
    password: str


class SummarizeRequest(BaseModel):
    text: str
    style: str = "concise"


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse(
        {
            "message": "Multimodal Art Critic API is running",
            "docs": "/docs",
            "health": "/api/v1/health",
            "workflow": "/api/v1/workflows/full-analysis",
            "compare": "/api/v1/workflows/compare-analysis",
            "auth": [
                "/api/v1/auth/register",
                "/api/v1/auth/login",
                "/api/v1/auth/me",
            ],
            "chat": [
                "/api/v1/chat/summarize",
            ],
        }
    )


@app.get("/favicon.ico")
def favicon() -> JSONResponse:
    return JSONResponse({}, status_code=204)


def _apply_controls_to_prompt(prompt: str, stylization: float, drama: float, texture: float, warmth: float) -> str:
    style_tokens = []

    if stylization >= 0.75:
        style_tokens.append("highly stylized")
    elif stylization <= 0.25:
        style_tokens.append("subtle stylization")

    if drama >= 0.75:
        style_tokens.append("cinematic dramatic lighting")
    elif drama <= 0.25:
        style_tokens.append("soft understated lighting")

    if texture >= 0.75:
        style_tokens.append("rich painterly textures")
    elif texture <= 0.25:
        style_tokens.append("clean smooth surfaces")

    if warmth >= 0.75:
        style_tokens.append("warm color temperature")
    elif warmth <= 0.25:
        style_tokens.append("cool color temperature")

    if not style_tokens:
        return prompt

    return f"{prompt}, {', '.join(style_tokens)}"


def _build_persona_prompt(persona: str, caption: str, description: str, critique_data: dict) -> str:
    return f"""
You are an art critic assistant with the persona: {persona}.

Image caption: {caption}
User description: {description}

Detected style: {critique_data['style']}
Detected emotion: {critique_data['emotion']}
Composition analysis: {critique_data['composition']}

Write a short art critique in a clear and friendly tone.
Mention:
1. style
2. composition
3. emotion
4. one suggestion for improvement
""".strip()


def _save_session_record(session_id: str, record: dict) -> None:
    session_file = SESSION_DIR / f"{session_id}.jsonl"
    with open(session_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _load_session_rows(session_id: str) -> list[dict]:
    session_file = SESSION_DIR / f"{session_id}.jsonl"
    if not session_file.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    rows = []
    with open(session_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _db() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def _init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000)
    return digest.hex()


def _create_user(email: str, password: str) -> dict:
    salt = os.urandom(16).hex()
    password_hash = _hash_password(password, salt)
    created_at = datetime.now(timezone.utc).isoformat()
    try:
        with _db() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (email.lower().strip(), password_hash, salt, created_at),
            )
            conn.commit()
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already registered")

    return {"id": user_id, "email": email.lower().strip()}


def _find_user_by_email(email: str) -> dict | None:
    with _db() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash, salt, created_at FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "email": row[1],
        "password_hash": row[2],
        "salt": row[3],
        "created_at": row[4],
    }


def _find_user_by_id(user_id: int) -> dict | None:
    with _db() as conn:
        row = conn.execute("SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()

    if not row:
        return None

    return {"id": row[0], "email": row[1], "created_at": row[2]}


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("utf-8"))


def _create_token(user_id: int, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_encoded = _b64url_encode(payload_bytes)
    signature = hmac.new(SECRET_KEY.encode("utf-8"), payload_encoded.encode("utf-8"), hashlib.sha256).digest()
    return f"{payload_encoded}.{_b64url_encode(signature)}"


def _decode_token(token: str) -> dict:
    try:
        payload_encoded, sig_encoded = token.split(".")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token format")

    expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), payload_encoded.encode("utf-8"), hashlib.sha256).digest()
    actual_sig = _b64url_decode(sig_encoded)
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    payload = json.loads(_b64url_decode(payload_encoded).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=401, detail="Token expired")

    return payload


def _get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    payload = _decode_token(credentials.credentials)
    user = _find_user_by_id(int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _assert_session_owner(session_id: str, user_id: int) -> None:
    rows = _load_session_rows(session_id)
    if rows and int(rows[0].get("user_id", -1)) != int(user_id):
        raise HTTPException(status_code=403, detail="You do not have access to this session")


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "multimodal-art-critic-api"}


@app.post("/api/v1/auth/register")
def register(payload: AuthRequest) -> dict:
    if "@" not in payload.email or len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Use a valid email and a password with at least 8 characters")

    user = _create_user(payload.email, payload.password)
    token = _create_token(user["id"], user["email"])
    return {"token": token, "user": user}


@app.post("/api/v1/auth/login")
def login(payload: AuthRequest) -> dict:
    user = _find_user_by_email(payload.email)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    incoming_hash = _hash_password(payload.password, user["salt"])
    if not hmac.compare_digest(incoming_hash, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = _create_token(user["id"], user["email"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"]}}


@app.get("/api/v1/auth/me")
def me(current_user: dict = Depends(_get_current_user)) -> dict:
    return {"user": current_user}


@app.post("/api/v1/chat/summarize")
def summarize_text(payload: SummarizeRequest, current_user: dict = Depends(_get_current_user)) -> dict:
    text = payload.text.strip()
    if len(text) < 30:
        raise HTTPException(status_code=400, detail="Please provide at least 30 characters to summarize")

    style = payload.style.strip().lower() or "concise"
    style_instruction = {
        "concise": "Create a concise summary in 3 to 5 bullet points.",
        "detailed": "Create a detailed summary with a short overview and then bullet points.",
        "chat": "Summarize in a conversational chatbot style with brief paragraphs.",
    }.get(style, "Create a concise summary in 3 to 5 bullet points.")

    prompt = (
        "You are a helpful summarization assistant. "
        f"{style_instruction}\n\n"
        "Text to summarize:\n"
        f"{text}"
    )

    try:
        summary = generate_chat_response(prompt)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Summarization failed: {str(e)}")

    return {
        "summary": summary,
        "style": style,
        "char_count": len(text),
        "user": current_user["email"],
    }


@app.post("/api/v1/workflows/full-analysis")
async def full_analysis(
    description: str = Form(default=""),
    persona: str = Form(default="friendly mentor"),
    stylization: float = Form(default=0.5),
    drama: float = Form(default=0.5),
    texture: float = Form(default=0.5),
    warmth: float = Form(default=0.5),
    session_id: str = Form(default=""),
    image: UploadFile | None = File(default=None),
    current_user: dict = Depends(_get_current_user),
) -> dict:
    caption = ""
    upload_path: Path | None = None

    if image is not None:
        ext = Path(image.filename or "upload.png").suffix or ".png"
        upload_name = f"upload_{uuid.uuid4().hex}{ext}"
        upload_path = UPLOAD_DIR / upload_name
        data = await image.read()
        upload_path.write_bytes(data)

        try:
            caption = generate_image_caption(str(upload_path))
        except Exception:
            caption = ""

    if not caption and description.strip():
        caption = description.strip()

    if not caption:
        raise HTTPException(status_code=400, detail="Provide image or description for analysis")

    critique_data = build_critique(caption, description)
    prompt_data = build_sd_prompt(
        critique_data["style"],
        critique_data["emotion"],
        critique_data["composition"],
        description,
    )

    positive_prompt = _apply_controls_to_prompt(
        prompt_data["positive_prompt"],
        stylization=stylization,
        drama=drama,
        texture=texture,
        warmth=warmth,
    )

    try:
        refined_critique = generate_chat_response(
            _build_persona_prompt(persona, caption, description, critique_data)
        )
    except Exception:
        refined_critique = critique_data["critique"]

    generated_image_url = None
    try:
        generated_image = generate_image_from_prompt(positive_prompt, prompt_data["negative_prompt"])
        out_name = f"gen_{uuid.uuid4().hex}.png"
        out_path = OUTPUT_DIR / out_name
        generated_image.save(out_path)
        generated_image_url = f"/outputs/{out_name}"
    except Exception:
        generated_image_url = None

    sid = session_id.strip() or uuid.uuid4().hex
    if session_id.strip():
        _assert_session_owner(sid, current_user["id"])

    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "workflow": "single",
        "user_id": current_user["id"],
        "user_email": current_user["email"],
        "description": description,
        "persona": persona,
        "caption": caption,
        "style": critique_data["style"],
        "emotion": critique_data["emotion"],
        "composition": critique_data["composition"],
        "positive_prompt": positive_prompt,
        "negative_prompt": prompt_data["negative_prompt"],
        "generated_image_url": generated_image_url,
        "upload_file": str(upload_path) if upload_path else "",
        "controls": {
            "stylization": stylization,
            "drama": drama,
            "texture": texture,
            "warmth": warmth,
        },
    }
    _save_session_record(sid, record)

    return {
        "session_id": sid,
        "caption": caption,
        "analysis": {
            "style": critique_data["style"],
            "emotion": critique_data["emotion"],
            "composition": critique_data["composition"],
        },
        "critique": refined_critique,
        "generation": {
            "positive_prompt": positive_prompt,
            "negative_prompt": prompt_data["negative_prompt"],
            "edit_suggestion": prompt_data["edit_suggestion"],
            "generated_image_url": generated_image_url,
        },
    }


@app.post("/api/v1/workflows/compare-analysis")
async def compare_analysis(
    description: str = Form(default=""),
    persona: str = Form(default="friendly mentor"),
    stylization: float = Form(default=0.5),
    drama: float = Form(default=0.5),
    texture: float = Form(default=0.5),
    warmth: float = Form(default=0.5),
    session_id: str = Form(default=""),
    images: list[UploadFile] = File(default=[]),
    current_user: dict = Depends(_get_current_user),
) -> dict:
    if len(images) < 2:
        raise HTTPException(status_code=400, detail="Upload at least 2 images for comparison")
    if len(images) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 images are allowed per comparison")

    items = []
    for idx, image in enumerate(images):
        ext = Path(image.filename or "upload.png").suffix or ".png"
        upload_name = f"compare_{uuid.uuid4().hex}{ext}"
        upload_path = UPLOAD_DIR / upload_name
        upload_path.write_bytes(await image.read())

        try:
            caption = generate_image_caption(str(upload_path))
        except Exception:
            caption = f"Artwork {idx + 1}"

        critique_data = build_critique(caption, description)
        score = 6
        if critique_data["style"] != "expressive contemporary art":
            score += 1
        if critique_data["emotion"] != "awe":
            score += 1
        if "balanced" in critique_data["composition"].lower():
            score += 1

        item = {
            "index": idx,
            "filename": image.filename or upload_name,
            "caption": caption,
            "style": critique_data["style"],
            "emotion": critique_data["emotion"],
            "composition": critique_data["composition"],
            "score": score,
        }
        items.append(item)

    best_item = max(items, key=lambda x: x["score"])
    summary_prompt = (
        f"You are an art critic with persona {persona}. Compare these artworks and suggest the strongest piece. "
        f"Items: {json.dumps(items)}. Mention strengths, consistency, and one improvement direction."
    )
    try:
        summary = generate_chat_response(summary_prompt)
    except Exception:
        summary = (
            f"Best candidate is image {best_item['index'] + 1} ({best_item['filename']}). "
            "Use its composition as baseline and strengthen emotional clarity in the other versions."
        )

    prompt_data = build_sd_prompt(
        best_item["style"],
        best_item["emotion"],
        best_item["composition"],
        description,
    )
    positive_prompt = _apply_controls_to_prompt(
        prompt_data["positive_prompt"],
        stylization=stylization,
        drama=drama,
        texture=texture,
        warmth=warmth,
    )

    generated_image_url = None
    try:
        generated_image = generate_image_from_prompt(positive_prompt, prompt_data["negative_prompt"])
        out_name = f"compare_gen_{uuid.uuid4().hex}.png"
        out_path = OUTPUT_DIR / out_name
        generated_image.save(out_path)
        generated_image_url = f"/outputs/{out_name}"
    except Exception:
        generated_image_url = None

    sid = session_id.strip() or uuid.uuid4().hex
    if session_id.strip():
        _assert_session_owner(sid, current_user["id"])

    _save_session_record(
        sid,
        {
            "timestamp": datetime.utcnow().isoformat(),
            "workflow": "compare",
            "user_id": current_user["id"],
            "user_email": current_user["email"],
            "persona": persona,
            "description": description,
            "items": items,
            "best_index": best_item["index"],
            "summary": summary,
            "caption": best_item["caption"],
            "style": best_item["style"],
            "emotion": best_item["emotion"],
            "composition": best_item["composition"],
            "positive_prompt": positive_prompt,
            "negative_prompt": prompt_data["negative_prompt"],
            "generated_image_url": generated_image_url,
            "controls": {
                "stylization": stylization,
                "drama": drama,
                "texture": texture,
                "warmth": warmth,
            },
        },
    )

    return {
        "session_id": sid,
        "items": items,
        "best_index": best_item["index"],
        "summary": summary,
        "generation": {
            "positive_prompt": positive_prompt,
            "negative_prompt": prompt_data["negative_prompt"],
            "edit_suggestion": prompt_data["edit_suggestion"],
            "generated_image_url": generated_image_url,
        },
    }


@app.get("/api/v1/sessions/{session_id}")
def get_session_history(session_id: str, current_user: dict = Depends(_get_current_user)) -> dict:
    _assert_session_owner(session_id, current_user["id"])
    rows = _load_session_rows(session_id)
    return {"session_id": session_id, "turns": rows}


@app.get("/api/v1/sessions/{session_id}/export")
def export_session_report(session_id: str, current_user: dict = Depends(_get_current_user)) -> PlainTextResponse:
    _assert_session_owner(session_id, current_user["id"])
    rows = _load_session_rows(session_id)
    lines = [f"# Multimodal Art Critic Session Report: {session_id}", ""]

    for idx, row in enumerate(rows, start=1):
        lines.append(f"## Turn {idx}")
        lines.append(f"- Timestamp: {row.get('timestamp', '')}")
        lines.append(f"- Workflow: {row.get('workflow', 'single')}")
        lines.append(f"- Persona: {row.get('persona', '')}")
        lines.append(f"- Description: {row.get('description', '')}")

        if row.get("workflow") == "compare":
            lines.append(f"- Summary: {row.get('summary', '')}")
            lines.append("- Items:")
            for item in row.get("items", []):
                lines.append(
                    f"  - [{item.get('index', 0) + 1}] {item.get('filename', '')}: "
                    f"{item.get('style', '')} / {item.get('emotion', '')}, score {item.get('score', '')}"
                )
        else:
            lines.append(f"- Caption: {row.get('caption', '')}")
            lines.append(f"- Style: {row.get('style', '')}")
            lines.append(f"- Emotion: {row.get('emotion', '')}")
            lines.append(f"- Composition: {row.get('composition', '')}")
            lines.append(f"- Positive Prompt: {row.get('positive_prompt', '')}")
            lines.append(f"- Negative Prompt: {row.get('negative_prompt', '')}")
            lines.append(f"- Generated Image: {row.get('generated_image_url', '')}")

        lines.append("")

    filename = f"session_{session_id}.md"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return PlainTextResponse("\n".join(lines), media_type="text/markdown", headers=headers)


_init_db()
