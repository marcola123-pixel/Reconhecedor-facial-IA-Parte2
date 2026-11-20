package br.ufms.portaria

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.net.Uri
import android.util.Base64
import androidx.exifinterface.media.ExifInterface
import java.io.ByteArrayOutputStream

object PreparadorFotos {

    private const val TAMANHO_MAXIMO = 1280
    private const val LIMITE_BASE64 = 2_700_000

    fun preparar(
        context: Context,
        uri: Uri
    ): String {

        val resolver = context.contentResolver

        val opcoes = BitmapFactory.Options().apply {
            inJustDecodeBounds = true
        }

        val fluxoDimensoes = resolver.openInputStream(uri)
            ?: error("Nao foi possivel abrir a fotografia.")

        fluxoDimensoes.use {
            BitmapFactory.decodeStream(it, null, opcoes)
        }

        require(opcoes.outWidth > 0 && opcoes.outHeight > 0) {
            "Fotografia invalida."
        }

        var amostragem = 1

        while (
            opcoes.outWidth / amostragem > TAMANHO_MAXIMO * 2 ||
            opcoes.outHeight / amostragem > TAMANHO_MAXIMO * 2
        ) {
            amostragem *= 2
        }

        val leitura = BitmapFactory.Options().apply {
            inSampleSize = amostragem
        }

        val original = resolver.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, leitura)
        } ?: error("Nao foi possivel decodificar a fotografia.")

        val orientacao = resolver.openInputStream(uri)?.use {
            ExifInterface(it).getAttributeInt(
                ExifInterface.TAG_ORIENTATION,
                ExifInterface.ORIENTATION_NORMAL
            )
        } ?: ExifInterface.ORIENTATION_NORMAL

        val matriz = Matrix()

        when (orientacao) {
            ExifInterface.ORIENTATION_ROTATE_90 ->
                matriz.postRotate(90f)

            ExifInterface.ORIENTATION_ROTATE_180 ->
                matriz.postRotate(180f)

            ExifInterface.ORIENTATION_ROTATE_270 ->
                matriz.postRotate(270f)

            ExifInterface.ORIENTATION_FLIP_HORIZONTAL ->
                matriz.postScale(-1f, 1f)

            ExifInterface.ORIENTATION_FLIP_VERTICAL ->
                matriz.postScale(1f, -1f)

            ExifInterface.ORIENTATION_TRANSPOSE -> {
                matriz.postRotate(90f)
                matriz.postScale(-1f, 1f)
            }

            ExifInterface.ORIENTATION_TRANSVERSE -> {
                matriz.postRotate(270f)
                matriz.postScale(-1f, 1f)
            }
        }

        val orientada = Bitmap.createBitmap(
            original,
            0,
            0,
            original.width,
            original.height,
            matriz,
            true
        )

        if (orientada !== original) {
            original.recycle()
        }

        val escala = minOf(
            1f,
            TAMANHO_MAXIMO.toFloat() /
                maxOf(orientada.width, orientada.height)
        )

        val largura = maxOf(1, (orientada.width * escala).toInt())
        val altura = maxOf(1, (orientada.height * escala).toInt())

        val reduzida = Bitmap.createScaledBitmap(
            orientada,
            largura,
            altura,
            true
        )

        if (reduzida !== orientada) {
            orientada.recycle()
        }

        var qualidade = 85
        var resultado: String

        do {
            val saida = ByteArrayOutputStream()

            reduzida.compress(
                Bitmap.CompressFormat.JPEG,
                qualidade,
                saida
            )

            resultado = Base64.encodeToString(
                saida.toByteArray(),
                Base64.NO_WRAP
            )

            qualidade -= 10

        } while (resultado.length > LIMITE_BASE64 && qualidade >= 45)

        reduzida.recycle()

        require(resultado.length <= LIMITE_BASE64) {
            "Fotografia muito grande mesmo apos compressao."
        }

        return "data:image/jpeg;base64,$resultado"
    }
}
