package br.ufms.portaria

import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class CadastroPessoaApi {

    data class Resultado(
        val cadastradas: Int,
        val rejeitadas: Int,
        val pessoas: Int,
        val mensagem: String
    )

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .build()

    fun cadastrar(
        nome: String,
        imagens: List<String>,
        token: String,
        callback: (Resultado?, String?) -> Unit
    ) {
        if (nome.isBlank() || nome.length > 80) {
            callback(null, "Informe um nome valido de ate 80 caracteres.")
            return
        }

        if (imagens.size !in 3..10) {
            callback(null, "Selecione de 3 a 10 fotografias.")
            return
        }

        if (token.isBlank()) {
            callback(null, "Autenticacao administrativa necessaria.")
            return
        }

        val json = JSONObject().apply {
            put("nome", nome.trim())
            put("imagens", JSONArray(imagens))
        }

        val body = json.toString()
            .toRequestBody("application/json; charset=utf-8".toMediaType())

        val request = Request.Builder()
            .url("${Config.SERVER_URL}/pessoas")
            .header("X-Porteiro-Token", token)
            .post(body)
            .build()

        client.newCall(request).enqueue(object : Callback {

            override fun onFailure(call: Call, e: IOException) {
                callback(null, "Falha de conexao com o servidor.")
            }

            override fun onResponse(call: Call, response: Response) {
                response.use {
                    val texto = it.body?.string().orEmpty()

                    if (it.code == 401 || it.code == 403) {
                        callback(null, "Acesso administrativo negado.")
                        return
                    }

                    if (it.code == 409) {
                        callback(null, "Ja existe uma pessoa cadastrada com esse nome.")
                        return
                    }

                    if (it.code == 413) {
                        callback(null, "Fotografias muito grandes para envio.")
                        return
                    }

                    if (it.code == 422) {
                        callback(
                            null,
                            "Cadastro rejeitado. Verifique se existem pelo menos 3 rostos validos."
                        )
                        return
                    }

                    if (!it.isSuccessful) {
                        callback(null, "Erro HTTP ${it.code}.")
                        return
                    }

                    try {
                        val resposta = JSONObject(texto)

                        callback(
                            Resultado(
                                cadastradas = resposta.optInt("cadastradas"),
                                rejeitadas = resposta.optInt("rejeitadas"),
                                pessoas = resposta.optInt("pessoas"),
                                mensagem = resposta.optString(
                                    "mensagem",
                                    "Cadastro realizado."
                                )
                            ),
                            null
                        )
                    } catch (e: Exception) {
                        callback(null, "Resposta invalida do servidor.")
                    }
                }
            }
        })
    }
}
