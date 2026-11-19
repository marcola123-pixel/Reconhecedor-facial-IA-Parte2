
import asyncio

from app.rate_limit import RecognitionRateLimitMiddleware


def executar_requisicao(middleware, path="/reconhecer", method="POST"):
    """Simula uma requisicao ASGI sem carregar o modelo facial."""

    async def executar():
        mensagens = []

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8443),
        }

        async def receive():
            return {
                "type": "http.request",
                "body": b"",
                "more_body": False,
            }

        async def send(message):
            mensagens.append(message)

        await middleware(scope, receive, send)

        inicio = next(
            m for m in mensagens
            if m["type"] == "http.response.start"
        )

        headers = {
            k.decode().lower(): v.decode()
            for k, v in inicio.get("headers", [])
        }

        return inicio["status"], headers

    return asyncio.run(executar())


async def aplicativo_simulado(scope, receive, send):
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [],
    })
    await send({
        "type": "http.response.body",
        "body": b"ok",
    })


def configurar(monkeypatch, enabled="1", maximum="2"):
    monkeypatch.setenv("FACEREC_RATE_LIMIT_ENABLED", enabled)
    monkeypatch.setenv("FACEREC_RATE_LIMIT_MAX", maximum)
    monkeypatch.setenv("FACEREC_RATE_LIMIT_WINDOW", "5")

    return RecognitionRateLimitMiddleware(aplicativo_simulado)


def test_rate_limit_permite_requisicoes_normais(monkeypatch):
    middleware = configurar(monkeypatch)

    assert executar_requisicao(middleware)[0] == 200
    assert executar_requisicao(middleware)[0] == 200


def test_rate_limit_bloqueia_excesso_com_429(monkeypatch):
    middleware = configurar(monkeypatch)

    executar_requisicao(middleware)
    executar_requisicao(middleware)

    status, headers = executar_requisicao(middleware)

    assert status == 429
    assert int(headers["retry-after"]) >= 1


def test_rate_limit_nao_bloqueia_outras_rotas(monkeypatch):
    middleware = configurar(monkeypatch, maximum="1")

    assert executar_requisicao(middleware)[0] == 200
    assert executar_requisicao(
        middleware, path="/status", method="GET"
    )[0] == 200


def test_rate_limit_desativado_nao_bloqueia(monkeypatch):
    middleware = configurar(monkeypatch, enabled="0", maximum="1")

    for _ in range(5):
        assert executar_requisicao(middleware)[0] == 200


def test_rate_limit_recupera_apos_janela(monkeypatch):
    from unittest.mock import patch

    middleware = configurar(monkeypatch, maximum="2")

    with patch("app.rate_limit.time.monotonic", return_value=100.0):
        assert executar_requisicao(middleware)[0] == 200
        assert executar_requisicao(middleware)[0] == 200
        assert executar_requisicao(middleware)[0] == 429

    with patch("app.rate_limit.time.monotonic", return_value=106.0):
        assert executar_requisicao(middleware)[0] == 200
