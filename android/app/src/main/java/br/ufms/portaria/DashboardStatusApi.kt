package br.ufms.portaria

import okhttp3.Call
import okhttp3.Callback
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class DashboardStatusApi {

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()


    data class Estatisticas(
        val reconhecimentos: Int,
        val autorizados: Int,
        val negados: Int
    )

    fun carregarEstatisticas(
        token: String,
        callback: (Estatisticas?) -> Unit
    ) {
        val request = Request.Builder()
            .url("${Config.SERVER_URL}/dashboard/estatisticas")
            .header("X-Porteiro-Token", token)
            .get()
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback(null)
            }

            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (!it.isSuccessful) {
                        callback(null)
                        return
                    }

                    val estatisticas = try {
                        val json = JSONObject(it.body?.string().orEmpty())

                        Estatisticas(
                            reconhecimentos = json.getInt("total_registros"),
                            autorizados = json.getInt("total_liberados"),
                            negados = json.getInt("total_negados")
                        )
                    } catch (e: Exception) {
                        null
                    }

                    callback(estatisticas)
                }
            }
        })
    }


    fun carregarPessoas(callback: (Int?) -> Unit) {
        val request = Request.Builder()
            .url("${Config.SERVER_URL}/status")
            .get()
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback(null)
            }

            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (!it.isSuccessful) {
                        callback(null)
                        return
                    }

                    val quantidade = try {
                        val json = JSONObject(it.body?.string().orEmpty())
                        if (json.has("pessoas_cadastradas") &&
                            !json.isNull("pessoas_cadastradas")) {
                            json.getInt("pessoas_cadastradas")
                        } else {
                            null
                        }
                    } catch (e: Exception) {
                        null
                    }

                    callback(quantidade)
                }
            }
        })
    }
}
