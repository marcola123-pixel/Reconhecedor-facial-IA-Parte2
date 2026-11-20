package br.ufms.portaria

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class CadastroPessoaActivity : AppCompatActivity() {

    private val fotosSelecionadas = mutableListOf<android.net.Uri>()

    private val seletorFotos =
        registerForActivityResult(
            androidx.activity.result.contract.ActivityResultContracts.PickMultipleVisualMedia(10)
        ) { uris ->
            fotosSelecionadas.clear()
            fotosSelecionadas.addAll(uris.distinct().take(10))
            atualizarQuantidade()
        }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContentView(R.layout.activity_cadastro_pessoa)

        findViewById<TextView>(R.id.btnVoltarCadastro)
            .setOnClickListener { finish() }

        findViewById<Button>(R.id.btnSelecionarFotos)
            .setOnClickListener { abrirSeletorFotos() }

        findViewById<Button>(R.id.btnConfirmarCadastro)
            .setOnClickListener {
                executarCadastro()
            }

        atualizarQuantidade()
    }

    private fun abrirSeletorFotos() {
        seletorFotos.launch(
            androidx.activity.result.PickVisualMediaRequest(
                androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia.ImageOnly
            )
        )
    }
    private fun atualizarQuantidade() {
        val quantidade = fotosSelecionadas.size

        findViewById<TextView>(R.id.textoQuantidadeFotos).text =
            "$quantidade de 10 fotografias selecionadas"

        findViewById<Button>(R.id.btnConfirmarCadastro).isEnabled =
            quantidade in 3..10

        if (quantidade > 10) {
            Toast.makeText(
                this,
                "Selecione no maximo 10 fotografias.",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    private var enviando = false

    private fun executarCadastro() {
        if (enviando) return

        val nome = findViewById<android.widget.EditText>(
            R.id.campoNomePessoa
        ).text.toString().trim()

        val token = AdminSession.obterToken()

        if (nome.isBlank() || nome.length > 80) {
            Toast.makeText(this, "Informe um nome valido.", Toast.LENGTH_LONG).show()
            return
        }

        if (fotosSelecionadas.size !in 3..10) {
            Toast.makeText(this, "Selecione de 3 a 10 fotos.", Toast.LENGTH_LONG).show()
            return
        }

        if (token.isNullOrBlank()) {
            Toast.makeText(this, "Acesso administrativo necessario.", Toast.LENGTH_LONG).show()
            return
        }

        val fotos = fotosSelecionadas.toList()
        enviando = true

        findViewById<Button>(R.id.btnConfirmarCadastro).isEnabled = false
        findViewById<Button>(R.id.btnSelecionarFotos).isEnabled = false
        findViewById<TextView>(R.id.textoAvisoCadastro).text =
            "Preparando fotografias..."

        Thread {
            try {
                val imagens = fotos.mapIndexed { indice, uri ->
                    runOnUiThread {
                        if (!isFinishing && !isDestroyed) {
                            findViewById<TextView>(R.id.textoAvisoCadastro).text =
                                "Preparando fotografia ${indice + 1} de ${fotos.size}..."
                        }
                    }

                    PreparadorFotos.preparar(applicationContext, uri)
                }

                runOnUiThread {
                    if (!isFinishing && !isDestroyed) {
                        findViewById<TextView>(R.id.textoAvisoCadastro).text =
                            "Enviando cadastro ao servidor..."
                    }
                }

                CadastroPessoaApi().cadastrar(
                    nome = nome,
                    imagens = imagens,
                    token = token
                ) { resultado, erro ->

                    runOnUiThread {
                        if (isFinishing || isDestroyed) return@runOnUiThread

                        enviando = false
                        findViewById<Button>(R.id.btnSelecionarFotos).isEnabled = true
                        atualizarQuantidade()

                        if (resultado != null) {
                            Toast.makeText(
                                this,
                                "Cadastro realizado! ${resultado.cadastradas} fotos validas.",
                                Toast.LENGTH_LONG
                            ).show()

                            setResult(RESULT_OK)
                            finish()
                        } else {
                            findViewById<TextView>(R.id.textoAvisoCadastro).text =
                                erro ?: "Falha no cadastro."
                        }
                    }
                }

            } catch (e: Exception) {
                runOnUiThread {
                    if (isFinishing || isDestroyed) return@runOnUiThread

                    enviando = false
                    findViewById<Button>(R.id.btnSelecionarFotos).isEnabled = true
                    atualizarQuantidade()

                    findViewById<TextView>(R.id.textoAvisoCadastro).text =
                        "Erro ao preparar fotografias: ${e.message ?: "erro desconhecido"}"
                }
            }
        }.start()
    }
}
