import secrets
import asyncio
import base64
import importlib
import io
import os
from pathlib import Path
import sys
from unittest.mock import patch

import httpx
import numpy as np
import pytest
from PIL import Image

import facerec.inference as inference
import facerec.detection as detection
from facerec.gallery import Gallery


@pytest.fixture(scope="module")
def api_module(tmp_path_factory):
    """Importa a API com modelo, detector e galeria simulados."""

    temp_dir = tmp_path_factory.mktemp("api_test")
    gallery_path = temp_dir / "gallery_test.npz"

    fake_meta = {
        "name": "experimento_teste",
        "image_size": 160,
        "id_threshold": 0.5,
    }

    class FakeDetector:
        def __init__(self, image_size=160, device=None):
            pass

        def crop(self, image):
            return image

    with patch.dict(
        os.environ,
        {
            "FACEREC_RUN": "modelo_simulado",
            "FACEREC_GALLERY": str(gallery_path),
            "FACEREC_HISTORY_DB": str(temp_dir / "history_import.db"),
            "FACEREC_SECURITY_AUDIT_DB": str(temp_dir / "audit_import.db"),
            "PORTEIRO_TOKEN": "token-de-teste",
            "FACEREC_THRESHOLD": "0.5",
            "FACEREC_RATE_LIMIT_ENABLED": "0",
            "FACEREC_RATE_LIMIT_ENABLED": "0",
        },
    ), patch.object(
        inference,
        "load_run",
        return_value=("modelo_falso", fake_meta, "transform_falso"),
    ), patch.object(
        inference,
        "run_fingerprint",
        return_value="modelo_teste",
    ), patch.object(
        detection,
        "FaceDetector",
        FakeDetector,
    ), patch.object(
        Gallery,
        "load",
        classmethod(
            lambda cls, path, expected_model_id: Gallery(
                model_id="modelo_teste"
            )
        ),
    ):
        sys.modules.pop("app.main", None)
        main = importlib.import_module("app.main")

        # Inicializa os middlewares enquanto o ambiente
        # simulado dos testes ainda esta ativo.
        main.app.middleware_stack = main.app.build_middleware_stack()

    main.GALLERY_PATH = str(gallery_path)

    yield main

    sys.modules.pop("app.main", None)


def make_request(main, method, path, **kwargs):
    """Executa uma requisição HTTP contra a aplicação ASGI."""

    async def execute():
        transport = httpx.ASGITransport(app=main.app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(execute())


def prepare_api(main, tmp_path, monkeypatch):
    """Isola os dados e configurações de cada teste."""

    main.TOKEN = secrets.token_urlsafe(32)
    main.GALLERY_PATH = str(tmp_path / "gallery_test.npz")
    main.gallery = Gallery(model_id="modelo_teste")

    main.HISTORY_DB_PATH = tmp_path / "history_test.db"
    main.init_history_db()

    main.SECURITY_AUDIT_DB_PATH = tmp_path / "security_test.db"
    main.init_audit_db(main.SECURITY_AUDIT_DB_PATH)

    monkeypatch.setattr(
        main.detector,
        "crop",
        lambda image: image,
    )

    return {"X-Porteiro-Token": main.TOKEN}


def image_data_url():
    """Cria uma imagem PNG sintética válida, sem usar fotos reais."""

    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color="white").save(
        buffer,
        format="PNG",
    )

    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def fake_embeddings(embedding):
    """Cria uma função simulada que retorna embeddings determinísticos."""

    def generate(model, transform, faces, device):
        vector = np.asarray(embedding, dtype=np.float32)
        return np.tile(vector, (len(faces), 1))

    return generate


# ============================================================
# AUTENTICAÇÃO E ACESSO
# ============================================================

def test_pessoas_sem_token_retorna_401(api_module, tmp_path, monkeypatch):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    response = make_request(main, "GET", "/pessoas")

    assert response.status_code == 401


def test_pessoas_com_token_incorreto_retorna_401(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    response = make_request(
        main,
        "GET",
        "/pessoas",
        headers={"X-Porteiro-Token": "token-incorreto"},
    )

    assert response.status_code == 401


def test_pessoas_com_token_correto_acessa_rota(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    response = make_request(
        main,
        "GET",
        "/pessoas",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0


# ============================================================
# STATUS E CABEÇALHOS DE SEGURANÇA
# ============================================================

def test_rota_status_retorna_resposta(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    response = make_request(main, "GET", "/status")

    assert response.status_code == 200
    assert response.json()["experimento"] == "experimento_teste"
    assert response.json()["limiar"] == 0.5
    assert response.json()["pessoas_cadastradas"] == 0


def test_respostas_contem_cabecalhos_de_seguranca(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    response = make_request(main, "GET", "/status")

    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "no-referrer"
    assert response.headers.get("Content-Security-Policy") is not None


# ============================================================
# CADASTRO DE PESSOAS
# ============================================================

def test_cadastro_com_tres_imagens_validas(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    monkeypatch.setattr(
        main,
        "embed_images",
        fake_embeddings([1.0, 0.0]),
    )

    response = make_request(
        main,
        "POST",
        "/pessoas",
        headers=headers,
        json={
            "nome": "Pessoa Teste",
            "imagens": [image_data_url() for _ in range(3)],
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["cadastradas"] == 3
    assert data["rejeitadas"] == 0
    assert data["pessoas"] == 1
    assert data["substituida"] is False


def test_cadastro_rejeita_menos_de_tres_imagens(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    response = make_request(
        main,
        "POST",
        "/pessoas",
        headers=headers,
        json={
            "nome": "Pessoa Teste",
            "imagens": [image_data_url(), image_data_url()],
        },
    )

    assert response.status_code == 422


def test_cadastro_rejeita_nome_em_branco(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    response = make_request(
        main,
        "POST",
        "/pessoas",
        headers=headers,
        json={
            "nome": "   ",
            "imagens": [image_data_url() for _ in range(3)],
        },
    )

    assert response.status_code == 400


def test_cadastro_contabiliza_imagem_invalida(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    monkeypatch.setattr(
        main,
        "embed_images",
        fake_embeddings([1.0, 0.0]),
    )

    imagens = [
        image_data_url(),
        "data:image/png;base64,nao-e-uma-imagem-valida",
        image_data_url(),
        image_data_url(),
    ]

    response = make_request(
        main,
        "POST",
        "/pessoas",
        headers=headers,
        json={
            "nome": "Pessoa Teste",
            "imagens": imagens,
        },
    )

    assert response.status_code == 200
    assert response.json()["cadastradas"] == 3
    assert response.json()["rejeitadas"] == 1


def test_cadastro_rejeita_quando_nao_ha_tres_rostos_validos(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    imagens = [
        image_data_url(),
        "data:image/png;base64,imagem-invalida",
        "data:image/png;base64,outra-imagem-invalida",
    ]

    response = make_request(
        main,
        "POST",
        "/pessoas",
        headers=headers,
        json={
            "nome": "Pessoa Teste",
            "imagens": imagens,
        },
    )

    assert response.status_code == 422
    assert len(main.gallery) == 0


def test_cadastro_duplicado_retorna_409_sem_substituir(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    monkeypatch.setattr(
        main,
        "embed_images",
        fake_embeddings([1.0, 0.0]),
    )

    payload = {
        "nome": "Pessoa Teste",
        "imagens": [image_data_url() for _ in range(3)],
    }

    primeira = make_request(
        main, "POST", "/pessoas", headers=headers, json=payload
    )

    # Mesmo nome, mas com letras minúsculas.
    payload_duplicado = {
        **payload,
        "nome": "pessoa teste",
    }

    segunda = make_request(
        main,
        "POST",
        "/pessoas",
        headers=headers,
        json=payload_duplicado,
    )

    assert primeira.status_code == 200
    assert primeira.json()["substituida"] is False

    assert segunda.status_code == 409
    assert len(main.gallery) == 1
    assert main.gallery.names() == ["Pessoa Teste"]

    # Confirma que o protótipo original continua identificável.
    resultado = main.gallery.identify(
        np.array([1.0, 0.0]),
        threshold=0.5,
    )

    assert resultado.name == "Pessoa Teste"

# ============================================================
# RECONHECIMENTO FACIAL
# ============================================================

def test_reconhece_pessoa_cadastrada(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    main.gallery.enroll(
        "Pessoa Conhecida",
        np.array([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]),
    )

    monkeypatch.setattr(
        main,
        "embed_images",
        fake_embeddings([1.0, 0.0]),
    )

    response = make_request(
        main,
        "POST",
        "/reconhecer",
        json={"image": image_data_url()},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["rosto_detectado"] is True
    assert data["liberado"] is True
    assert data["nome"] == "Pessoa Conhecida"


def test_classifica_pessoa_desconhecida(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    main.gallery.enroll(
        "Pessoa Conhecida",
        np.array([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]),
    )

    monkeypatch.setattr(
        main,
        "embed_images",
        fake_embeddings([0.0, 1.0]),
    )

    response = make_request(
        main,
        "POST",
        "/reconhecer",
        json={"image": image_data_url()},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["rosto_detectado"] is True
    assert data["liberado"] is False
    assert data["nome"] is None


def test_reconhecimento_sem_rosto_detectado(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    monkeypatch.setattr(
        main.detector,
        "crop",
        lambda image: None,
    )

    response = make_request(
        main,
        "POST",
        "/reconhecer",
        json={"image": image_data_url()},
    )

    assert response.status_code == 200
    assert response.json()["rosto_detectado"] is False


def test_reconhecimento_com_multiplos_rostos_retorna_422(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    def raise_multiple_faces(image):
        raise detection.MultipleFacesError(
            "Mais de um rosto foi detectado."
        )

    monkeypatch.setattr(
        main.detector,
        "crop",
        raise_multiple_faces,
    )

    response = make_request(
        main,
        "POST",
        "/reconhecer",
        json={"image": image_data_url()},
    )

    assert response.status_code == 422


def test_reconhecimento_com_imagem_invalida_retorna_400(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    response = make_request(
        main,
        "POST",
        "/reconhecer",
        json={"image": "data:image/png;base64,imagem-invalida"},
    )

    assert response.status_code == 400


# ============================================================
# EXCLUSÃO E PERSISTÊNCIA
# ============================================================

def test_exclui_pessoa_cadastrada(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    main.gallery.enroll(
        "Pessoa Teste",
        np.array([[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]),
    )

    response = make_request(
        main,
        "DELETE",
        "/pessoas/Pessoa Teste",
        headers=headers,
    )

    assert response.status_code == 200
    assert len(main.gallery) == 0


def test_exclusao_de_pessoa_inexistente_retorna_404(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    response = make_request(
        main,
        "DELETE",
        "/pessoas/Nao Existe",
        headers=headers,
    )

    assert response.status_code == 404


def test_cadastro_persiste_galeria_em_arquivo_temporario(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    monkeypatch.setattr(
        main,
        "embed_images",
        fake_embeddings([1.0, 0.0]),
    )

    response = make_request(
        main,
        "POST",
        "/pessoas",
        headers=headers,
        json={
            "nome": "Pessoa Persistida",
            "imagens": [image_data_url() for _ in range(3)],
        },
    )

    assert response.status_code == 200
    assert os.path.exists(main.GALLERY_PATH)

    galeria_salva = Gallery.load(
        main.GALLERY_PATH,
        expected_model_id="modelo_teste",
    )

    assert len(galeria_salva) == 1

    pessoas = galeria_salva.people()

    assert len(pessoas) == 1
    assert pessoas[0]["nome"] == "Pessoa Persistida"
    assert pessoas[0]["imagens"] == 3

# ============================================================
# SEGURANÇA: CONFIGURAÇÃO DO TOKEN
# ============================================================

def test_administracao_desativada_sem_token_configurado(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    main.TOKEN = ""

    response = make_request(
        main,
        "GET",
        "/pessoas",
    )

    assert response.status_code == 403


# ============================================================
# SEGURANÇA: LIMITE DO CORPO HTTP
# ============================================================

def run_body_limit_middleware(
    middleware,
    chunks,
    content_length=None,
):
    """Executa o middleware isoladamente com blocos HTTP simulados."""

    async def execute():
        headers = []

        if content_length is not None:
            headers.append(
                (b"content-length", str(content_length).encode())
            )

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/teste",
            "raw_path": b"/teste",
            "query_string": b"",
            "headers": headers,
            "server": ("test", 80),
            "client": ("test", 1234),
        }

        messages = [
            {
                "type": "http.request",
                "body": chunk,
                "more_body": index < len(chunks) - 1,
            }
            for index, chunk in enumerate(chunks)
        ]

        if not messages:
            messages = [
                {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }
            ]

        message_index = 0
        sent = []

        async def receive():
            nonlocal message_index

            if message_index < len(messages):
                message = messages[message_index]
                message_index += 1
                return message

            return {
                "type": "http.disconnect",
            }

        async def send(message):
            sent.append(message)

        async def fake_app(scope, receive, send):
            while True:
                message = await receive()

                if message["type"] == "http.disconnect":
                    break

                if not message.get("more_body", False):
                    break

            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })

            await send({
                "type": "http.response.body",
                "body": b"OK",
            })

        wrapped = middleware(fake_app)

        await wrapped(scope, receive, send)

        status = next(
            message["status"]
            for message in sent
            if message["type"] == "http.response.start"
        )

        return status

    return asyncio.run(execute())


def test_middleware_bloqueia_content_length_acima_do_limite(api_module):
    limite = 32
    middleware = lambda app: api_module.RequestBodyLimitMiddleware(
    app,
    max_body_size=limite,
)

    status = run_body_limit_middleware(
        middleware,
        chunks=[b"x" * 33],
        content_length=33,
    )

    assert status == 413


def test_middleware_bloqueia_corpo_excedido_em_blocos(api_module):
    limite = 32
    middleware = lambda app: api_module.RequestBodyLimitMiddleware(
    app,
    max_body_size=limite,
)

    status = run_body_limit_middleware(
        middleware,
        chunks=[
            b"x" * 20,
            b"y" * 20,
        ],
    )

    assert status == 413


def test_middleware_aceita_corpo_dentro_do_limite(api_module):
    limite = 32
    middleware = lambda app: api_module.RequestBodyLimitMiddleware(
    app,
    max_body_size=limite,
)

    status = run_body_limit_middleware(
        middleware,
        chunks=[
            b"x" * 16,
            b"y" * 16,
        ],
    )

    assert status == 200

# ============================================================
# HISTORICO DE RECONHECIMENTO
# ============================================================

def test_historico_sem_token_retorna_401(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    response = make_request(main, "GET", "/historico")

    assert response.status_code == 401


def test_historico_com_token_incorreto_retorna_401(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    response = make_request(
        main,
        "GET",
        "/historico",
        headers={"X-Porteiro-Token": "token-incorreto"},
    )

    assert response.status_code == 401


def test_historico_com_token_correto_retorna_lista_vazia(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    response = make_request(
        main,
        "GET",
        "/historico",
        headers=headers,
    )

    assert response.status_code == 200

    dados = response.json()

    assert dados["total_retornado"] == 0
    assert dados["registros"] == []
    assert dados["retencao_dias"] == 30


def test_gravacao_de_evento_aparece_no_historico(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    gravado = main.record_history_event(
        name="Pessoa_Teste_Historico",
        authorized=True,
        similarity=0.9876,
    )

    assert gravado is True

    response = make_request(
        main,
        "GET",
        "/historico",
        headers=headers,
    )

    assert response.status_code == 200

    dados = response.json()

    assert dados["total_retornado"] == 1

    registro = dados["registros"][0]

    assert registro["nome"] == "Pessoa_Teste_Historico"
    assert registro["liberado"] is True
    assert registro["similaridade"] == 0.9876
    assert registro["data_hora"]


def test_historico_bloqueia_evento_duplicado_em_10_segundos(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    primeiro = main.record_history_event(
        name="Pessoa_Teste_Duplicidade",
        authorized=False,
        similarity=0.3210,
    )

    segundo = main.record_history_event(
        name="Pessoa_Teste_Duplicidade",
        authorized=False,
        similarity=0.3210,
    )

    registros = main.read_history()

    assert primeiro is True
    assert segundo is False
    assert len(registros) == 1
    assert registros[0]["nome"] == "Pessoa_Teste_Duplicidade"



# ============================================================
# HISTORICO: RETENCAO E ESTATISTICAS
# ============================================================

def test_historico_filtra_registros_expirados(
    api_module, tmp_path, monkeypatch
):
    import sqlite3
    from datetime import datetime, timezone, timedelta

    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    antigo = (
        datetime.now(timezone.utc) - timedelta(days=31)
    ).isoformat(timespec="seconds")

    with sqlite3.connect(main.HISTORY_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO recognition_events
            (created_at, name, authorized, similarity)
            VALUES (?, ?, ?, ?)
            """,
            (antigo, "Registro_Expirado", 1, 0.9)
        )

    assert main.read_history() == []
    assert main.read_history_stats()["total_registros"] == 0


def test_estatisticas_contabilizam_decisoes(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    assert main.record_history_event("Pessoa_A", True, 0.9)
    assert main.record_history_event("Pessoa_B", False, 0.2)
    assert main.record_history_event("Pessoa_C", True, 0.8)

    stats = main.read_history_stats()

    assert stats["total_registros"] == 3
    assert stats["total_liberados"] == 2
    assert stats["total_negados"] == 1


def test_novo_evento_remove_registros_expirados(
    api_module, tmp_path, monkeypatch
):
    import sqlite3
    from datetime import datetime, timezone, timedelta

    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    antigo = (
        datetime.now(timezone.utc) - timedelta(days=31)
    ).isoformat(timespec="seconds")

    with sqlite3.connect(main.HISTORY_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO recognition_events
            (created_at, name, authorized, similarity)
            VALUES (?, ?, ?, ?)
            """,
            (antigo, "Registro_Antigo", 0, 0.1)
        )

    assert main.record_history_event("Pessoa_Nova", True, 0.95)

    with sqlite3.connect(main.HISTORY_DB_PATH) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM recognition_events"
        ).fetchone()[0]

    assert total == 1
    assert main.read_history_stats()["total_registros"] == 1


# ============================================================
# INTEGRACAO DA AUDITORIA DE SEGURANCA
# ============================================================

def test_auditoria_sem_token_retorna_401(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    response = make_request(
        main, "GET", "/seguranca/auditoria"
    )

    assert response.status_code == 401


def test_auditoria_token_incorreto_retorna_401(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    prepare_api(main, tmp_path, monkeypatch)

    response = make_request(
        main,
        "GET",
        "/seguranca/auditoria",
        headers={"X-Porteiro-Token": "token-errado"},
    )

    assert response.status_code == 401


def test_auditoria_token_correto_retorna_200(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    response = make_request(
        main,
        "GET",
        "/seguranca/auditoria",
        headers=headers,
    )

    assert response.status_code == 200
    assert "eventos" in response.json()


def test_auditoria_registra_tentativas_negadas(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    response_sem_token = make_request(
        main, "GET", "/pessoas"
    )

    response_token_errado = make_request(
        main,
        "GET",
        "/pessoas",
        headers={"X-Porteiro-Token": "segredo-de-teste-invalido"},
    )

    assert response_sem_token.status_code == 401
    assert response_token_errado.status_code == 401

    consulta = make_request(
        main,
        "GET",
        "/seguranca/auditoria",
        headers=headers,
    )

    assert consulta.status_code == 200

    eventos = consulta.json()["eventos"]
    tipos = [evento["tipo"] for evento in eventos]

    assert "admin_access_denied" in tipos
    assert "admin_login_failure" in tipos
    assert all(evento["sucesso"] is False for evento in eventos)

    # O token nunca deve aparecer no retorno.
    assert "segredo-de-teste-invalido" not in consulta.text
    assert "token-de-teste" not in consulta.text


def test_auditoria_respeita_limite(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    for _ in range(4):
        response = make_request(
            main, "GET", "/pessoas"
        )
        assert response.status_code == 401

    consulta = make_request(
        main,
        "GET",
        "/seguranca/auditoria?limit=2",
        headers=headers,
    )

    assert consulta.status_code == 200
    assert len(consulta.json()["eventos"]) == 2


# ============================================================
# AUDITORIA DE OPERACOES ADMINISTRATIVAS
# ============================================================

def test_auditoria_cadastro_registra_sucesso(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    monkeypatch.setattr(
        main,
        "embed_images",
        fake_embeddings([1.0, 0.0]),
    )

    response = make_request(
        main,
        "POST",
        "/pessoas",
        headers=headers,
        json={
            "nome": "Pessoa Auditoria",
            "imagens": [image_data_url() for _ in range(3)],
        },
    )

    assert response.status_code == 200
    assert Path(main.GALLERY_PATH).exists()

    eventos = main.read_security_events(
        main.SECURITY_AUDIT_DB_PATH
    )

    assert len(eventos) == 1
    assert eventos[0]["tipo"] == "person_created"
    assert eventos[0]["sucesso"] is True


def test_auditoria_exclusao_registra_sucesso(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    main.gallery.enroll(
        "Pessoa Auditoria",
        np.array([
            [1.0, 0.0],
            [1.0, 0.0],
            [1.0, 0.0],
        ]),
    )

    response = make_request(
        main,
        "DELETE",
        "/pessoas/Pessoa Auditoria",
        headers=headers,
    )

    assert response.status_code == 200
    assert len(main.gallery) == 0

    eventos = main.read_security_events(
        main.SECURITY_AUDIT_DB_PATH
    )

    assert len(eventos) == 1
    assert eventos[0]["tipo"] == "person_deleted"
    assert eventos[0]["sucesso"] is True


def test_auditoria_cadastro_duplicado_nao_registra_sucesso(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    main.gallery.enroll(
        "Pessoa Existente",
        np.array([
            [1.0, 0.0],
            [1.0, 0.0],
            [1.0, 0.0],
        ]),
    )

    response = make_request(
        main,
        "POST",
        "/pessoas",
        headers=headers,
        json={
            "nome": "pessoa existente",
            "imagens": [image_data_url() for _ in range(3)],
        },
    )

    assert response.status_code == 409
    assert len(main.gallery) == 1

    eventos = main.read_security_events(
        main.SECURITY_AUDIT_DB_PATH
    )

    assert not any(
        evento["tipo"] == "person_created"
        for evento in eventos
    )


def test_auditoria_exclusao_inexistente_nao_registra_sucesso(
    api_module, tmp_path, monkeypatch
):
    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    response = make_request(
        main,
        "DELETE",
        "/pessoas/Pessoa Inexistente",
        headers=headers,
    )

    assert response.status_code == 404

    eventos = main.read_security_events(
        main.SECURITY_AUDIT_DB_PATH
    )

    assert not any(
        evento["tipo"] == "person_deleted"
        for evento in eventos
    )


def test_auditoria_indisponivel_nao_interrompe_cadastro(
    api_module, tmp_path, monkeypatch
):
    import sqlite3

    main = api_module
    headers = prepare_api(main, tmp_path, monkeypatch)

    monkeypatch.setattr(
        main,
        "embed_images",
        fake_embeddings([1.0, 0.0]),
    )

    def falha_simulada(*args, **kwargs):
        raise sqlite3.OperationalError(
            "falha simulada no banco de auditoria"
        )

    monkeypatch.setattr(
        main,
        "record_security_event",
        falha_simulada,
    )

    response = make_request(
        main,
        "POST",
        "/pessoas",
        headers=headers,
        json={
            "nome": "Pessoa Sem Auditoria",
            "imagens": [image_data_url() for _ in range(3)],
        },
    )

    # Confirma a politica atual de disponibilidade.
    assert response.status_code == 200
    assert len(main.gallery) == 1
    assert Path(main.GALLERY_PATH).exists()

    # A auditoria nao deve inventar um registro.
    eventos = main.read_security_events(
        main.SECURITY_AUDIT_DB_PATH
    )

    assert eventos == []
