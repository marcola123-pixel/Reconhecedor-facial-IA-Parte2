"""Parte 2 — aplicação web do porteiro eletrônico (HTTPS, decisão no servidor).

Usa o experimento escolhido na Parte 1 (runs/<exp>/best.pt + meta.json) e a galeria de pessoas
cadastradas (embeddings/gallery.npz). Nenhuma foto é gravada em disco.

    python scripts/gerar_certificado.py        # uma vez (cria certs/cert.pem e certs/key.pem)
    export FACEREC_RUN=runs/e04_cnn_triplet    # experimento vencedor da Parte 1
    export PORTEIRO_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    python app/main.py                         # abre https://localhost:8443
"""
import base64
import binascii
import io
import os
import sys
from pathlib import Path
import secrets
import sqlite3
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import torch  # noqa: E402
from fastapi import Depends, FastAPI, Header, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles  # noqa: E402
from PIL import Image  # noqa: E402
from typing import Annotated
from pydantic import BaseModel, Field  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware
from app.rate_limit import RecognitionRateLimitMiddleware
from app.security_audit import (
    init_audit_db,
    record_security_event,
    read_security_events,
)
  # noqa: E402

from facerec.detection import FaceDetector, MultipleFacesError
from facerec.gallery import Gallery  # noqa: E402
from facerec.inference import (
    embed_images,
    load_run,
    run_fingerprint
)

HOST, PORT = "127.0.0.1", 8443
RUN_DIR = os.environ.get("FACEREC_RUN", "runs/e04_cnn_triplet")
GALLERY_PATH = os.environ.get("FACEREC_GALLERY", "embeddings/gallery.npz")
TOKEN = os.environ.get("PORTEIRO_TOKEN", "")
MAX_IMAGE_CHARS = 4_000_000          # ~3 MB em base64
MAX_IMAGE_PIXELS = 12_000_000

device = "cuda" if torch.cuda.is_available() else "cpu"
model, meta, transform = load_run(RUN_DIR, device)
THRESHOLD = float(os.environ.get("FACEREC_THRESHOLD", meta["id_threshold"]))   # vem da VALIDAÇÃO (ADR-003)
detector = FaceDetector(
    image_size=meta["image_size"],
    device=device
)
MODEL_ID = run_fingerprint(RUN_DIR)
gallery = Gallery.load(
    GALLERY_PATH,
    expected_model_id=MODEL_ID
)



# ============================================================
# HISTORICO PERSISTENTE DE ACESSOS
# ============================================================

HISTORY_DB_PATH = Path(
    os.environ.get(
        "FACEREC_HISTORY_DB",
        str(ROOT / "data" / "recognition_history.db")
    )
)

HISTORY_RETENTION_DAYS = max(
    1,
    int(os.environ.get("FACEREC_HISTORY_RETENTION_DAYS", "30"))
)

HISTORY_COOLDOWN_SECONDS = 10


def init_history_db():
    HISTORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(HISTORY_DB_PATH, timeout=10) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recognition_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                name TEXT NOT NULL,
                authorized INTEGER NOT NULL,
                similarity REAL NOT NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_created_at
            ON recognition_events(created_at)
        """)

        conn.commit()


def record_history_event(name, authorized, similarity):
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat(timespec="seconds")
    cutoff = now - timedelta(days=HISTORY_RETENTION_DAYS)

    try:
        with sqlite3.connect(HISTORY_DB_PATH, timeout=10) as conn:
            conn.execute("BEGIN IMMEDIATE")

            conn.execute(
                "DELETE FROM recognition_events WHERE created_at < ?",
                (cutoff.isoformat(timespec="seconds"),)
            )

            previous = conn.execute(
                """
                SELECT created_at
                FROM recognition_events
                WHERE name = ? AND authorized = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (name, int(authorized))
            ).fetchone()

            if previous:
                previous_time = datetime.fromisoformat(previous[0])

                if (now - previous_time).total_seconds() < HISTORY_COOLDOWN_SECONDS:
                    conn.commit()
                    return False

            conn.execute(
                """
                INSERT INTO recognition_events
                    (created_at, name, authorized, similarity)
                VALUES (?, ?, ?, ?)
                """,
                (timestamp, name, int(authorized), float(similarity))
            )

            conn.commit()
            return True

    except sqlite3.Error as error:
        print(f"[HISTORICO] Erro ao registrar evento: {error}")
        return False



def delete_history_for_person(name: str) -> int:
    """Remove eventos da pessoa, com comparacao Unicode."""
    from contextlib import closing

    normalized_name = name.strip().casefold()

    with closing(sqlite3.connect(HISTORY_DB_PATH, timeout=10)) as conn:
        with conn:
            conn.execute("BEGIN IMMEDIATE")

            rows = conn.execute(
                "SELECT id, name FROM recognition_events"
            ).fetchall()

            ids = [
                event_id
                for event_id, stored_name in rows
                if stored_name.strip().casefold() == normalized_name
            ]

            if not ids:
                return 0

            conn.executemany(
                "DELETE FROM recognition_events WHERE id = ?",
                [(event_id,) for event_id in ids]
            )

            return len(ids)



def read_history(limit=100):
    limit = max(1, min(int(limit), 200))
    cutoff = (
        datetime.now(timezone.utc) -
        timedelta(days=HISTORY_RETENTION_DAYS)
    ).isoformat(timespec="seconds")

    with sqlite3.connect(HISTORY_DB_PATH, timeout=10) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT id, created_at, name, authorized, similarity
            FROM recognition_events
            WHERE created_at >= ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (cutoff, limit)
        ).fetchall()

    return [
        {
            "id": row["id"],
            "data_hora": row["created_at"],
            "nome": row["name"],
            "liberado": bool(row["authorized"]),
            "similaridade": row["similarity"]
        }
        for row in rows
    ]


def read_history_stats():
    cutoff = (
        datetime.now(timezone.utc) -
        timedelta(days=HISTORY_RETENTION_DAYS)
    ).isoformat(timespec="seconds")

    with sqlite3.connect(HISTORY_DB_PATH, timeout=10) as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_registros,
                COALESCE(SUM(
                    CASE WHEN authorized = 1 THEN 1 ELSE 0 END
                ), 0) AS total_liberados,
                COALESCE(SUM(
                    CASE WHEN authorized = 0 THEN 1 ELSE 0 END
                ), 0) AS total_negados
            FROM recognition_events
            WHERE created_at >= ?
            """,
            (cutoff,)
        ).fetchone()

    return {
        "total_registros": row[0],
        "total_liberados": row[1],
        "total_negados": row[2]
    }


init_history_db()

SECURITY_AUDIT_DB_PATH = Path(
    os.environ.get(
        "FACEREC_SECURITY_AUDIT_DB",
        str(ROOT / "data" / "security_audit.db"),
    )
)

init_audit_db(SECURITY_AUDIT_DB_PATH)

app = FastAPI(title="Porteiro Eletrônico")

class RequestBodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    """Limita o tamanho total do corpo das requisições HTTP."""

    def __init__(self, app, max_body_size: int):
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            key.lower(): value
            for key, value in scope.get("headers", [])
        }

        content_length = headers.get(b"content-length")

        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                response = JSONResponse(
                    {"detail": "Cabeçalho Content-Length inválido."},
                    status_code=400
                )
                await response(scope, receive, send)
                return

            if size < 0:
                response = JSONResponse(
                    {"detail": "Tamanho de requisição inválido."},
                    status_code=400
                )
                await response(scope, receive, send)
                return

            if size > self.max_body_size:
                response = JSONResponse(
                    {"detail": "Requisição muito grande. Limite de 32 MB."},
                    status_code=413
                )
                await response(scope, receive, send)
                return

        received = 0
        response_started = False

        async def limited_receive():
            nonlocal received

            message = await receive()

            if message["type"] == "http.request":
                received += len(message.get("body", b""))

                if received > self.max_body_size:
                    raise RequestBodyTooLarge()

            return message

        async def tracked_send(message):
            nonlocal response_started

            if message["type"] == "http.response.start":
                response_started = True

            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)

        except RequestBodyTooLarge:
            if not response_started:
                response = JSONResponse(
                    {"detail": "Requisição muito grande. Limite de 32 MB."},
                    status_code=413
                )
                await response(scope, receive, send)


app.add_middleware(
    RequestBodyLimitMiddleware,
    max_body_size=32 * 1024 * 1024
)

app.add_middleware(CORSMiddleware, allow_origins=[f"https://127.0.0.1:{PORT}", f"https://localhost:{PORT}"],
                   allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type", "X-Porteiro-Token", "X-Facerec-Client"])


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        r = await call_next(request)
        r.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        r.headers["X-Content-Type-Options"] = "nosniff"
        r.headers["X-Frame-Options"] = "DENY"
        r.headers["Referrer-Policy"] = "no-referrer"
        r.headers["Permissions-Policy"] = "camera=(self), microphone=()"
        r.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        return r


app.add_middleware(SecurityHeaders)
app.add_middleware(RecognitionRateLimitMiddleware)
app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")


def safe_audit_event(event_type, success):
    """Registra auditoria sem revelar credenciais."""
    try:
        record_security_event(
            SECURITY_AUDIT_DB_PATH,
            event_type,
            success,
        )
        return True
    except (OSError, ValueError, sqlite3.Error) as error:
        print(
            "[AUDITORIA] Falha ao registrar evento: "
            + type(error).__name__
        )
        return False


def require_admin(x_porteiro_token: str = Header(default="")):
    """Protege as operacoes administrativas."""

    if not TOKEN:
        raise HTTPException(
            403,
            "defina PORTEIRO_TOKEN no servidor para habilitar a administracao"
        )

    if not secrets.compare_digest(x_porteiro_token, TOKEN):
        event_type = (
            "admin_login_failure"
            if x_porteiro_token
            else "admin_access_denied"
        )
        safe_audit_event(event_type, False)
        raise HTTPException(401, "token invalido")


def decode_image(data_url: str) -> Image.Image:
    if not isinstance(data_url, str):
        raise HTTPException(400, "Imagem inválida.")

    if len(data_url) > MAX_IMAGE_CHARS:
        raise HTTPException(413, "Imagem grande demais.")

    try:
        header, payload = data_url.split(",", 1)

        if not header.startswith("data:image/"):
            raise HTTPException(400, "Formato de imagem inválido.")

        if ";base64" not in header:
            raise HTTPException(400, "Imagem deve utilizar Base64.")

        raw = base64.b64decode(payload, validate=True)

        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(400, "Formato de imagem não permitido.")

            if image.width > 4096 or image.height > 4096:
                raise HTTPException(
                    413,
                    "Dimensões da imagem muito grandes."
                )

            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise HTTPException(
                    413,
                    "Quantidade de pixels da imagem muito grande."
                )

            image.load()
            return image.convert("RGB")

    except HTTPException:
        raise

    except (
        ValueError,
        binascii.Error,
        OSError,
        Image.DecompressionBombError
    ):
        raise HTTPException(400, "Imagem inválida.")


class FrameIn(BaseModel):
    image: Annotated[str, Field(max_length=4_000_000)]


class EnrollIn(BaseModel):
    nome: Annotated[str, Field(min_length=1, max_length=80)]
    imagens: list[
        Annotated[str, Field(max_length=2_800_000)]
    ] = Field(min_length=3, max_length=10)


@app.get("/")
def home():
    return FileResponse(ROOT / "app" / "static" / "index.html")


@app.get("/status")
def status():
    return {"experimento": meta["name"], "limiar": THRESHOLD, "pessoas_cadastradas": len(gallery),
            "device": device}

@app.get("/pessoas", dependencies=[Depends(require_admin)])
def listar_pessoas():
    return {
        "total": len(gallery),
        "pessoas": gallery.people()
    }



@app.post("/reconhecer")
def reconhecer(frame: FrameIn):
    try:
        face = detector.crop(decode_image(frame.image))

    except MultipleFacesError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error)
        )

    if face is None:
        return {
            "rosto_detectado": False,
            "mensagem": "Nenhum rosto foi detectado."
        }

    # Gera o embedding facial
    emb = embed_images(model, transform, [face], device)[0]

    # Identifica a pessoa usando o limiar do E07
    m = gallery.identify(
    emb,
    threshold=THRESHOLD
)

    # A decisão é realizada no servidor
    liberado = m.name is not None

    record_history_event(
        name=m.name or "Desconhecido",
        authorized=liberado,
        similarity=round(m.score, 4)
    )

    return {
        "rosto_detectado": True,
        "liberado": liberado,
        "nome": m.name,
        "similaridade": round(m.score, 4)
    }

@app.get("/seguranca/auditoria", dependencies=[Depends(require_admin)])
def consultar_auditoria(limit: int = 100):
    return {
        "eventos": read_security_events(
            SECURITY_AUDIT_DB_PATH,
            limit,
        )
    }


@app.get("/historico", dependencies=[Depends(require_admin)])
def consultar_historico(limit: int = 100):
    registros = read_history(limit)
    estatisticas = read_history_stats()

    return {
        "total_retornado": len(registros),
        "registros": registros,
        "estatisticas": estatisticas,
        "retencao_dias": HISTORY_RETENTION_DAYS
    }


@app.post("/pessoas", dependencies=[Depends(require_admin)])
def cadastrar(body: EnrollIn):

    if not body.nome.strip():
        raise HTTPException(400, "Informe um nome válido.")
    nome = body.nome.strip()

    if any(
        existente.casefold() == nome.casefold()
        for existente in gallery.names()
    ):
        raise HTTPException(
            status_code=409,
            detail="Já existe um cadastro com esse nome. Remova o cadastro anterior antes de cadastrar novamente."
        )

    if len(body.imagens) < 3:
        raise HTTPException(
            422,
            "Envie pelo menos 3 imagens."
        )

    faces = []
    rejeitadas = 0

    for imagem in body.imagens:
        try:
            face = detector.crop(decode_image(imagem))

            if face is not None:
                faces.append(face)
            else:
                rejeitadas += 1

        except MultipleFacesError:
            rejeitadas += 1

        except HTTPException:
            rejeitadas += 1

    if len(faces) < 3:
        raise HTTPException(
            422,
            "São necessários pelo menos 3 rostos válidos."
        )

    embeddings = embed_images(
        model,
        transform,
        faces,
        device
    )


    substituida = gallery.enroll(nome, embeddings)
    gallery.save(GALLERY_PATH)
    safe_audit_event("person_created", True)

    return {
        "cadastradas": len(faces),
        "rejeitadas": rejeitadas,
        "pessoas": len(gallery),
        "substituida": substituida,
        "mensagem": (
            "Cadastro anterior substituído com sucesso."
            if substituida
            else "Pessoa cadastrada com sucesso."
        )
    }


@app.delete("/pessoas/{nome}", dependencies=[Depends(require_admin)])
def remover(nome: str):
    import copy

    existing_name = next(
        (name for name in gallery.names()
         if name.casefold() == nome.strip().casefold()),
        None
    )

    if existing_name is None:
        raise HTTPException(404, "pessoa nao encontrada")

    previous_gallery = copy.deepcopy(gallery)

    try:
        if not gallery.remove(existing_name):
            raise HTTPException(404, "pessoa nao encontrada")

        gallery.save(GALLERY_PATH)
        delete_history_for_person(existing_name)

    except (sqlite3.Error, OSError, ValueError) as exc:
        gallery._sum = previous_gallery._sum
        gallery._count = previous_gallery._count
        gallery.embedding_dim = previous_gallery.embedding_dim

        try:
            gallery.save(GALLERY_PATH)
        except (OSError, ValueError):
            safe_audit_event("person_deleted", False)
            raise HTTPException(
                500,
                "Falha na exclusao e na recuperacao da galeria."
            ) from exc

        safe_audit_event("person_deleted", False)
        raise HTTPException(
            500,
            "Exclusao interrompida; galeria restaurada."
        ) from exc

    safe_audit_event("person_deleted", True)
    return {"removida": True, "pessoas": len(gallery)}




if __name__ == "__main__":
    import uvicorn
    cert, key = ROOT / "certs" / "cert.pem", ROOT / "certs" / "key.pem"
    if not (cert.exists() and key.exists()):
        sys.exit("Certificado TLS não encontrado. Rode: python scripts/gerar_certificado.py")
    print(f"https://{HOST}:{PORT}  | experimento={meta['name']} | limiar={THRESHOLD:.3f}")
    uvicorn.run(app, host=HOST, port=PORT, ssl_keyfile=str(key), ssl_certfile=str(cert))
