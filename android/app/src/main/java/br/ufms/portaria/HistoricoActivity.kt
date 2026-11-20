package br.ufms.portaria

import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import java.util.Locale
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class HistoricoActivity : AppCompatActivity() {

    private lateinit var lista: LinearLayout
    private lateinit var status: TextView
    private lateinit var total: TextView
    private lateinit var autorizados: TextView
    private lateinit var negados: TextView

    private var carregando = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_historico)

        lista = findViewById(R.id.historicoLista)
        status = findViewById(R.id.historicoStatus)
        total = findViewById(R.id.historicoTotal)
        autorizados = findViewById(R.id.historicoAutorizados)
        negados = findViewById(R.id.historicoNegados)

        findViewById<View>(R.id.historicoVoltar).setOnClickListener {
            finish()
        }

        findViewById<View>(R.id.historicoAtualizar).setOnClickListener {
            carregarHistorico()
        }

        carregarHistorico()
    }

    private fun carregarHistorico() {
        if (carregando) return

        val token = AdminSession.obterToken()

        if (token.isNullOrBlank()) {
            status.text = "Conecte-se como administrador no Dashboard."
            lista.removeAllViews()
            return
        }

        carregando = true
        status.text = "Carregando registros..."

        HistoricoApi().carregar(token) { resultado, erro ->
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread

                carregando = false

                if (resultado == null) {
                    status.text = erro ?: "Nao foi possivel carregar o historico."

                    if (erro == "Acesso administrativo negado.") {
                        AdminSession.desconectar()
                        lista.removeAllViews()
                        Toast.makeText(
                            this,
                            "Sessao administrativa encerrada.",
                            Toast.LENGTH_LONG
                        ).show()
                    }
                    return@runOnUiThread
                }

                total.text = resultado.total.toString()
                autorizados.text = resultado.autorizados.toString()
                negados.text = resultado.negados.toString()

                status.text = if (resultado.retencaoDias > 0) {
                    "Retencao: ${resultado.retencaoDias} dias | " +
                        "${resultado.registros.size} registros exibidos"
                } else {
                    "${resultado.registros.size} registros exibidos"
                }

                lista.removeAllViews()

                if (resultado.registros.isEmpty()) {
                    lista.addView(criarTexto("Nenhum reconhecimento registrado.", 15))
                } else {
                    resultado.registros.forEach { registro ->
                        lista.addView(criarCard(registro))
                    }
                }
            }
        }
    }

    private fun criarCard(registro: HistoricoApi.Registro): View {
        val verde = Color.rgb(34, 197, 94)
        val vermelho = Color.rgb(248, 113, 113)

        val cor = if (registro.liberado) verde else vermelho
        val resultado = if (registro.liberado) "AUTORIZADO" else "NEGADO"

        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(14), dp(16), dp(14))

            background = GradientDrawable().apply {
                setColor(Color.rgb(25, 36, 30))
                cornerRadius = dp(14).toFloat()
                setStroke(dp(1), Color.rgb(49, 69, 55))
            }

            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                bottomMargin = dp(12)
            }
        }

        val nome = criarTexto(
            registro.nome.ifBlank { "Desconhecido" },
            17
        ).apply {
            setTypeface(null, Typeface.BOLD)
        }

        val situacao = criarTexto(resultado, 13).apply {
            setTextColor(cor)
            setTypeface(null, Typeface.BOLD)
        }

        val data = criarTexto(
            "Data: ${formatarDataLocal(registro.dataHora)}",
            12
        ).apply {
            setTextColor(Color.rgb(166, 185, 173))
        }

        val similaridade = criarTexto(
            "Similaridade: " +
                String.format(Locale.US, "%.4f", registro.similaridade),
            12
        ).apply {
            setTextColor(Color.rgb(166, 185, 173))
        }

        card.addView(nome)
        card.addView(situacao)
        card.addView(data)
        card.addView(similaridade)

        return card
    }

    private fun formatarDataLocal(valor: String): String {
        if (valor.isBlank()) return "--"

        return try {
            val dataUtc = OffsetDateTime.parse(valor)

            val dataLocal = dataUtc.atZoneSameInstant(
                ZoneId.systemDefault()
            )

            val formato = DateTimeFormatter.ofPattern(
                "dd/MM/yyyy 'às' HH:mm:ss",
                Locale.forLanguageTag("pt-BR")
            )

            dataLocal.format(formato)
        } catch (e: Exception) {
            valor
        }
    }
    private fun criarTexto(valor: String, tamanho: Int): TextView {
        return TextView(this).apply {
            text = valor
            textSize = tamanho.toFloat()
            setTextColor(Color.WHITE)
            setPadding(0, dp(3), 0, dp(3))
        }
    }

    private fun dp(valor: Int): Int {
        return (valor * resources.displayMetrics.density).toInt()
    }
}