package br.ufms.portaria

import android.content.Intent
import android.text.InputType
import android.widget.EditText
import androidx.appcompat.app.AlertDialog
import android.os.Bundle
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class DashboardActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_dashboard)

        findViewById<TextView>(R.id.btnReconhecimento).setOnClickListener {
            startActivity(Intent(this, MainActivity::class.java))
        }

        findViewById<TextView>(R.id.btnPessoas).setOnClickListener {
            startActivity(Intent(this, PessoasActivity::class.java))
        }
        findViewById<TextView>(R.id.btnHistorico).setOnClickListener {
            startActivity(Intent(this, HistoricoActivity::class.java))
        }
        findViewById<TextView>(R.id.btnSeguranca).setOnClickListener {
            startActivity(Intent(this, SegurancaActivity::class.java))
        }
        findViewById<TextView>(R.id.btnConfiguracoes).setOnClickListener {
            startActivity(Intent(this, ConfiguracoesActivity::class.java))
        }

        solicitarTokenAdministrativo()
    }

    override fun onResume() {
        super.onResume()
        carregarIndicadores()
    }


    private fun carregarIndicadores() {
        val indicador = findViewById<TextView>(R.id.valorPessoas)

        DashboardStatusApi().carregarPessoas { quantidade ->
            runOnUiThread {
                if (!isFinishing && !isDestroyed) {
                    indicador.text = quantidade?.toString() ?: "--"
                }
            }
        }
    }


    private fun solicitarTokenAdministrativo() {
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
            .setTitle("Acesso administrativo")
            .setMessage("Informe o token para carregar os indicadores.")
            .setView(container)
            .setPositiveButton("Conectar") { _, _ ->
                val token = campo.text.toString().trim()

                if (token.isEmpty()) {
                    Toast.makeText(
                        this,
                        "Informe o token administrativo.",
                        Toast.LENGTH_SHORT
                    ).show()
                } else {
                    carregarEstatisticas(token)
                }
            }
            .setNegativeButton("Agora nao", null)
            .show()
    }

    private fun carregarEstatisticas(token: String) {
        DashboardStatusApi().carregarEstatisticas(token) { dados ->
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread

                if (dados == null) {
                    Toast.makeText(
                        this,
                        "Nao foi possivel carregar as estatisticas.",
                        Toast.LENGTH_LONG
                    ).show()
                    return@runOnUiThread
                }
                AdminSession.conectar(token)



                findViewById<TextView>(
                    R.id.valorReconhecimentos
                ).text = dados.reconhecimentos.toString()

                findViewById<TextView>(
                    R.id.valorAutorizados
                ).text = dados.autorizados.toString()

                findViewById<TextView>(
                    R.id.valorNegados
                ).text = dados.negados.toString()
            }
        }
    }

    private fun configurarBotao(id: Int, nome: String) {
        findViewById<TextView>(id).setOnClickListener {
            Toast.makeText(
                this,
                "$nome: funcionalidade em desenvolvimento",
                Toast.LENGTH_SHORT
            ).show()
        }
    }
}
