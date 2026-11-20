package br.ufms.portaria

import okhttp3.Call
import okhttp3.Callback
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class ConfiguracoesApi {

    data class StatusServidor(
        val experimento: String,
        val limiar: Double,
        val pessoas: Int,
        val dispositivo: String
    )

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    fun carregar(
        callback: (StatusServidor?, String?) -> Unit
    ) {
        val request = Request.Builder()
            .url("${Config.SERVER_URL}/status")
            .get()
            .build()

        client.newCall(request).enqueue(object : Callback {

            override fun onFailure(call: Call, e: IOException) {
                callback(null, "Servidor indisponivel.")
            }

            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (!it.isSuccessful) {
                        callback(null, "Erro HTTP ${it.code}.")
                        return
                    }

                    try {
                        val json = JSONObject(it.body?.string().orEmpty())

                        callback(
                            StatusServidor(
                                experimento = json.getString("experimento"),
                                limiar = json.getDouble("limiar"),
                                pessoas = json.getInt("pessoas_cadastradas"),
                                dispositivo = json.getString("device")
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