# Next Face Premium — Reconhecimento Facial 1:N (Parte 2)

**UNIVERSIDADE FEDERAL DE MATO GROSSO DO SUL (UFMS)**
**FACULDADE DE COMPUTAÇÃO (FACOM)**
**DISCIPLINA: INTELIGÊNCIA ARTIFICIAL (2026)**
**PROFESSOR: EDSON TAKASHI MATSUBARA**
**TRABALHO: RECONHECIMENTO FACIAL 1:N — PARTE 2**

## Autor

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
| A8 — Validação automatizada | Concluída | 155 testes aprovados na última execução documentada. |

---

A Parte 1 investigou modelos e funções de perda para separar identidades não vistas durante o treinamento; a Parte 2 aplica o experimento E07 em um sistema de controle de acesso. Novas pessoas podem ser cadastradas sem retreinar o modelo.

A tabela experimental é atualizada por `scripts/aggregate_results.py` a partir dos JSONs em `experiments/results/`.

## Estrutura

```text
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

O E07 apresentou o menor EER e a menor FAR de desconhecidos
entre os experimentos E01, E06 e E07.

O E01 apresentou DIR superior (0.950 contra 0.923).
Portanto, o E07 não foi superior em todas as métricas.

A escolha priorizou a redução de falsas aceitações,
importante em sistemas de controle de acesso.

A aplicação utiliza embeddings de 512 dimensões e limiar
de identificação definido durante a validação.

Limitações: iluminação, pose, qualidade da câmera,
erros de detecção e possível sobreposição de identidades
entre dados de pré-treinamento e teste.

## Parte 2 — Next Face Premium

O backend FastAPI disponibiliza reconhecimento facial 1:N por HTTPS para as interfaces web e Android.

### Funcionalidades da interface

A interface possui seis páginas:

- Dashboard: indicadores, informações do modelo e eventos recentes.
- Reconhecimento: identificação facial utilizando a câmera.
- Pessoas: cadastro, listagem e exclusão de pessoas.
- Histórico: consulta de reconhecimentos registrados.
- Segurança: consulta de eventos de auditoria.
- Configurações: informações e estado da aplicação.

### Instalação e execução no Windows (web e API)

Na raiz do projeto, com Python 3.11 instalado:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
```

Gere o certificado TLS caso ainda não exista:

```powershell
python scripts/gerar_certificado.py
```

Configure o experimento e a galeria:

```powershell
$env:FACEREC_RUN = "runs/e07_facenet_full"
$env:FACEREC_GALLERY = "embeddings/gallery_demo.npz"
$env:PORTEIRO_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
```

O comando gera uma credencial aleatória para a sessão atual do PowerShell. Não publique seu valor; configure uma nova credencial forte em cada ambiente.

Inicie o servidor:

```powershell
python -m app.main
```

Acesse a interface em `https://127.0.0.1:8443` no navegador.

#### Inicialização com galeria vazia

Com `FACEREC_GALLERY` definido como `embeddings/gallery_demo.npz`, se esse arquivo ainda não existir, a aplicação inicia sem pessoas cadastradas. Para verificar, execute em outro terminal:

```powershell
curl.exe -k https://127.0.0.1:8443/status
```

O endpoint deverá informar `"pessoas_cadastradas": 0` para a galeria vazia. Os cadastros posteriores são persistidos localmente, sem necessidade de retreinar o modelo. O parâmetro `-k` ignora a validação do certificado e deve ser usado somente em testes locais com certificado autoassinado.

O modelo precisa estar disponível em
`runs/e07_facenet_full/best.pt`, acompanhado de `meta.json`. **Os pesos não estão no GitHub**: para reproduzir a inferência, é necessário obter ou treinar o checkpoint correspondente. Galerias e certificados locais também não são distribuídos.

### Endpoints da API

| Método | Rota | Finalidade |
|---|---|---|
| GET | / | Interface web |
| GET | /status | Estado da aplicação |
| POST | /reconhecer | Reconhecimento facial |
| GET | /pessoas | Listagem administrativa |
| POST | /pessoas | Cadastro de pessoas |
| DELETE | /pessoas/{nome} | Exclusão de cadastro |
| GET | /historico | Histórico de reconhecimentos |
| GET | /seguranca/auditoria | Auditoria de segurança |

As rotas administrativas exigem o cabeçalho X-Porteiro-Token.

O cadastro exige pelo menos três imagens com rostos válidos.
A decisão de reconhecimento é realizada pelo servidor.

### Histórico de reconhecimentos

O sistema utiliza SQLite para armazenar eventos de reconhecimento.

A interface apresenta registros e indicadores de atividade.
Os dados locais de histórico não devem ser publicados.

### Segurança e auditoria

A aplicação inclui:

- HTTPS local.
- Autenticação administrativa por token.
- Cabeçalhos de segurança HTTP.
- Restrições de CORS.
- Validação de imagens recebidas.
- Limite de tamanho das requisições.
- Registro de eventos administrativos em SQLite.
- Rate limiting para requisições de reconhecimento.

O rate limiting possui configuração por variáveis de ambiente.
A ativação e os limites efetivos dependem da configuração
do servidor.

### Aplicativo Android — Next Face Premium

Além da interface web, o projeto possui um aplicativo Android nativo,
desenvolvido em Kotlin e integrado ao backend FastAPI.

O aplicativo foi testado em um dispositivo Android físico, utilizando
a câmera para capturar imagens e enviar quadros ao servidor.

#### Arquitetura Android

```text
Câmera do smartphone
        |
        v
CameraX - captura de quadros
        |
        v
OkHttp - requisição HTTPS
        |
        v
FastAPI - POST /reconhecer
        |
        v
MTCNN - detecção e recorte facial
        |
        v
FaceNet E07 - embedding de 512 dimensões
        |
        v
Similaridade de cosseno + threshold
        |
        v
Reconhecido / desconhecido
        |
        v
Resultado apresentado no Android
```

O reconhecimento facial é processado pelo servidor, e não
diretamente pelo dispositivo móvel.

#### Tecnologias

| Tecnologia | Finalidade |
|---|---|
| Kotlin | Desenvolvimento do aplicativo Android |
| CameraX | Captura de imagens da câmera |
| OkHttp | Comunicação com a API FastAPI |
| HTTPS | Comunicação criptografada |
| FastAPI | Backend de reconhecimento |
| MTCNN | Detecção e recorte facial |
| FaceNet E07 | Extração de embeddings de 512 dimensões |

#### Configuração do aplicativo

O código-fonte Android está no diretório `android/`.

A configuração de comunicação está em:

`android/app/src/main/java/br/ufms/portaria/Config.kt`

```kotlin
const val SERVER_URL = "https://localhost:8443"
const val INTERVALO_MS = 800L
```

O intervalo de 800 ms define a frequência de envio dos quadros
para reconhecimento.

#### Execução com dispositivo físico

1. Iniciar o backend FastAPI com o modelo E07 disponível.
2. Conectar o smartphone ao computador por USB.
3. Habilitar a depuração USB no Android.
4. Confirmar que o dispositivo aparece no ADB.
5. Configurar o encaminhamento da porta HTTPS.

```powershell
adb devices
adb reverse tcp:8443 tcp:8443
```

Com o encaminhamento ativo, o endereço `https://localhost:8443`
utilizado pelo aplicativo aponta para o servidor executado
no computador.

A configuração de desenvolvimento utiliza certificado TLS local,
incluído na configuração de confiança do aplicativo Android.
Caso o certificado do servidor seja substituído, a configuração
do aplicativo deverá ser atualizada e o APK recompilado.

#### Compilação e APK

O projeto Android pode ser aberto no Android Studio.

Para gerar um APK de desenvolvimento, utilize a tarefa Gradle
`assembleDebug`, pelo Android Studio ou pelo Gradle Wrapper
do projeto.

O APK gerado fica em:

`android/app/build/outputs/apk/debug/app-debug.apk`

O APK é um artefato de desenvolvimento e não representa uma
distribuição pública de produção.

#### Validação do Android

A aplicação foi testada em um smartphone físico, com captura
de imagens pela câmera, comunicação com a API local e
reconhecimento facial funcional.

O aplicativo demonstra a reutilização do mesmo backend
de Inteligência Artificial por interfaces web e mobile.

#### Limitações do Android

- O aplicativo requer conexão com o backend FastAPI; não executa a inferência no dispositivo.
- A configuração testada utiliza USB e encaminhamento de porta ADB.
- O certificado TLS é destinado ao ambiente local de desenvolvimento.
- O APK não foi preparado para distribuição pública em produção.

### Testes automatizados

A última execução completa informada, antes da publicação inicial da Parte 2, apresentou:

```text
155 passed in 6.86s
```

A suite cobre API, autenticação, reconhecimento, cadastro,
galeria, métricas, histórico, auditoria e rate limiting.

Para executar novamente:

```powershell
python -m pytest tests -v --tb=short
```

A aprovação dos testes automatizados deve ser complementada
por verificações manuais no navegador e no Android.


### Validação funcional manual

A aplicação web foi testada localmente com o modelo
`e07_facenet_full`, inicialmente com zero pessoas cadastradas.

Foram verificados:

1. Autenticação administrativa com token.
2. Cadastro com três imagens faciais válidas.
3. Reconhecimento autorizado de pessoa cadastrada.
4. Tratamento de imagem sem rosto.
5. Exclusão do cadastro pela interface.
6. Retorno do dashboard a zero pessoas cadastradas.

A câmera do navegador também foi testada com sucesso.

### Limitações de implantação

O desempenho pode variar com iluminação, pose e qualidade de captura. O ambiente demonstrado utiliza HTTPS local com certificado de desenvolvimento e não representa uma implantação de produção. A inferência requer o checkpoint E07 correspondente, não distribuído no repositório.


## Avaliação experimental do alinhamento facial — E07

### Objetivo e metodologia

Foi realizado um experimento comparativo entre duas estratégias
de pré-processamento facial:

- **Legacy:** recorte facial convencional realizado pelo MTCNN.
- **Aligned:** alinhamento geométrico baseado em cinco landmarks faciais.

As estratégias utilizaram o mesmo modelo `e07_facenet_full`,
com pesos idênticos e limiar de identificação `0.5838396380334074`.

A avaliação utilizou 140 fotografias de 40 identidades
selecionadas da partição de teste reconstruída do conjunto LFW.

Foram consideradas 20 identidades conhecidas, com três imagens
de cadastro e duas consultas por identidade, e 20 identidades
desconhecidas, com duas consultas por identidade.

O protocolo totalizou 60 imagens de cadastro e 80 consultas.
A integridade das imagens foi verificada por hashes SHA-256.

### Resultados

| Métrica | Legacy | Aligned |
|---|---:|---:|
| Detecções bem-sucedidas | 140/140 | 140/140 |
| DIR — identificação correta | 95% | 95% |
| FRR — falsa rejeição | 5% | 5% |
| FAR observado | 0% | 0% |
| Identificações corretas | 38/40 | 38/40 |
| Rejeições incorretas | 2/40 | 2/40 |
| Falsas aceitações | 0/40 | 0/40 |
| Tempo médio de detecção e pré-processamento | 35,45 ms | 35,23 ms |

Os tempos foram medidos em CPU durante uma execução.
Não incluem toda a inferência do sistema.

A diferença de aproximadamente 0,62% no tempo médio
não permite concluir superioridade de desempenho.

### Auditoria pareada

Uma segunda execução comparou individualmente as decisões
das 80 consultas.

A auditoria encontrou **zero decisões alteradas** entre
Legacy e Aligned.

As duas rejeições incorretas ocorreram nas mesmas consultas.
Nenhuma identidade desconhecida foi aceita.

Essa concordância não significa que embeddings e similaridades
sejam idênticos, nem demonstra equivalência estatística geral.

### Reprodutibilidade

Os principais componentes experimentais são:

- `src/facerec/alignment.py`
- `src/facerec/detection.py`
- `scripts/compare_alignment.py`
- `scripts/run_alignment_experiment.py`
- `scripts/audit_alignment_decisions.py`
- `tests/test_compare_alignment.py`
- `tests/test_audit_alignment_decisions.py`

Para executar os testes automatizados:

    python -m pytest -q

Para executar o experimento:

    python -u scripts/run_alignment_experiment.py

A execução requer o checkpoint E07, o conjunto de imagens
e o manifesto privado previamente preparado.

O manifesto e os resultados ficam em
`data/private/face_alignment_eval/`, diretório ignorado pelo Git.

A aplicação utiliza `legacy` por padrão. O modo `aligned`
exige uma galeria experimental isolada.

### Limitações e conclusão

A partição de teste foi reconstruída a partir da configuração
e dos arquivos atualmente disponíveis, sem um manifesto
histórico com hashes do treinamento original.

O limiar foi originalmente calibrado para Legacy.
A amostra também é limitada, e FAR observado de 0%
não garante ausência de falsas aceitações em produção.

**Conclusão:** nas condições avaliadas, o alinhamento
geométrico não apresentou melhoria nas decisões de
identificação do E07. Legacy permanece como padrão,
enquanto Aligned é mantido como alternativa experimental.

## Privacidade (LGPD) — critério eliminatório

Fotos, nomes, embeddings, galeria, checkpoints e termos de consentimento **não** vão para o Git (`.gitignore`). Modelos são treinados **só com dataset público**. Dados privados são processados localmente, aparecem apenas em métricas agregadas e são apagados ao fim da disciplina. Detalhes: [`docs/specs/007-privacy-lgpd.md`](docs/specs/007-privacy-lgpd.md).

## Spec-Driven Development e uso de IA

O desenvolvimento do projeto seguiu os princípios de **Spec-Driven Development (SDD)**, com o seguinte fluxo:

**Requisitos → Especificações → Critérios de aceitação → Implementação → Testes.**

As especificações e decisões arquiteturais estão documentadas em:

- `docs/specs/` — requisitos, especificações e critérios de aceitação.
- `docs/decisions/` — registros de decisões arquiteturais (ADRs).

O desenvolvimento contou com assistência de ferramentas de inteligência artificial, utilizadas como apoio à implementação, revisão de código, documentação e testes.

O autor permanece responsável por compreender, validar e explicar a arquitetura, as funções de perda (*losses*), o treinamento, as métricas e as decisões técnicas do projeto.

Fotografias, embeddings e checkpoints privados não devem ser compartilhados com assistentes de IA, conforme a política descrita na seção **Privacidade (LGPD)**.
