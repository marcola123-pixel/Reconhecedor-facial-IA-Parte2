# Next Face Premium — Reconhecimento Facial 1:N (Parte 2)

**UNIVERSIDADE FEDERAL DE MATO GROSSO DO SUL (UFMS)**
**FACULDADE DE COMPUTAÇÃO (FACOM)**
**DISCIPLINA: INTELIGÊNCIA ARTIFICIAL (2026)**
**PROFESSOR: EDSON TAKASHI MATSUBARA**
**TRABALHO: RECONHECIMENTO FACIAL 1:N — PARTE 2**

### Autor

**Marcos Vinicius Moreira Cairo**
**RGA:** 202419040675
**E-mail:** marcos.cairo@ufms.br

### Vídeo de demonstração

**Link:** *A adicionar após a gravação do vídeo de demonstração.*

### Visão geral

O **Next Face Premium** é uma aplicação acadêmica de controle de acesso por reconhecimento facial 1:N, com interface web responsiva, API FastAPI e cliente Android. O fluxo principal é **imagem → detecção (MTCNN) → recorte → embedding → similaridade de cosseno → autorizado/desconhecido**. O sistema contempla cadastro e exclusão de pessoas, histórico, auditoria administrativa e controles de privacidade.

### Atividades desenvolvidas

| Atividade | Status | Descrição |
|---|---|---|
| A1 — Detecção facial | Concluída | Detecção com MTCNN e validação de imagens e múltiplos rostos. |
| A2 — Reconhecimento 1:N | Concluída | Embeddings de 512 dimensões, protótipos por identidade e comparação por cosseno com limiar de validação. |
| A3 — Cadastro e exclusão | Concluída | Cadastro com pelo menos três imagens faciais válidas, prevenção de duplicados e remoção. |
| A4 — Interface web | Concluída | Dashboard, reconhecimento, pessoas, histórico, segurança e configurações. |
| A5 — Cliente Android | Implementada e testada | Aplicativo Android integrado à API local via HTTPS; APK de desenvolvimento. |
| A6 — Histórico e auditoria | Concluída | Persistência local de eventos em SQLite. |
| A7 — Segurança e privacidade | Implementada | Autenticação por token, validação de entrada, limites de requisição, auditoria e verificações de privacidade. |
| A8 — Validação automatizada | Concluída | 95 testes aprovados na última execução informada. |

---

Base experimental da Parte 1, estendida na Parte 2. Pipeline: **imagem → detecção (MTCNN) → recorte → rede neural → embedding → comparação → reconhecido /desconhecido**.

Cada pessoa é uma região no espaço de embeddings; **cadastrar alguém novo não exige retreinar** (basta guardar o protótipo das fotos).
O que se investiga na Parte 1 é *qual rede e qual função de perda* produzem os embeddings que melhor separam pessoas **nunca vistas** no treino.

> **Estado atual:** código, specs, ADRs e testes prontos. **Experimentos E01 a E07 executados; modelo E07 selecionado; aplicação Next Face Premium e cliente Android implementados; 95 testes automatizados aprovados** — a tabela de resultados abaixo é preenchida automaticamente por `scripts/aggregate_results.py` a partir dos JSONs em `experiments/results/`.

## Estrutura

```
configs/                 um YAML por experimento (hipótese + hiperparâmetros + seed)
src/facerec/             splits (por identidade), metrics, losses, models, data, train, evaluation, gallery, detection
scripts/                 prepare_faces, evaluate_private, enroll, aggregate_results, gerar_certificado
app/                     Parte 2: aplicação web (FastAPI + HTTPS)
tests/                   testes das losses, métricas, splits (anti-leakage), galeria
docs/specs/              especificações e critérios de aceitação (Spec-Driven Development)
docs/decisions/          ADRs (decisões e alternativas)
experiments/results/     resultados AGREGADOS (JSON + gráficos) — sem dados individuais
data/README.md           como obter os datasets (nenhum dado é versionado)
```

## Instalação

```bash
python -m venv venv && .\venv\Scripts\Activate.ps1      # Windows: venv\Scripts\activate
pip install -r requirements.txt                      # se o pip reclamar de versões: pip install --no-deps facenet-pytorch
pip install -e .
pytest                                               # testes
```

## Dados

Veja [`data/README.md`](data/README.md): dataset **público** (LFW; CelebA opcional) baixado da fonte oficial, e dataset **privado** do grupo (consentimento, só adultos, nunca no Git).

## Parte 1 — como reproduzir os experimentos

```bash
# 1) baixar o LFW (fonte oficial) em data/raw/ e recortar os rostos
python scripts/prepare_faces.py --src data/raw/lfw_funneled --dst data/processed/lfw

# 2) rodar cada experimento (cada um grava experiments/results/<exp>.json + gráficos)
python -m facerec.train configs/e01_facenet_baseline.yaml
python -m facerec.train configs/e02_cnn_crossentropy.yaml
python -m facerec.train configs/e03_cnn_contrastive.yaml
python -m facerec.train configs/e04_cnn_triplet.yaml
python -m facerec.train configs/e05_cnn_supcon.yaml
python -m facerec.train configs/e06_facenet_partial.yaml   # ajuste a loss conforme E03–E05
python -m facerec.train configs/e07_facenet_full.yaml

# 3) atualizar a tabela abaixo
python scripts/aggregate_results.py --write

# 4) teste final, só agregado, no dataset privado (limiares vêm da validação pública)
python scripts/evaluate_private.py --run runs/e07_facenet_full --root data/private/processed
```

### Protocolo (spec 006)

- Divisão **por identidade** 70/15/15 (seed fixa): quem está no teste nunca esteve no treino. Checagem automática de identidades disjuntas e de arquivos idênticos (hash) entre partições.
- A **melhor época** e **todos os limiares** (EER, FAR 1%, FAR 0,1% e limiar de identificação) saem da **validação**; o teste só aplica esses valores.
- Métricas: AUC, EER, FAR/FRR, Accuracy, Precision, Recall, F1, matriz de confusão (pares), e — em protocolo aberto — DIR, FRR de conhecidos, falsa identificação e FAR de desconhecidos. Gráficos: distribuição de similaridade (mesma pessoa × pessoas diferentes) e FAR×FRR.
- Reprodutibilidade: seed, hiperparâmetros, versões das bibliotecas e hardware gravados em cada JSON.

### Resultados

<!-- RESULTS:START -->
| Exp. | Modelo | Estratégia | Dataset | AUC | EER | Accuracy | F1 | DIR / FAR-desc. | Melhor época |
|---|---|---|---|---|---|---|---|---|---|
| E01 | InceptionResnetV1 (pré-treinada) | sem fine-tuning + none | público | 0.989 | 0.022 | 0.979 | 0.979 | 0.950 / 0.062 | 0 |
| E02 | CNN própria (128-d) | treino do zero + ce | público | 0.834 | 0.243 | 0.758 | 0.763 | 0.086 / 0.464 | 27 |
| E03 | CNN própria (128-d) | treino do zero + contrastive | público | 0.910 | 0.167 | 0.837 | 0.840 | 0.275 / 0.348 | 30 |
| E04 | CNN própria (128-d) | treino do zero + triplet | público | 0.922 | 0.146 | 0.856 | 0.860 | 0.491 / 0.329 | 25 |
| E05 | CNN própria (128-d) | treino do zero + supcon | público | 0.935 | 0.138 | 0.865 | 0.866 | 0.514 / 0.348 | 28 |
| E06 | InceptionResnetV1 (pré-treinada) | fine-tuning parcial + triplet | público | 0.991 | 0.026 | 0.971 | 0.971 | 0.914 / 0.036 | 9 |
| E07 | InceptionResnetV1 (pré-treinada) | fine-tuning completo + triplet | público | 0.991 | 0.021 | 0.976 | 0.976 | 0.923 / 0.017 | 3 |
<!-- RESULTS:END -->

*Accuracy e F1 são de verificação de pares, no limiar de EER escolhido na validação. DIR/FAR-desc.: taxa de conhecidos aceitos e identificados corretamente / taxa de desconhecidos aceitos (protocolo aberto).*

### Análise dos resultados

O experimento **E07**, baseado em InceptionResnetV1 com
fine-tuning completo e triplet loss, foi selecionado para
a aplicação de reconhecimento facial 1:N.

Resultados do E07:

- AUC: 0.991
- EER: 0.021
- Accuracy: 0.976
- F1: 0.976
- DIR: 0.923
- FAR de desconhecidos: 0.017
- Melhor época: 3

O E07 apresentou o menor EER e a menor FAR de desconhecidos
entre os experimentos E01, E06 e E07.

O E01 apresentou DIR superior (0.950 contra 0.923).
Portanto, o E07 não foi superior em todas as métricas.

A escolha priorizou a redução de falsas aceitações,
importante em sistemas de controle de acesso.

A aplicação utiliza embeddings de 512 dimensoes e limiar
de identificação definido durante a validação.

Limitações: iluminação, pose, qualidade da câmera,
erros de detecção e possível sobreposicao de identidades
entre dados de pré-treinamento e teste.

## Parte 2 - Next Face Premium

O Next Face Premium e uma aplicação de reconhecimento facial 1:N
desenvolvida com FastAPI, HTTPS e interface web responsiva.

O modelo utilizado e o E07, baseado em InceptionResnetV1,
com embeddings de 512 dimensoes e comparacao por similaridade
de cosseno.

### Funcionalidades da interface

A interface possui seis paginas:

- Dashboard: indicadores, informações do modelo e eventos recentes.
- Reconhecimento: identificação facial utilizando a câmera.
- Pessoas: cadastro, listagem e exclusao de pessoas.
- Histórico: consulta de reconhecimentos registrados.
- Seguranca: consulta de eventos de auditoria.
- Configurações: informações e estado da aplicação.

### Instalação e execução no Windows

Na raiz do projeto, com Python 3.11 instalado:

~~~powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
~~~

Gere o certificado TLS caso ainda não exista:

~~~powershell
python scripts/gerar_certificado.py
~~~

Configure o experimento e a galeria:

~~~powershell
$env:FACEREC_RUN = "runs/e07_facenet_full"
$env:FACEREC_GALLERY = "embeddings/gallery_e07_v2.npz"
$env:PORTEIRO_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
~~~

O comando gera uma credencial aleatória para a sessão atual do PowerShell. Não publique seu valor; configure uma nova credencial forte em cada ambiente.

Inicie o servidor:

~~~powershell
python -m app.main
~~~

Acesse https://127.0.0.1:8443 no navegador.

O modelo precisa estar disponível em
`runs/e07_facenet_full/best.pt`, acompanhado de `meta.json`. **Os pesos não estão no GitHub**: para reproduzir a inferência, é necessário obter ou treinar o checkpoint correspondente. Galerias e certificados locais também não são distribuídos.

### Endpoints da API

| Metodo | Rota | Finalidade |
|---|---|---|
| GET | / | Interface web |
| GET | /status | Estado da aplicação |
| POST | /reconhecer | Reconhecimento facial |
| GET | /pessoas | Listagem administrativa |
| POST | /pessoas | Cadastro de pessoas |
| DELETE | /pessoas/{nome} | Exclusao de cadastro |
| GET | /historico | Historico de reconhecimentos |
| GET | /seguranca/auditoria | Auditoria de seguranca |

As rotas administrativas exigem o cabecalho X-Porteiro-Token.

O cadastro exige pelo menos três imagens com rostos validos.
A decisão de reconhecimento e realizada pelo servidor.

### Histórico de reconhecimentos

O sistema utiliza SQLite para armazenar eventos de reconhecimento.

A interface apresenta registros e indicadores de atividade.
Os dados locais de histórico não devem ser publicados.

### Segurança e auditoria

A aplicação inclui:

- HTTPS local.
- Autenticação administrativa por token.
- Cabeçalhos de seguranca HTTP.
- Restricoes de CORS.
- Validação de imagens recebidas.
- Limite de tamanho das requisições.
- Registro de eventos administrativos em SQLite.
- Rate limiting para requisições de reconhecimento.

O rate limiting possui configuração por variaveis de ambiente.
A ativacao e os limites efetivos dependem da configuração
do servidor.

### Aplicativo Android

O projeto inclui um aplicativo Android que utiliza o backend
FastAPI para realizar reconhecimento facial.

O APK de desenvolvimento fica em:

android/app/build/outputs/apk/debug/app-debug.apk

Durante os testes com dispositivo conectado por USB,
foi utilizado o encaminhamento da porta 8443:

~~~powershell
adb reverse tcp:8443 tcp:8443
~~~

O APK e uma versão de desenvolvimento e não representa
uma distribuição publica de producao.

### Testes automatizados

A última execução completa informada, antes da publicação inicial da Parte 2, apresentou:

~~~text
95 passed in 7.05s
~~~

A suite cobre API, autenticação, reconhecimento, cadastro,
galeria, métricas, histórico, auditoria e rate limiting.

Para executar novamente:

~~~powershell
python -m pytest tests -v --tb=short
~~~

A aprovação dos testes automatizados deve ser complementada
por verificações manuais no navegador e no Android.

## Privacidade (LGPD) — critério eliminatório

Fotos, nomes, embeddings, galeria, checkpoints e termos de consentimento **não** vão para o Git (`.gitignore`). Modelos são treinados **só com dataset público**. Dados privados são processados localmente, aparecem apenas em métricas agregadas e são apagados ao fim da disciplina. Detalhes: [`docs/specs/007-privacy-lgpd.md`](docs/specs/007-privacy-lgpd.md).

## Spec-Driven Development e uso de IA

Requisitos → especificação → critérios de aceitação → implementação → testes, em `docs/specs/` e `docs/decisions/`. O código foi desenvolvido com assistência de IA (Claude) a partir dessas especificações; o autor é responsável por compreender e explicar arquitetura, losses, treino, métricas e decisões. Nenhuma foto, embedding ou checkpoint privado foi/deve ser enviado a assistentes de IA.
