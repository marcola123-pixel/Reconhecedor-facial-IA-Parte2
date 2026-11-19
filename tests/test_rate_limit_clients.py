"""Testes do isolamento do rate limit por cliente."""

import asyncio
from unittest.mock import patch

import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.rate_limit import RecognitionRateLimitMiddleware


async def reconhecer(request):
    return JSONResponse({"ok": True})


def criar_cliente(max_requests=2, global_max=10):
    app = Starlette(
        routes=[Route("/reconhecer", reconhecer, methods=["POST"])]
    )

    configuracao = {
        "FACEREC_RATE_LIMIT_ENABLED": "1",
        "FACEREC_RATE_LIMIT_MAX": str(max_requests),
        "FACEREC_RATE_LIMIT_WINDOW": "5",
        "FACEREC_RATE_LIMIT_GLOBAL_MAX": str(global_max),
    }

    with patch.dict("os.environ", configuracao):
        app.add_middleware(RecognitionRateLimitMiddleware)

        # Forca a inicializacao do middleware com as variaveis
        # de ambiente configuradas.
        app.middleware_stack = app.build_middleware_stack()

    return app


def executar(cenario, max_requests=2, global_max=10):
    app = criar_cliente(max_requests, global_max)

    async def rodar():
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await cenario(client)

    return asyncio.run(rodar())


def test_web_nao_bloqueia_android():
    async def cenario(client):
        web = {"X-Facerec-Client": "web"}
        android = {"X-Facerec-Client": "android"}

        respostas = []

        for headers in (web, web, web, android, android):
            resposta = await client.post(
                "/reconhecer", headers=headers
            )
            respostas.append(resposta.status_code)

        return respostas

    assert executar(cenario) == [200, 200, 429, 200, 200]


def test_android_tem_limite_independente():
    async def cenario(client):
        android = {"X-Facerec-Client": "android"}

        respostas = []

        for _ in range(3):
            resposta = await client.post(
                "/reconhecer", headers=android
            )
            respostas.append(resposta.status_code)

        return respostas

    assert executar(cenario) == [200, 200, 429]


def test_limite_global_protege_servidor():
    async def cenario(client):
        respostas = []

        for tipo in ("web", "android", "other"):
            resposta = await client.post(
                "/reconhecer",
                headers={"X-Facerec-Client": tipo},
            )
            respostas.append(resposta.status_code)

        return respostas

    return_codes = executar(
        cenario,
        max_requests=2,
        global_max=2,
    )

    assert return_codes == [200, 200, 429]
