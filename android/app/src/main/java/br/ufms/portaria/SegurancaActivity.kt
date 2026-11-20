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
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

class SegurancaActivity : AppCompatActivity() {

    private lateinit var lista: LinearLayout
    private lateinit var status: TextView
    private lateinit var total: TextView
    private lateinit var sucessos: TextView
    private lateinit var falhas: TextView

    private var carregando = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_seguranca)

        lista = findViewById(R.id.segurancaLista)
        status = findViewById(R.id.segurancaStatus)
        total = findViewById(R.id.segurancaTotal)
        sucessos = findViewById(R.id.segurancaSucessos)
        falhas = findViewById(R.id.segurancaFalhas)

        findViewById<View>(R.id.segurancaVoltar).setOnClickListener {
            finish()
        }

        findViewById<View>(R.id.segurancaAtualizar).setOnClickListener {
            carregarAuditoria()
        }

        carregarAuditoria()
    }

    private fun carregarAuditoria() {
        if (carregando) return

        val token = AdminSession.obterToken()

        if (token.isNullOrBlank()) {
            status.text = "Conecte-se como administrador no Dashboard."
            lista.removeAllViews()
            limparContadores()
            return
        }

        carregando = true
        status.text = "Carregando auditoria..."

        SegurancaApi().carregar(token) { eventos, erro ->
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread

                carregando = false

                if (eventos == null) {
                    status.text = erro ?: "Nao foi possivel carregar a auditoria."

                    if (erro == "Acesso administrativo negado.") {
                        AdminSession.desconectar()
                        lista.removeAllViews()
                        limparContadores()

                        Toast.makeText(
                            this,
                            "Sessao administrativa encerrada.",
                            Toast.LENGTH_LONG
                        ).show()
                    }

                    return@runOnUiThread
                }

                val quantidadeSucessos = eventos.count { it.sucesso }
                val quantidadeFalhas = eventos.size - quantidadeSucessos

                total.text = eventos.size.toString()
                sucessos.text = quantidadeSucessos.toString()
                falhas.text = quantidadeFalhas.toString()

                status.text = "${eventos.size} eventos exibidos (maximo 100)"

                lista.removeAllViews()

                if (eventos.isEmpty()) {
                    lista.addView(
                        criarTexto("Nenhum evento de seguranca registrado.", 15)
                    )
                } else {
                    eventos.forEach { evento ->
                        lista.addView(criarCard(evento))
                    }
                }
            }
        }
    }

    private fun limparContadores() {
        total.text = "--"
        sucessos.text = "--"
        falhas.text = "--"
    }

    private fun criarCard(evento: SegurancaApi.Evento): View {
        val verde = Color.rgb(34, 197, 94)
        val vermelho = Color.rgb(248, 113, 113)
        val cor = if (evento.sucesso) verde else vermelho

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

        val titulo = criarTexto(traduzirEvento(evento.tipo), 17).apply {
            setTypeface(null, Typeface.BOLD)
        }

        val resultado = criarTexto(
            if (evento.sucesso) "SUCESSO" else "FALHA",
            13
        ).apply {
            setTextColor(cor)
            setTypeface(null, Typeface.BOLD)
        }

        val data = criarTexto(
            "Data: ${formatarDataLocal(evento.dataHora)}",
            12
        ).apply {
            setTextColor(Color.rgb(166, 185, 173))
        }

        val identificador = criarTexto(
            "Evento #${evento.id} | ${evento.tipo}",
            12
        ).apply {
            setTextColor(Color.rgb(166, 185, 173))
        }

        card.addView(titulo)
        card.addView(resultado)
        card.addView(data)
        card.addView(identificador)

        return card
    }

    private fun traduzirEvento(tipo: String): String {
        return when (tipo) {
            "admin_login_success" -> "Login administrativo realizado"
            "admin_login_failure" -> "Falha no login administrativo"
            "admin_access_denied" -> "Acesso administrativo negado"
            "person_created" -> "Pessoa cadastrada"
            "person_deleted" -> "Pessoa removida"
            "admin_logout" -> "Sessao administrativa encerrada"
            "session_expired" -> "Sessao expirada"
            "security_block" -> "Bloqueio de seguranca"
            else -> tipo
        }
    }

    private fun formatarDataLocal(valor: String): String {
        if (valor.isBlank()) return "--"

        return try {
            val data = OffsetDateTime.parse(valor)
                .atZoneSameInstant(ZoneId.systemDefault())

            val formato = DateTimeFormatter.ofPattern(
                "dd/MM/yyyy 'as' HH:mm:ss",
                Locale.forLanguageTag("pt-BR")
            )

            data.format(formato)
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