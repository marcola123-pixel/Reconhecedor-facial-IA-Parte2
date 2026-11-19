# Cliente Android da portaria (projeto de portfólio — fora do escopo da disciplina)

App Android (Kotlin) que usa a câmera frontal, envia ~1 quadro por segundo ao seu servidor (`POST /reconhecer`) e mostra **liberado / negado**.
Toda a IA continua no servidor (`python app/main.py`); o celular é só o cliente. **Esta é a Fase 1** — a inferência no próprio aparelho (TFLite) seria a Fase 2.

> Estes arquivos **não foram compilados nem executados** por quem os escreveu (sem Android SDK no ambiente). Espere pequenos ajustes de versão; cole os erros do Gradle/Logcat para corrigir.

## Privacidade (leia antes)
- O termo de consentimento da disciplina vale **só para o trabalho acadêmico** (item 26 do enunciado). Para o app, cadastre **só você** ou pessoas que autorizem expressamente este novo uso.
- Use uma **galeria separada** da do trabalho: `FACEREC_GALLERY=embeddings/mobile_gallery.npz`.
- O app não grava quadros, não usa analytics e não escreve nomes no log; `allowBackup="false"` impede cópia dos dados do app.
- Sem detecção de vivacidade: uma foto exibida em outro celular pode ser aceita.

## 1. Criar o projeto
Android Studio → *New Project* → **Empty Views Activity** · Language **Kotlin** · Package name **`br.ufms.portaria`** · Minimum SDK 24 ou superior.
(Se usar outro pacote, troque a linha `package` dos `.kt` e adicione `import <seu.pacote>.R` no `MainActivity.kt`.)

## 2. Copiar os arquivos desta pasta
| Origem (`android/app/src/...`) | Destino no projeto |
|---|---|
| `main/java/br/ufms/portaria/Config.kt`, `PortariaApi.kt`, `MainActivity.kt` | `app/src/main/java/br/ufms/portaria/` (substitui o `MainActivity.kt`) |
| `main/res/layout/activity_main.xml` | `app/src/main/res/layout/` (substitui) |
| `main/res/xml/network_security_config.xml` | `app/src/main/res/xml/` (crie a pasta `xml`) |
| `test/java/br/ufms/portaria/PortariaApiTest.kt` | `app/src/test/java/br/ufms/portaria/` (opcional) |

## 3. Dependências — `app/build.gradle.kts`, dentro de `dependencies { ... }`
```kotlin
val cameraxVersion = "1.3.4"
implementation("androidx.camera:camera-core:$cameraxVersion")
implementation("androidx.camera:camera-camera2:$cameraxVersion")
implementation("androidx.camera:camera-lifecycle:$cameraxVersion")
implementation("androidx.camera:camera-view:$cameraxVersion")
implementation("com.squareup.okhttp3:okhttp:4.12.0")
testImplementation("org.json:json:20240303")   // só para o teste unitário
```
Depois *Sync Now*. (Se o Studio sugerir versões mais novas, aceite.)

## 4. `AndroidManifest.xml`
- Antes de `<application>`:
  ```xml
  <uses-permission android:name="android.permission.CAMERA" />
  <uses-permission android:name="android.permission.INTERNET" />
  ```
- Em `<application ...>`: `android:allowBackup="false"` e `android:networkSecurityConfig="@xml/network_security_config"`.
- Em `<activity ...>`: `android:screenOrientation="portrait"`.

## 5. Confiar no certificado do seu servidor
O servidor usa um certificado autoassinado. Copie **só o certificado público** (nunca a `key.pem`):
```powershell
New-Item -ItemType Directory <PROJETO_ANDROID>\app\src\main\res\raw -Force
Copy-Item certs\cert.pem <PROJETO_ANDROID>\app\src\main\res\raw\server_cert.pem
```
Se você gerar o certificado de novo, copie de novo e recompile. O `.gitignore` já ignora `*.pem`.

## 6. Preparar o POCO C75
1. *Configurações → Sobre o telefone* → toque 7 vezes na versão do sistema (HyperOS/MIUI) para liberar o modo desenvolvedor.
2. *Configurações adicionais → Opções do desenvolvedor* → ligue **Depuração USB** (em Xiaomi/POCO também pode ser preciso ligar "Instalar via USB", o que às vezes pede login na conta Mi).
3. Conecte o cabo USB e aceite o aviso de "Permitir depuração USB deste computador".

## 7. Rodar
Terminal 1 (PC) — servidor com o modelo escolhido e uma galeria só para o app:
```powershell
$env:FACEREC_RUN = "runs/e07_facenet_full"
$env:FACEREC_GALLERY = "embeddings/mobile_gallery.npz"
$env:PORTEIRO_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
python app\main.py
```
Terminal 2 — ponte USB (o `localhost:8443` do celular passa a apontar para o PC; o servidor continua só em `127.0.0.1`):
```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb devices                          # o POCO deve aparecer como "device" (não "unauthorized")
& $adb reverse tcp:8443 tcp:8443        # refaça se reconectar o cabo
```
No Android Studio: escolha o POCO na lista de dispositivos e clique em ▶ *Run*.

## 8. Como saber que funcionou
1. O app pede a câmera e mostra "Aguardando".
2. Com a galeria vazia e seu rosto no quadro: **"Acesso negado · Nenhuma pessoa cadastrada"** (prova que celular → servidor → modelo funciona).
3. No PC, abra `https://localhost:8443`, cadastre-se (token + 3 fotos) e volte ao celular: **"Acesso liberado"**.
   Dica: cadastrar pela webcam do PC e reconhecer pela câmera do celular pode reduzir a similaridade; se necessário, recadastre.

## Problemas comuns
| Sintoma | Provável causa |
|---|---|
| "Sem conexão (...)" no app | servidor desligado, ou faltou `adb reverse` (ele se perde ao reconectar o cabo) |
| `SSLHandshakeException` / "Trust anchor" | `server_cert.pem` ausente, desatualizado ou o `res/xml` não está no manifest |
| `adb devices` mostra `unauthorized` | aceite o aviso de depuração no celular |
| "Nenhum rosto" sempre | rosto pequeno ou luz fraca; teste o servidor antes pela página web |
| Erro de compilação em `toBitmap()` | versão antiga do CameraX: use 1.3.x ou superior |

## Próximos passos
- **1b:** telas de cadastro e exclusão no app (`POST /pessoas`, `DELETE /pessoas/{nome}` com o token em armazenamento criptografado).
- **2:** inferência no aparelho — exige um modelo leve convertido (ONNX/TFLite), teste de paridade dos embeddings, nova calibração do limiar e galeria criptografada (Android Keystore).
