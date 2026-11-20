package br.ufms.portaria

import android.content.Intent
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

        findViewById<TextView>(R.id.btnNovaPessoa)
            .setOnClickListener {
                if (!AdminSession.estaConectado()) {
                    Toast.makeText(
                        this,
                        "Conecte-se como administrador primeiro.",
                        Toast.LENGTH_LONG
                    ).show()
                    return@setOnClickListener
                }

                startActivity(
                    Intent(this, CadastroPessoaActivity::class.java)
                )
            }
        carregarPessoas()
    }


    override fun onResume() {
        super.onResume()
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

                    val container = LinearLayout(this).apply {
                        orientation = LinearLayout.VERTICAL
                        setBackgroundResource(R.drawable.bg_premium_card)
                    }

                    item.setBackgroundColor(Color.TRANSPARENT)
                    container.addView(item)

                    val botaoExcluir = TextView(this).apply {
                        text = "EXCLUIR CADASTRO"
                        setTextColor(Color.rgb(248, 113, 113))
                        textSize = 14f
                        gravity = Gravity.CENTER
                        setPadding(24, 16, 24, 24)
                        setOnClickListener {
                            confirmarExclusao(pessoa.nome)
                        }
                    }

                    container.addView(botaoExcluir)
                    lista.addView(container, params)
                }
            }
        }
    }

    private var exclusaoEmAndamento = false

    private fun confirmarExclusao(nome: String) {
        if (exclusaoEmAndamento) return

        val token = AdminSession.obterToken()

        if (token.isNullOrBlank()) {
            Toast.makeText(
                this,
                "Autenticacao administrativa necessaria.",
                Toast.LENGTH_LONG
            ).show()
            return
        }

        androidx.appcompat.app.AlertDialog.Builder(this)
            .setTitle("Excluir cadastro?")
            .setMessage(
                "Deseja excluir definitivamente o cadastro de \"$nome\"?\n\n" +
                "Os dados biometricos e o historico de reconhecimento " +
                "associado a esta pessoa serao removidos.\n\n" +
                "Esta acao nao pode ser desfeita."
            )
            .setNegativeButton("CANCELAR", null)
            .setPositiveButton("EXCLUIR DEFINITIVAMENTE") { _, _ ->
                executarExclusao(nome, token)
            }
            .show()
    }

    private fun executarExclusao(nome: String, token: String) {
        if (exclusaoEmAndamento) return

        exclusaoEmAndamento = true

        findViewById<TextView>(R.id.textoTotalPessoas).text =
            "Excluindo cadastro..."

        PessoasApi().excluir(nome, token) { sucesso, mensagem ->

            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread

                exclusaoEmAndamento = false

                Toast.makeText(
                    this,
                    mensagem,
                    Toast.LENGTH_LONG
                ).show()

                if (!sucesso && mensagem == "Acesso administrativo negado.") {
                    AdminSession.desconectar()
                }

                carregarPessoas()
            }
        }
    }
}
