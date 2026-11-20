package br.ufms.portaria

import okhttp3.Call
import okhttp3.Callback
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class SegurancaApi {

    data class Evento(
        val id: Int,
        val dataHora: String,
        val tipo: String,
        val sucesso: Boolean
    )

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    fun carregar(
        token: String,
        callback: (List<Evento>?, String?) -> Unit
    ) {
        if (token.isBlank()) {
            callback(null, "Autenticacao administrativa necessaria.")
            return
        }

        val request = Request.Builder()
            .url("${Config.SERVER_URL}/seguranca/auditoria?limit=100")
            .header("X-Porteiro-Token", token)
            .get()
            .build()

        client.newCall(request).enqueue(object : Callback {

            override fun onFailure(call: Call, e: IOException) {
                callback(null, "Falha de conexao com o servidor.")
            }

            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (it.code == 401 || it.code == 403) {
                        callback(null, "Acesso administrativo negado.")
                        return
                    }

                    if (!it.isSuccessful) {
                        callback(null, "Erro HTTP ${it.code}.")
                        return
                    }

                    try {
                        val json = JSONObject(it.body?.string().orEmpty())
                        val array = json.getJSONArray("eventos")
                        val eventos = mutableListOf<Evento>()

                        for (i in 0 until array.length()) {
                            val item = array.getJSONObject(i)

                            eventos.add(
                                Evento(
                                    id = item.getInt("id"),
                                    dataHora = item.optString("data_hora", ""),
                                    tipo = item.getString("tipo"),
                                    sucesso = item.getBoolean("sucesso")
                                )
                            )
                        }

                        callback(eventos, null)
                    } catch (e: Exception) {
                        callback(null, "Resposta invalida do servidor.")
                    }
                }
            }
        })
    }
}