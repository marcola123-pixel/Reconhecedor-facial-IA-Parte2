package br.ufms.portaria

import android.os.Bundle
import android.graphics.Color
import android.view.Gravity
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class PessoasActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_pessoas)

        findViewById<TextView>(R.id.btnVoltarPessoas)
            .setOnClickListener { finish() }

        findViewById<TextView>(R.id.btnAtualizarPessoas)
            .setOnClickListener { carregarPessoas() }

        carregarPessoas()
    }

    private fun carregarPessoas() {
        val token = AdminSession.obterToken()

        if (token.isNullOrBlank()) {
            findViewById<TextView>(R.id.textoTotalPessoas).text =
                "Acesso administrativo necessario."
            return
        }

        findViewById<TextView>(R.id.textoTotalPessoas).text =
            "Carregando pessoas..."

        PessoasApi().listar(token) { resultado, erro ->

            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread

                if (resultado == null) {
                    findViewById<TextView>(
                        R.id.textoTotalPessoas
                    ).text = erro ?: "Falha ao carregar pessoas."

                    if (erro == "Acesso administrativo negado.") {
                        AdminSession.desconectar()
                    }
                    return@runOnUiThread
                }

                findViewById<TextView>(
                    R.id.textoTotalPessoas
                ).text = "Total: ${resultado.total} pessoas"

                val lista = findViewById<LinearLayout>(
                    R.id.listaPessoas
                )

                lista.removeAllViews()

                if (resultado.pessoas.isEmpty()) {
                    val vazio = TextView(this).apply {
                        text = "Nenhuma pessoa cadastrada."
                        setTextColor(Color.WHITE)
                        textSize = 16f
                    }
                    lista.addView(vazio)
                    return@runOnUiThread
                }

                resultado.pessoas.forEach { pessoa ->

                    val item = TextView(this).apply {
                        text = "${pessoa.nome}\n${pessoa.imagens} imagens cadastradas"
                        setTextColor(Color.WHITE)
                        textSize = 17f
                        setPadding(24, 24, 24, 24)
                        setBackgroundResource(R.drawable.bg_premium_card)
                    }

                    val params = LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT,
                        LinearLayout.LayoutParams.WRAP_CONTENT
                    ).apply {
                        bottomMargin = (12 * resources.displayMetrics.density).toInt()
                    }

                    lista.addView(item, params)
                }
            }
        }
    }
}
