package br.ufms.portaria

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Matrix
import android.os.Bundle
import android.os.SystemClock
import android.util.Log
import android.view.View
import android.view.WindowManager
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Cliente da portaria: mostra a câmera frontal, envia ~1 quadro/s ao servidor (POST /reconhecer) e exibe
 * o resultado. Nenhum quadro é salvo no aparelho; nada identificável é escrito no log.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var preview: PreviewView
    private lateinit var painel: View
    private lateinit var estado: TextView
    private lateinit var detalhe: TextView

    private val analiseExecutor = Executors.newSingleThreadExecutor()
    private val api = PortariaApi()
    private val emAndamento = AtomicBoolean(false)
    private var ultimoEnvio = 0L

    @Volatile
    private var bloqueadoAte = 0L

    private val pedirCamera =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { concedida ->
            if (concedida) iniciarCamera()
            else mostrar("Sem permissão", "A câmera é necessária para a portaria.", COR_NEUTRA)
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        preview = findViewById(R.id.preview)
        painel = findViewById(R.id.painel)
        estado = findViewById(R.id.estado)
        detalhe = findViewById(R.id.detalhe)
        mostrar("Aguardando", "Aponte o rosto para a câmera", COR_NEUTRA)

        val temPermissao = ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED
        if (temPermissao) iniciarCamera() else pedirCamera.launch(Manifest.permission.CAMERA)
    }

    override fun onDestroy() {
        super.onDestroy()
        analiseExecutor.shutdown()
    }

    private fun iniciarCamera() {
        val futuro = ProcessCameraProvider.getInstance(this)
        futuro.addListener({
            try {
                val provider = futuro.get()
                val previewCase = Preview.Builder().build().also {
                    it.setSurfaceProvider(preview.surfaceProvider)
                }
                val analise = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()
                    .also { it.setAnalyzer(analiseExecutor) { quadro -> analisar(quadro) } }

                provider.unbindAll()
                provider.bindToLifecycle(this, CameraSelector.DEFAULT_FRONT_CAMERA, previewCase, analise)
            } catch (e: Exception) {
                Log.e(TAG, "não foi possível iniciar a câmera", e)
                mostrar("Erro", "Não foi possível iniciar a câmera.", COR_NEUTRA)
            }
        }, ContextCompat.getMainExecutor(this))
    }

    /** Roda na thread de análise. Sempre fecha o quadro (senão a câmera para de entregar). */
    private fun analisar(quadro: ImageProxy) {
        try {
            val agora = SystemClock.elapsedRealtime()
            if (agora < bloqueadoAte) return
            if (agora - ultimoEnvio < Config.INTERVALO_MS) return
            if (!emAndamento.compareAndSet(false, true)) return     // já há uma requisição em andamento
            ultimoEnvio = agora
            val jpeg = paraJpeg(quadro)
            api.reconhecer(jpeg) { resultado ->
                if (resultado is Resultado.LimiteAtingido) {
                    val esperaMs = resultado.esperaSegundos * 1000L
                    bloqueadoAte = SystemClock.elapsedRealtime() + esperaMs
                }

                emAndamento.set(false)
                runOnUiThread { exibir(resultado) }
            }
        } catch (e: Exception) {
            emAndamento.set(false)
            Log.e(TAG, "falha ao processar o quadro", e)
        } finally {
            quadro.close()
        }
    }

    /** O sensor entrega a imagem deitada; giramos para o rosto ficar em pé antes de enviar (o MTCNN precisa disso). */
    private fun paraJpeg(quadro: ImageProxy): ByteArray {
        val bitmap = quadro.toBitmap()
        val matriz = Matrix().apply { postRotate(quadro.imageInfo.rotationDegrees.toFloat()) }
        val girado = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matriz, true)
        val saida = ByteArrayOutputStream()
        girado.compress(Bitmap.CompressFormat.JPEG, Config.JPEG_QUALITY, saida)
        return saida.toByteArray()
    }

    private fun exibir(r: Resultado) {
        when (r) {
            is Resultado.SemRosto -> mostrar("Nenhum rosto", "Aponte o rosto para a câmera", COR_NEUTRA)
            is Resultado.Liberado -> mostrar("Acesso liberado", r.nome + similaridade(r.similaridade), COR_OK)
            is Resultado.Negado -> {
                val motivo = r.motivo?.let { MOTIVOS[it] } ?: "Desconhecido"
                mostrar("Acesso negado", motivo + similaridade(r.similaridade), COR_NEGADO)
            }
            is Resultado.LimiteAtingido -> mostrar(
                "Aguardando servidor",
                "Muitas solicitações. Aguarde ${r.esperaSegundos} segundos.",
                COR_NEUTRA
            )
            is Resultado.Erro -> mostrar("Erro", r.mensagem, COR_NEUTRA)
        }
    }

    private fun similaridade(valor: Double?): String =
        if (valor == null) "" else "  ·  similaridade ${Math.round(valor * 100)}%"

    private fun mostrar(titulo: String, texto: String, corFundo: Int) {
        estado.text = titulo
        detalhe.text = texto
        painel.setBackgroundColor(corFundo)
    }

    companion object {
        private const val TAG = "Portaria"      // nunca registre nomes ou imagens no log
        private val COR_NEUTRA = Color.parseColor("#CC171D27")
        private val COR_OK = Color.parseColor("#CC1F3C31")
        private val COR_NEGADO = Color.parseColor("#CC3C2225")
        private val MOTIVOS = mapOf(
            "multiplos_rostos" to "Mais de um rosto",
            "rosto_pequeno_demais" to "Aproxime-se da câmera",
            "galeria_vazia" to "Nenhuma pessoa cadastrada",
            "abaixo_do_limiar" to "Desconhecido",
        )
    }
}
