package br.ufms.portaria

object Config {
    /** Com `adb reverse tcp:8443 tcp:8443`, o localhost do celular aponta para o servidor rodando no PC. */
    const val SERVER_URL = "https://localhost:8443"
    const val INTERVALO_MS = 800L      // 1 quadro a cada 0,8 s (igual à página web)
    const val JPEG_QUALITY = 80
}
