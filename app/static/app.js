
"use strict";

// ======================================================
// NEXT FACE PREMIUM - INTERFACE E INTEGRAÇÃO COM A API
// Mantém os endpoints atuais do backend.
// ======================================================

const API = {
    status: "/status",
    recognize: "/reconhecer",
    history: "/historico",
    securityAudit: "/seguranca/auditoria"
};

const state = {
    cameraActive: false,
    stream: null,
    captureTimer: null,
    requestInProgress: false,
    events: [],
    model: null,
    threshold: null,
    adminToken: "",
    people: [],
    historyRecords: [],
    historyStats: null,
    securityEvents: []
};

const $ = (id) => document.getElementById(id);

// Elementos da câmera
const video = $("video");
const canvas = $("canvas");
const cameraButton = $("camera-button");
const cameraHint = $("camera-hint");

// ======================================================
// RELÓGIO
// ======================================================

function updateClock() {
    const now = new Date();

    $("clock").textContent = now.toLocaleTimeString("pt-BR", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });
}

updateClock();
setInterval(updateClock, 1000);

// ======================================================
// NAVEGAÇÃO ENTRE TELAS
// ======================================================

const pageTitles = {
    dashboard: "Dashboard",
    recognition: "Reconhecimento facial",
    people: "Pessoas",
    history: "Histórico",
    security: "Segurança",
    settings: "Configurações"
};

function showPage(pageName) {
    const page = $("page-" + pageName);

    if (!page) return;

    document.querySelectorAll(".page").forEach((item) => {
        item.classList.remove("active");
    });

    page.classList.add("active");

    document.querySelectorAll(".nav-item").forEach((item) => {
        item.classList.toggle(
            "active",
            item.dataset.page === pageName
        );
    });

    $("page-heading").textContent = pageTitles[pageName] || "Next Face";
    $("breadcrumb-current").textContent =
        (pageTitles[pageName] || "Next Face").toUpperCase();

    $("sidebar").classList.remove("open");

    if (pageName === "history") {
        loadHistory();
    }

    if (pageName === "security") {
        loadSecurityAudit();
    }
}

document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => {
        showPage(button.dataset.page);
    });
});

document.querySelectorAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => {
        showPage(button.dataset.go);
    });
});

$("mobile-menu").addEventListener("click", () => {
    $("sidebar").classList.toggle("open");
});

// ======================================================
// STATUS DO BACKEND
// ======================================================

function setConnectionStatus(online, message = "") {
    const dots = [
        $("sidebar-status-dot"),
        $("top-status-dot"),
        $("dashboard-status-dot")
    ];

    dots.forEach((dot) => {
        dot.classList.remove("online", "offline");
        dot.classList.add(online ? "online" : "offline");
    });

    $("sidebar-status").textContent = online ? "Sistema operacional" : "Sistema offline";
    $("top-status").textContent = online ? "Servidor conectado" : "Servidor desconectado";
    $("api-status").textContent = online ? "Conectada" : "Indisponível";
    $("dashboard-status-title").textContent = online ? "Sistema operacional" : "Sem conexão com o servidor";
    $("dashboard-status-description").textContent =
        message || (online
            ? "A API respondeu à consulta de status."
            : "Não foi possível consultar a API.");

    $("dashboard-status-tag").textContent = online ? "ONLINE" : "OFFLINE";
    $("dashboard-status-tag").classList.toggle("offline", !online);

    $("last-check").textContent = new Date().toLocaleTimeString("pt-BR");
}

function readPeopleCount(data) {
    const possibleValues = [
        data.pessoas_cadastradas,
        data.people_count,
        data.pessoas,
        data.total_pessoas,
        data.gallery_size
    ];

    const value = possibleValues.find(
        (item) => typeof item === "number"
    );

    return value === undefined ? "—" : value;
}

function updateSystemInformation(data) {
    const model =
        data.experimento ??
        data.experiment ??
        data.model ??
        data.modelo ??
        "Não informado";

    const device =
        data.device ??
        data.dispositivo ??
        "Não informado";

    const threshold =
        data.limiar ??
        data.threshold ??
        data.limite ??
        null;

    const people = readPeopleCount(data);

    state.model = model;
    state.threshold = threshold;

    $("people-count").textContent = people;
    $("model-name").textContent = String(model);
    $("device-name").textContent = String(device);

    const formattedThreshold = typeof threshold === "number"
        ? threshold.toFixed(4)
        : "Não informado";

    $("threshold-value").textContent = formattedThreshold;

    $("recognition-model").textContent = String(model);
    $("recognition-threshold").textContent = formattedThreshold;

    $("settings-model").textContent = String(model);
    $("settings-device").textContent = String(device);
    $("settings-threshold").textContent = formattedThreshold;
    $("settings-people").textContent = people;
}

async function loadStatus() {
    try {
        const response = await fetch(API.status, {
            method: "GET",
            headers: { "Accept": "application/json" },
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error(`Erro HTTP ${response.status}`);
        }

        const data = await response.json();

        updateSystemInformation(data);
        setConnectionStatus(true);

        const apiStatus = $("settings-api-status");
        const lastUpdate = $("settings-last-update");

        if (apiStatus) apiStatus.textContent = "Conectado";
        if (lastUpdate) {
            lastUpdate.textContent =
                new Date().toLocaleString("pt-BR");
        }

    } catch (error) {
        console.error("Erro ao consultar status:", error);
        setConnectionStatus(false, "Verifique se o servidor FastAPI está em execução.");

        const apiStatus = $("settings-api-status");
        if (apiStatus) apiStatus.textContent = "Desconectado";
    }
}

$("refresh-status").addEventListener("click", loadStatus);
$("refresh-settings").addEventListener("click", loadStatus);

// ======================================================
// CÂMERA
// ======================================================

function waitForVideoMetadata(element) {
    if (element.readyState >= 1 && element.videoWidth > 0) {
        return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
            cleanup();
            reject(new Error("Tempo esgotado aguardando a câmera."));
        }, 10000);

        function cleanup() {
            clearTimeout(timeout);
            element.removeEventListener("loadedmetadata", onLoaded);
            element.removeEventListener("error", onError);
        }

        function onLoaded() {
            cleanup();
            resolve();
        }

        function onError() {
            cleanup();
            reject(new Error("Não foi possível inicializar o vídeo."));
        }

        element.addEventListener("loadedmetadata", onLoaded, { once: true });
        element.addEventListener("error", onError, { once: true });
    });
}

async function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("Seu navegador não disponibiliza acesso à câmera. Acesse pelo endereço HTTPS ou localhost.");
    }

    const stream = await navigator.mediaDevices.getUserMedia({
        video: {
            facingMode: "user",
            width: { ideal: 640 },
            height: { ideal: 480 }
        },
        audio: false
    });

    state.stream = stream;
    video.srcObject = stream;

    await waitForVideoMetadata(video);
    await video.play();

    state.cameraActive = true;

    $("camera-frame").classList.add("camera-on");
    $("camera-state").textContent = "ATIVA";
    $("camera-state").classList.add("active");
    $("camera-placeholder").setAttribute("aria-hidden", "true");

    cameraButton.textContent = "■ Desativar câmera";
    cameraButton.classList.remove("button-primary");
    cameraButton.classList.add("button-secondary");

    cameraHint.textContent = "Câmera ativa. O sistema está analisando imagens periodicamente.";

    state.captureTimer = setInterval(captureAndAnalyze, 800);
}

function stopCamera() {
    state.cameraActive = false;

    if (state.captureTimer) {
        clearInterval(state.captureTimer);
        state.captureTimer = null;
    }

    if (state.stream) {
        state.stream.getTracks().forEach((track) => track.stop());
        state.stream = null;
    }

    video.pause();
    video.srcObject = null;

    $("camera-frame").classList.remove("camera-on");
    $("camera-state").textContent = "DESLIGADA";
    $("camera-state").classList.remove("active");
    $("camera-placeholder").removeAttribute("aria-hidden");

    cameraButton.textContent = "◎ Ativar câmera";
    cameraButton.classList.remove("button-secondary");
    cameraButton.classList.add("button-primary");

    cameraHint.textContent = "Câmera desligada.";

    resetRecognitionDisplay();
}

cameraButton.addEventListener("click", async () => {
    if (state.cameraActive) {
        stopCamera();
        return;
    }

    cameraButton.disabled = true;
    cameraHint.textContent = "Solicitando acesso à câmera...";

    try {
        await startCamera();
    } catch (error) {
        console.error("Erro na câmera:", error);
        stopCamera();
        cameraHint.textContent = error.message || "Não foi possível acessar a câmera.";
    } finally {
        cameraButton.disabled = false;
    }
});

// ======================================================
// CAPTURA E ENVIO PARA O FASTAPI
// ======================================================

async function captureAndAnalyze() {
    if (
        !state.cameraActive ||
        state.requestInProgress ||
        Date.now() < (state.retryAfterUntil || 0) ||
        video.readyState < 2 ||
        video.videoWidth === 0 ||
        video.videoHeight === 0
    ) {
        return;
    }

    state.requestInProgress = true;

    try {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const context = canvas.getContext("2d");

        // Espelha a imagem para corresponder à visualização da câmera.
        context.save();
        context.translate(canvas.width, 0);
        context.scale(-1, 1);
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        context.restore();

        const image = canvas.toDataURL("image/jpeg", 0.82);

        const response = await fetch(API.recognize, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Facerec-Client": "web"
            },
            body: JSON.stringify({ image })
        });

        const data = await response.json().catch(() => ({}));

        if (response.status === 429) {
            const retryAfter = Number(response.headers.get("Retry-After"));
            const espera = Number.isFinite(retryAfter) && retryAfter > 0
                ? Math.ceil(retryAfter)
                : 5;

            state.retryAfterUntil = Date.now() + espera * 1000;

            if (state.cameraActive) {
                cameraHint.textContent =
                    `Servidor ocupado. Aguarde aproximadamente ${espera} segundos.`;
            }

            return;
        }

        if (!response.ok) {
            const detail = typeof data.detail === "string"
                ? data.detail
                : `Erro HTTP ${response.status}`;

            throw new Error(detail);
        }

        if (!state.cameraActive) return;

        processRecognitionResult(data);

    } catch (error) {
        console.error("Erro na análise facial:", error);

        if (state.cameraActive) {
            cameraHint.textContent = "Falha na comunicação com o servidor: " + error.message;
        }
    } finally {
        state.requestInProgress = false;
    }
}

// ======================================================
// EXIBIÇÃO DO RESULTADO
// ======================================================

function resetRecognitionDisplay() {
    $("result-state").textContent = "AGUARDANDO";
    $("result-state").className = "result-state neutral";

    $("person-name").textContent = "Aguardando captura";
    $("person-description").textContent = "Nenhuma análise realizada.";
    $("identity-avatar").textContent = "?";

    $("similarity-value").textContent = "—";
    $("similarity-bar").style.width = "0%";

    $("access-decision").classList.remove("denied");
    $("access-decision").innerHTML = `
        <span class="decision-symbol">—</span>
        <div>
            <strong>Aguardando decisão</strong>
            <span>O resultado aparecerá após a análise.</span>
        </div>
    `;
}

function processRecognitionResult(data) {
    if (data.rosto_detectado === false) {
        $("result-state").textContent = "SEM ROSTO";
        $("result-state").className = "result-state neutral";

        $("person-name").textContent = "Nenhum rosto detectado";
        $("person-description").textContent =
            data.mensagem || "Posicione o rosto diante da câmera.";

        $("identity-avatar").textContent = "?";
        $("similarity-value").textContent = "—";
        $("similarity-bar").style.width = "0%";

        $("access-decision").classList.remove("denied");
        $("access-decision").innerHTML = `
            <span class="decision-symbol">◎</span>
            <div>
                <strong>Aguardando rosto</strong>
                <span>O sistema continuará analisando a câmera.</span>
            </div>
        `;
        return;
    }

    const similarity = Number(data.similaridade);
    const validSimilarity = Number.isFinite(similarity);

    const name = data.nome || "Desconhecido";
    const authorized = data.liberado === true;

    $("person-name").textContent = name;
    $("person-description").textContent = authorized
        ? "Identificação aceita pelo sistema."
        : "Identidade não autorizada ou não identificada.";

    $("identity-avatar").textContent =
        name !== "Desconhecido" ? name.trim().charAt(0).toUpperCase() : "?";

    $("result-state").textContent = authorized ? "AUTORIZADO" : "NEGADO";
    $("result-state").className =
        "result-state " + (authorized ? "authorized" : "denied");

    if (validSimilarity) {
        $("similarity-value").textContent = similarity.toFixed(4);

        // A barra é apenas uma representação visual da escala.
        // Não representa probabilidade de identidade.
        const visualValue = Math.max(0, Math.min(1, similarity)) * 100;
        $("similarity-bar").style.width = visualValue + "%";
    } else {
        $("similarity-value").textContent = "Não informado";
        $("similarity-bar").style.width = "0%";
    }

    $("access-decision").classList.toggle("denied", !authorized);
    $("access-decision").innerHTML = authorized
        ? `
            <span class="decision-symbol">✓</span>
            <div>
                <strong>Acesso autorizado</strong>
                <span>O sistema reconheceu uma pessoa cadastrada.</span>
            </div>
        `
        : `
            <span class="decision-symbol">×</span>
            <div>
                <strong>Acesso não autorizado</strong>
                <span>O sistema não liberou o acesso.</span>
            </div>
        `;

    addEvent({
        name,
        authorized,
        similarity: validSimilarity ? similarity : null,
        time: new Date()
    });
}

// ======================================================
// HISTÓRICO TEMPORÁRIO DA INTERFACE
// ======================================================

function updateDashboardCounters() {
    const stats = state.historyStats;

    if (!state.adminToken || !stats) {
        $("recognitions-count").textContent = "—";
        $("authorized-count").textContent = "—";
        $("denied-count").textContent = "—";
        return;
    }

    $("recognitions-count").textContent = stats.total_registros;
    $("authorized-count").textContent = stats.total_liberados;
    $("denied-count").textContent = stats.total_negados;
}

function addEvent(event) {
    const previous = state.events[0];

    // Evita registrar repetidamente o mesmo resultado em quadros consecutivos.
    if (
        previous &&
        previous.name === event.name &&
        previous.authorized === event.authorized &&
        Date.now() - previous.time.getTime() < 5000
    ) {
        return;
    }

    state.events.unshift(event);
    state.events = state.events.slice(0, 30);

    renderEvents();
    updateDashboardCounters();

    if (state.adminToken) {
        loadHistoryStats();
    }
}

function renderEvents() {
    const container = $("recent-events");

    if (!container) return;

    container.innerHTML = "";

    if (state.events.length === 0) {
        container.innerHTML =
            '<div class="empty-state">Nenhuma identificação registrada nesta sessão.</div>';
        return;
    }

    state.events.forEach((event) => {
        const item = document.createElement("div");
        item.className = "event-item";

        const symbol = document.createElement("div");
        symbol.className =
            "event-symbol" + (event.authorized ? "" : " denied");
        symbol.textContent = event.authorized ? "✓" : "×";

        const main = document.createElement("div");
        main.className = "event-main";

        const name = document.createElement("strong");
        name.textContent = event.name;

        const detail = document.createElement("span");
        detail.textContent = event.authorized
            ? "Acesso autorizado"
            : "Acesso não autorizado";

        main.append(name, detail);

        const time = document.createElement("span");
        time.className = "event-time";
        time.textContent = event.time.toLocaleTimeString("pt-BR");

        item.append(symbol, main, time);
        container.appendChild(item);
    });
}

$("clear-events").addEventListener("click", () => {
    state.events = [];
    renderEvents();
    updateDashboardCounters();
});


// ======================================================
// GERENCIAMENTO DE PESSOAS
// ======================================================

function showPeopleFeedback(message, type = "info") {
    const feedback = $("people-feedback");

    feedback.hidden = false;
    feedback.textContent = message;
    feedback.className = "people-feedback " + type;
}

function setAdminStatus(message, connected = false) {
    $("admin-token-status").textContent = message;

    $("admin-token-status").classList.toggle(
        "admin-connected",
        connected
    );
}

async function adminRequest(url, options = {}) {
    if (!state.adminToken) {
        throw new Error("Informe o token administrativo.");
    }

    const headers = {
        ...(options.headers || {}),
        "X-Porteiro-Token": state.adminToken
    };

    const response = await fetch(url, {
        ...options,
        headers
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        const message =
            typeof data.detail === "string"
                ? data.detail
                : "Não foi possível concluir a operação.";

        throw new Error(message);
    }

    return data;
}


function renderHistory() {
    const container = $("history-events");

    if (!container) return;

    container.innerHTML = "";

    if (!state.adminToken) {
        container.innerHTML =
            '<div class="empty-state">Conecte-se como administrador para consultar o histórico.</div>';
        return;
    }

    if (state.historyRecords.length === 0) {
        container.innerHTML =
            '<div class="empty-state">Nenhum registro persistente encontrado.</div>';
        return;
    }

    state.historyRecords.forEach((record) => {
        const item = document.createElement("div");
        item.className = "event-item";

        const authorized = Boolean(record.liberado);

        const symbol = document.createElement("div");
        symbol.className = "event-symbol" + (authorized ? "" : " denied");
        symbol.textContent = authorized ? "✓" : "×";

        const main = document.createElement("div");
        main.className = "event-main";

        const name = document.createElement("strong");
        name.textContent = record.nome || "Desconhecido";

        const detail = document.createElement("span");
        const similarity = Number(record.similaridade);
        const similarityText = Number.isFinite(similarity)
            ? ` · Similaridade: ${(similarity * 100).toFixed(2)}%`
            : "";

        detail.textContent =
            (authorized ? "Acesso autorizado" : "Acesso não autorizado") +
            similarityText;

        main.append(name, detail);

        const time = document.createElement("span");
        time.className = "event-time";

        const date = new Date(record.data_hora);
        time.textContent = Number.isNaN(date.getTime())
            ? "Data indisponível"
            : date.toLocaleString("pt-BR");

        item.append(symbol, main, time);
        container.appendChild(item);
    });
}

async function loadHistoryStats() {
    if (!state.adminToken) {
        state.historyStats = null;
        updateDashboardCounters();
        return;
    }

    try {
        const data = await adminRequest(API.history + "?limit=1");
        state.historyStats = data.estatisticas || null;
        updateDashboardCounters();
    } catch (error) {
        console.error("Erro ao atualizar estatísticas do histórico:", error);
    }
}


async function loadHistory() {
    const container = $("history-events");

    if (!container) return;

    if (!state.adminToken) {
        state.historyRecords = [];
        renderHistory();
        return;
    }

    container.innerHTML =
        '<div class="empty-state">Carregando histórico...</div>';

    try {
        const data = await adminRequest(API.history);

        state.historyRecords = Array.isArray(data.registros)
            ? data.registros
            : [];

        state.historyStats = data.estatisticas || null;
        updateDashboardCounters();
        renderHistory();
    } catch (error) {
        state.historyRecords = [];
        state.historyStats = null;
        updateDashboardCounters();
        container.innerHTML = "";

        const message = document.createElement("div");
        message.className = "empty-state";
        message.textContent =
            "Não foi possível carregar o histórico: " + error.message;

        container.appendChild(message);
    }
}

async function loadPeople() {
    const container = $("people-list");

    if (!state.adminToken) {
        container.innerHTML =
            '<div class="empty-state">Conecte-se como administrador para visualizar a galeria.</div>';
        return;
    }

    container.innerHTML =
        '<div class="empty-state">Carregando pessoas...</div>';

    try {
        const data = await adminRequest("/pessoas");

        state.people = Array.isArray(data.pessoas)
            ? data.pessoas
            : [];

        renderPeople();

        $("people-total").textContent =
            data.total ?? state.people.length;

        setAdminStatus("Administrador conectado. Galeria carregada.", true);

    } catch (error) {
        state.people = [];
        $("people-total").textContent = "—";

        container.innerHTML =
            '<div class="empty-state">Não foi possível carregar a galeria.</div>';

        setAdminStatus(error.message);

        if (
            error.message.toLowerCase().includes("token") ||
            error.message.toLowerCase().includes("administra")
        ) {
            state.adminToken = "";
        }
    }
}

function renderPeople() {
    const container = $("people-list");
    const search = $("people-search").value.trim().toLowerCase();

    const filtered = state.people.filter((person) =>
        person.nome.toLowerCase().includes(search)
    );

    container.innerHTML = "";

    if (filtered.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = state.people.length === 0
            ? "Nenhuma pessoa cadastrada na galeria."
            : "Nenhuma pessoa encontrada.";
        container.appendChild(empty);
        return;
    }

    filtered.forEach((person) => {
        const item = document.createElement("div");
        item.className = "person-item";

        const avatar = document.createElement("div");
        avatar.className = "person-avatar";
        avatar.textContent = person.nome.trim().charAt(0).toUpperCase();

        const details = document.createElement("div");
        details.className = "person-details";

        const name = document.createElement("strong");
        name.textContent = person.nome;

        const photos = document.createElement("span");
        photos.textContent = `${person.imagens} imagens cadastradas`;

        details.append(name, photos);

        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "person-delete";
        removeButton.textContent = "Excluir";
        removeButton.addEventListener("click", () => {
            deletePerson(person.nome);
        });

        item.append(avatar, details, removeButton);
        container.appendChild(item);
    });
}

function connectAdmin() {
    const token = $("admin-token").value.trim();

    if (!token) {
        setAdminStatus("Informe o token administrativo.");
        return;
    }

    state.adminToken = token;
    loadPeople();
    loadHistory();
}

function disconnectAdmin() {
    resetSecurityAudit();
    state.adminToken = "";
    state.people = [];
    state.historyRecords = [];
    state.historyStats = null;

    $("admin-token").value = "";
    $("people-total").textContent = "—";

    renderPeople();
    renderHistory();
    updateDashboardCounters();
    setAdminStatus("Administrador desconectado.");
}


const MAX_IMAGE_SIZE = 2 * 1024 * 1024; // 2 MB por imagem
const MAX_TOTAL_IMAGES_SIZE = 20 * 1024 * 1024; // 20 MB por cadastro

const ALLOWED_IMAGE_TYPES = new Set([
    "image/jpeg",
    "image/png",
    "image/webp"
]);

function validateImageFiles(files) {
    let totalSize = 0;

    for (const file of files) {
        if (!ALLOWED_IMAGE_TYPES.has(file.type)) {
            return `Formato não permitido: ${file.name}. Utilize JPEG, PNG ou WEBP.`;
        }

        if (file.size === 0) {
            return `O arquivo ${file.name} está vazio.`;
        }

        if (file.size > MAX_IMAGE_SIZE) {
            return `A imagem ${file.name} ultrapassa o limite de 2 MB.`;
        }

        totalSize += file.size;
    }

    if (totalSize > MAX_TOTAL_IMAGES_SIZE) {
        return "O tamanho total das fotografias ultrapassa 20 MB.";
    }

    return null;
}

async function fileToDataURL(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();

        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(
            new Error(`Não foi possível ler o arquivo ${file.name}.`)
        );

        reader.readAsDataURL(file);
    });
}

async function registerPerson(event) {
    event.preventDefault();

    if (!state.adminToken) {
        showPeopleFeedback(
            "Conecte-se como administrador antes de cadastrar.",
            "error"
        );
        return;
    }

    const name = $("person-name-input").value.trim();
    const files = Array.from($("person-images-input").files);

    if (!name) {
        showPeopleFeedback("Informe o nome da pessoa.", "error");
        return;
    }

    if (files.length < 3) {
        showPeopleFeedback(
            "Selecione pelo menos 3 fotografias.",
            "error"
        );
        return;
    }

    if (files.length > 10) {
        showPeopleFeedback(
            "Selecione no máximo 10 fotografias por cadastro.",
            "error"
        );
        return;
    }


    const validationError = validateImageFiles(files);

    if (validationError) {
        showPeopleFeedback(validationError, "error");
        return;
    }


    const existing = state.people.find(
        (person) => person.nome.toLowerCase() === name.toLowerCase()
    );

    if (
        existing &&
        !confirm(
            `A pessoa "${existing.nome}" já está cadastrada.\n\n` +
            "O cadastro anterior será substituído pelas novas imagens. Deseja continuar?"
        )
    ) {
        return;
    }

    const button = $("register-person-button");
    button.disabled = true;
    button.textContent = "Processando imagens...";

    try {
        const images = await Promise.all(
            files.map(fileToDataURL)
        );

        button.textContent = "Cadastrando...";

        const result = await adminRequest("/pessoas", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                nome: name,
                imagens: images
            })
        });

        showPeopleFeedback(
            `${result.mensagem} ` +
            `${result.cadastradas} imagens aceitas e ` +
            `${result.rejeitadas} rejeitadas.`,
            "success"
        );

        $("people-form").reset();
        $("selected-images-info").textContent =
            "Nenhuma imagem selecionada.";

        await loadPeople();
        await loadStatus();

    } catch (error) {
        showPeopleFeedback(error.message, "error");
    } finally {
        button.disabled = false;
        button.textContent = "Cadastrar pessoa";
    }
}

async function deletePerson(name) {
    if (!confirm(
        `Tem certeza de que deseja excluir "${name}" da galeria facial?`
    )) {
        return;
    }

    try {
        await adminRequest(
            `/pessoas/${encodeURIComponent(name)}`,
            { method: "DELETE" }
        );

        showPeopleFeedback(
            `Cadastro de "${name}" removido com sucesso.`,
            "success"
        );

        await loadPeople();
        await loadStatus();

    } catch (error) {
        showPeopleFeedback(error.message, "error");
    }
}


// ======================================================
// INICIALIZAÇÃO
// ======================================================

renderEvents();
updateDashboardCounters();
loadStatus();
// Eventos do gerenciamento de pessoas.
$("save-admin-token").addEventListener("click", connectAdmin);

$("admin-token").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        connectAdmin();
    }
});

$("disconnect-admin").addEventListener("click", disconnectAdmin);

$("refresh-people").addEventListener("click", loadPeople);

$("people-search").addEventListener("input", renderPeople);

$("people-form").addEventListener("submit", registerPerson);


$("person-images-input").addEventListener("change", () => {
    const files = Array.from($("person-images-input").files);
    const count = files.length;

    $("selected-images-info").textContent = count === 0
        ? "Nenhuma imagem selecionada."
        : `${count} imagem(ns) selecionada(s).`;

    if (count === 0) return;

    const validationError = validateImageFiles(files);

    if (validationError) {
        showPeopleFeedback(validationError, "error");
    }
});


// Atualiza o status periodicamente.
setInterval(loadStatus, 15000);

// Se a página for fechada ou recarregada, libera a câmera.
window.addEventListener("beforeunload", () => {
    if (state.stream) {
        state.stream.getTracks().forEach((track) => track.stop());
    }
});



// ======================================================
// CENTRAL DE SEGURANCA - AUDITORIA ADMINISTRATIVA
// ======================================================

let securityRequestVersion = 0;

const SECURITY_EVENT_LABELS = {
    admin_login_success: "Autenticação administrativa",
    admin_login_failure: "Token administrativo inválido",
    admin_access_denied: "Acesso administrativo negado",
    person_created: "Pessoa cadastrada",
    person_deleted: "Pessoa exclu\u00edda",
    admin_logout: "Desconex\u00e3o administrativa",
    session_expired: "Sess\u00e3o expirada",
    security_block: "Bloqueio de segurança"
};

function setSecurityStatus(message) {
    const element = $("security-status");
    if (element) element.textContent = message;
}

function updateSecurityCounters(records) {
    const count = (predicate) => records.filter(predicate).length;

    $("security-total").textContent = String(records.length);

    $("security-denied").textContent = String(
        count((event) =>
            event.tipo === "admin_login_failure" ||
            event.tipo === "admin_access_denied" ||
            event.tipo === "security_block"
        )
    );

    $("security-created").textContent = String(
        count((event) =>
            event.tipo === "person_created" &&
            event.sucesso === true
        )
    );

    $("security-deleted").textContent = String(
        count((event) =>
            event.tipo === "person_deleted" &&
            event.sucesso === true
        )
    );
}

function resetSecurityAudit() {
    securityRequestVersion += 1;
    state.securityEvents = [];

    for (const id of [
        "security-total",
        "security-denied",
        "security-created",
        "security-deleted"
    ]) {
        const element = $(id);
        if (element) element.textContent = "\u2014";
    }

    const container = $("security-events");

    if (container) {
        container.replaceChildren();

        const message = document.createElement("div");
        message.className = "empty-state";
        message.textContent =
            "Conecte-se como administrador para consultar a auditoria.";

        container.appendChild(message);
    }

    setSecurityStatus("Aguardando autenticação administrativa.");
}

function renderSecurityAudit() {
    const container = $("security-events");
    if (!container) return;

    container.replaceChildren();

    const records = state.securityEvents;
    updateSecurityCounters(records);

    if (records.length === 0) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "Nenhum evento de auditoria encontrado.";
        container.appendChild(empty);
        return;
    }

    records.forEach((event) => {
        const success = event.sucesso === true;

        const item = document.createElement("div");
        item.className = "event-item security-event-item";

        const symbol = document.createElement("div");
        symbol.className =
            "event-symbol" + (success ? "" : " denied");
        symbol.textContent = success ? "\u2713" : "\u00d7";

        const content = document.createElement("div");
        content.className = "event-main";

        const title = document.createElement("strong");
        title.textContent =
            SECURITY_EVENT_LABELS[event.tipo] ||
            "Evento administrativo";

        const detail = document.createElement("span");
        detail.textContent = success
            ? "Opera\u00e7\u00e3o conclu\u00edda"
            : "Opera\u00e7\u00e3o negada ou n\u00e3o conclu\u00edda";

        content.append(title, detail);

        const time = document.createElement("span");
        time.className = "event-time";

        const date = new Date(event.data_hora);
        time.textContent = Number.isNaN(date.getTime())
            ? "Data indispon?vel"
            : date.toLocaleString("pt-BR");

        item.append(symbol, content, time);
        container.appendChild(item);
    });
}

async function loadSecurityAudit() {
    const container = $("security-events");
    if (!container) return;

    const requestVersion = ++securityRequestVersion;
    const tokenAtStart = state.adminToken;

    if (!tokenAtStart) {
        resetSecurityAudit();
        return;
    }

    setSecurityStatus("Consultando eventos de segurança...");

    try {
        const data = await adminRequest(
            API.securityAudit + "?limit=200"
        );

        // Ignora respostas antigas ou recebidas apos desconexao.
        if (
            requestVersion !== securityRequestVersion ||
            state.adminToken !== tokenAtStart
        ) {
            return;
        }

        state.securityEvents = Array.isArray(data.eventos)
            ? data.eventos
            : [];

        renderSecurityAudit();

        setSecurityStatus(
            "Auditoria atualizada. Exibindo " +
            state.securityEvents.length +
            " registro(s) consultado(s)."
        );
    } catch (error) {
        if (
            requestVersion !== securityRequestVersion ||
            state.adminToken !== tokenAtStart
        ) {
            return;
        }

        state.securityEvents = [];
        updateSecurityCounters([]);

        container.replaceChildren();

        const message = document.createElement("div");
        message.className = "empty-state";
        message.textContent =
            "N\u00e3o foi poss\u00edvel carregar a auditoria: " +
            error.message;

        container.appendChild(message);
        setSecurityStatus("Falha ao consultar a auditoria.");
    }
}

$("refresh-security").addEventListener(
    "click",
    loadSecurityAudit
);
