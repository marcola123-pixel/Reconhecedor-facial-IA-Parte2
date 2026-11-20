package br.ufms.portaria

import okhttp3.Call
import okhttp3.Callback
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class HistoricoApi {

    data class Registro(
        val nome: String,
        val dataHora: String,
        val liberado: Boolean,
        val similaridade: Double
    )

    data class Resultado(
        val total: Int,
        val autorizados: Int,
        val negados: Int,
        val registros: List<Registro>,
        val retencaoDias: Int
    )

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    fun carregar(
        token: String,
        callback: (Resultado?, String?) -> Unit
    ) {
        if (token.isBlank()) {
            callback(null, "Autenticacao administrativa necessaria.")
            return
        }

        val request = Request.Builder()
            .url("${Config.SERVER_URL}/historico?limit=100")
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
                        val stats = json.getJSONObject("estatisticas")
                        val array = json.getJSONArray("registros")
                        val registros = mutableListOf<Registro>()

                        for (i in 0 until array.length()) {
                            val item = array.getJSONObject(i)

                            registros.add(
                                Registro(
                                    nome = item.optString("nome", "Desconhecido"),
                                    dataHora = item.optString("data_hora", ""),
                                    liberado = item.getBoolean("liberado"),
                                    similaridade = item.optDouble("similaridade", 0.0)
                                )
                            )
                        }

                        callback(
                            Resultado(
                                total = stats.getInt("total_registros"),
                                autorizados = stats.getInt("total_liberados"),
                                negados = stats.getInt("total_negados"),
                                registros = registros,
                                retencaoDias = json.optInt("retencao_dias", 0)
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