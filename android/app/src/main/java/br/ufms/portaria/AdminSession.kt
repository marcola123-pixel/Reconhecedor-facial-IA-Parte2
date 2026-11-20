package br.ufms.portaria

object AdminSession {

    private var token: String? = null

    fun conectar(novoToken: String) {
        token = novoToken
    }

    fun obterToken(): String? {
        return token
    }

    fun desconectar() {
        token = null
    }

    fun estaConectado(): Boolean {
        return !token.isNullOrBlank()
    }
}
