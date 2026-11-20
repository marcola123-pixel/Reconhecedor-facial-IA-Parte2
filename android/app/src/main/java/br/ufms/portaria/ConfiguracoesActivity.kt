package br.ufms.portaria

import android.os.Bundle
import android.text.InputType
import android.widget.EditText
import android.view.View
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import java.util.Locale

class ConfiguracoesActivity : AppCompatActivity() {

    private lateinit var conexao: TextView
    private lateinit var modelo: TextView
    private lateinit var limiar: TextView
    private lateinit var dispositivo: TextView
    private lateinit var pessoas: TextView
    private lateinit var sessao: TextView

    private var carregando = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_configuracoes)

        conexao = findViewById(R.id.configConexao)
        modelo = findViewById(R.id.configModelo)
        limiar = findViewById(R.id.configLimiar)
        dispositivo = findViewById(R.id.configDispositivo)
        pessoas = findViewById(R.id.configPessoas)
        sessao = findViewById(R.id.configSessao)

        findViewById<View>(R.id.configVoltar).setOnClickListener {
            finish()
        }

        findViewById<View>(R.id.configAtualizar).setOnClickListener {
            carregarStatus()
        }

        findViewById<View>(R.id.configConectar).setOnClickListener {
            solicitarConexao()
        }

findViewById<View>(R.id.configDesconectar).setOnClickListener {
            confirmarDesconexao()
        }

        findViewById<TextView>(R.id.configEndereco).text =
            Config.SERVER_URL

        findViewById<TextView>(R.id.configIntervalo).text =
            "${Config.INTERVALO_MS} ms"

        atualizarSessao()
        carregarStatus()
    }

    override fun onResume() {
        super.onResume()
        if (::sessao.isInitialized) {
            atualizarSessao()
        }
    }

    private fun atualizarSessao() {
        val conectado = AdminSession.estaConectado()

        sessao.text = if (conectado) {
            "Administrador conectado"
        } else {
            "Administrador desconectado"
        }

        findViewById<View>(R.id.configConectar).visibility =
            if (conectado) View.GONE else View.VISIBLE

        findViewById<View>(R.id.configDesconectar).visibility =
            if (conectado) View.VISIBLE else View.GONE
    }

    private fun carregarStatus() {
        if (carregando) return

        carregando = true
        conexao.text = "Verificando conexao..."

        ConfiguracoesApi().carregar { resultado, erro ->
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread

                carregando = false

                if (resultado == null) {
                    conexao.text = erro ?: "Falha na conexao."
                    modelo.text = "--"
                    limiar.text = "--"
                    dispositivo.text = "--"
                    pessoas.text = "--"
                    return@runOnUiThread
                }

                conexao.text = "Servidor conectado"
                modelo.text = resultado.experimento
                limiar.text = String.format(
                    Locale.US,
                    "%.4f",
                    resultado.limiar
                )
                dispositivo.text = resultado.dispositivo
                pessoas.text = resultado.pessoas.toString()
            }
        }
    }

    private fun solicitarConexao() {
        if (AdminSession.estaConectado()) {
            atualizarSessao()
            return
        }

        val campo = EditText(this).apply {
            hint = "Token administrativo"
            inputType = InputType.TYPE_CLASS_TEXT or
                InputType.TYPE_TEXT_VARIATION_PASSWORD
            setSingleLine(true)
        }

        val container = android.widget.FrameLayout(this).apply {
            val margem = (24 * resources.displayMetrics.density).toInt()
            setPadding(margem, 0, margem, 0)
            addView(campo)
        }

        AlertDialog.Builder(this)
            .setTitle("Conectar administrador")
            .setMessage("Informe o token administrativo.")
            .setView(container)
            .setPositiveButton("Conectar") { _, _ ->
                val token = campo.text.toString().trim()

                if (token.isBlank()) {
                    Toast.makeText(
                        this,
                        "Informe o token administrativo.",
                        Toast.LENGTH_SHORT
                    ).show()
                } else {
                    validarConexao(token)
                }
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    private fun validarConexao(token: String) {
        DashboardStatusApi().carregarEstatisticas(token) { dados ->
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread

                if (dados == null) {
                    Toast.makeText(
                        this,
                        "Token invalido ou servidor indisponivel.",
                        Toast.LENGTH_LONG
                    ).show()
                    return@runOnUiThread
                }

                AdminSession.conectar(token)
                atualizarSessao()

                Toast.makeText(
                    this,
                    "Administrador conectado com sucesso.",
                    Toast.LENGTH_SHORT
                ).show()
            }
        }
    }
    private fun confirmarDesconexao() {
        if (!AdminSession.estaConectado()) {
            Toast.makeText(
                this,
                "Nenhuma sessao administrativa ativa.",
                Toast.LENGTH_SHORT
            ).show()
            return
        }

        AlertDialog.Builder(this)
            .setTitle("Encerrar sessao?")
            .setMessage(
                "O token administrativo sera removido da memoria do aplicativo."
            )
            .setPositiveButton("Desconectar") { _, _ ->
                AdminSession.desconectar()
                atualizarSessao()

                Toast.makeText(
                    this,
                    "Sessao administrativa encerrada.",
                    Toast.LENGTH_SHORT
                ).show()
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }
}