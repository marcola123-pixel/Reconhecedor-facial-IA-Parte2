package br.ufms.portaria

import android.util.Base64
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Resposta do POST /reconhecer já interpretada. A decisão liberado/negado vem do SERVIDOR. */
sealed class Resultado {
    object SemRosto : Resultado()
    data class Liberado(val nome: String, val similaridade: Double?) : Resultado()
    data class Negado(val motivo: String?, val similaridade: Double?) : Resultado()
    data class LimiteAtingido(val esperaSegundos: Long) : Resultado()
    data class Erro(val mensagem: String) : Resultado()
}

class PortariaApi(private val baseUrl: String = Config.SERVER_URL) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    fun reconhecer(jpeg: ByteArray, callback: (Resultado) -> Unit) {
        val dataUrl = "data:image/jpeg;base64," + Base64.encodeToString(jpeg, Base64.NO_WRAP)
        val json = JSONObject().put("image", dataUrl).toString()
        val request = Request.Builder()
            .url("$baseUrl/reconhecer")
            .header("X-Facerec-Client", "android")
            .post(json.toRequestBody("application/json".toMediaType()))
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback(Resultado.Erro("Sem conexão com o servidor (${e.javaClass.simpleName})"))
            }

            override fun onResponse(call: Call, response: Response) {
                response.use {
                    val espera = it.header("Retry-After")
                        ?.toLongOrNull()
                        ?.coerceIn(1L, 60L)
                        ?: 5L

                    callback(
                        if (it.code == 429) {
                            Resultado.LimiteAtingido(espera)
                        } else {
                            interpretar(it.code, it.body?.string().orEmpty())
                        }
                    )
                }
            }
        })
    }

    companion object {
        /** Pura (sem rede): fácil de testar. */
        fun interpretar(status: Int, corpo: String): Resultado = try {
            val j = JSONObject(corpo)
            when {
                status == 429 -> Resultado.Erro(
                    "Muitas solicitações. Aguarde alguns segundos."
                )
                status !in 200..299 -> {
                    val detalhe = j.optString(
                        "detail",
                        j.optString("erro", "Erro $status")
                    )
                    Resultado.Erro(detalhe)
                }
                !j.optBoolean("rosto_detectado", false) -> Resultado.SemRosto
                else -> {
                    val sim = if (j.isNull("similaridade")) null else j.optDouble("similaridade")
                    if (j.optBoolean("liberado", false)) {
                        Resultado.Liberado(j.optString("nome", ""), sim)
                    } else {
                        Resultado.Negado(if (j.isNull("motivo")) null else j.optString("motivo"), sim)
                    }
                }
            }
        } catch (e: Exception) {
            Resultado.Erro("Resposta inválida do servidor")
        }
    }
}
