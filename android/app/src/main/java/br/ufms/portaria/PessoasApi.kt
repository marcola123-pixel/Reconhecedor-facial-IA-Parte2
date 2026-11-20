package br.ufms.portaria

import okhttp3.Call
import okhttp3.Callback
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class PessoasApi {

    data class Pessoa(
        val nome: String,
        val imagens: Int
    )

    data class Resultado(
        val total: Int,
        val pessoas: List<Pessoa>
    )

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    fun listar(
        token: String,
        callback: (Resultado?, String?) -> Unit
    ) {
        val request = Request.Builder()
            .url("${Config.SERVER_URL}/pessoas")
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
                        val json = JSONObject(
                            it.body?.string().orEmpty()
                        )

                        val array = json.getJSONArray("pessoas")
                        val pessoas = mutableListOf<Pessoa>()

                        for (i in 0 until array.length()) {
                            val item = array.getJSONObject(i)

                            pessoas.add(
                                Pessoa(
                                    nome = item.getString("nome"),
                                    imagens = item.getInt("imagens")
                                )
                            )
                        }

                        callback(
                            Resultado(
                                total = json.getInt("total"),
                                pessoas = pessoas
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
