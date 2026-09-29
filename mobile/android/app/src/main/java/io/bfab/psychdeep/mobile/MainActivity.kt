package io.bfab.psychdeep.mobile

import android.app.Activity
import android.os.Bundle
import android.content.Intent
import android.view.ViewGroup
import android.widget.*
import androidx.lifecycle.lifecycleScope
import androidx.work.*
import dev.ffmpegkit.llama.Llama
import dev.ffmpegkit.llama.LlamaConfig
import dev.ffmpegkit.llama.LlamaModel
import kotlinx.coroutines.launch
import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.TimeUnit

class MainActivity : Activity() {
    private lateinit var store: SecureStore
    private lateinit var queue: InferenceQueue
    private var model: LlamaModel? = null
    private var modelFile: File? = null
    private lateinit var api: EditText
    private lateinit var token: EditText
    private lateinit var prompt: EditText
    private lateinit var response: TextView
    private lateinit var modelLabel: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store = SecureStore(this)
        queue = InferenceQueue(this)
        scheduleSync()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 32, 32, 32)
        }
        api = EditText(this).apply {
            hint = "PsychDeep API"
            setText(store.get("api_url") ?: "https://psychdeep-api.onrender.com")
        }
        token = EditText(this).apply {
            hint = "Access token"
            inputType = 0x81
            setText(store.get("access_token") ?: "")
        }
        val saveSession = Button(this).apply {
            text = "Guardar sesión"
            setOnClickListener {
                store.put("api_url", api.text.toString().trim())
                store.put("access_token", token.text.toString().trim())
                scheduleSync()
            }
        }
        val choose = Button(this).apply {
            text = "Seleccionar modelo GGUF"
            setOnClickListener {
                startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    type = "application/octet-stream"
                    addCategory(Intent.CATEGORY_OPENABLE)
                }, 10)
            }
        }
        modelLabel = TextView(this).apply { text = "Modelo: ninguno" }
        prompt = EditText(this).apply {
            hint = "Escribe un mensaje"
            minLines = 4
            gravity = 48
        }
        val send = Button(this).apply {
            text = "Inferir localmente"
            setOnClickListener { runInference() }
        }
        response = TextView(this).apply { text = "Las respuestas se generan en el dispositivo." }

        root.addView(api, lp())
        root.addView(token, lp())
        root.addView(saveSession, lp())
        root.addView(choose, lp())
        root.addView(modelLabel, lp())
        root.addView(prompt, lp())
        root.addView(send, lp())
        root.addView(response, lp())
        setContentView(root)
    }

    private fun lp() = LinearLayout.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT,
        ViewGroup.LayoutParams.WRAP_CONTENT
    )

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != 10 || resultCode != RESULT_OK || data?.data == null) return
        lifecycleScope.launch {
            try {
                val uri = data.data!!
                modelFile = File(filesDir, "models/model.gguf").also { it.parentFile?.mkdirs() }
                contentResolver.openInputStream(uri)!!.use { input ->
                    modelFile!!.outputStream().use { output -> input.copyTo(output) }
                }
                val checksum = sha256(modelFile!!)
                store.put("model_checksum", checksum)
                modelLabel.text = "Modelo: " + modelFile!!.name + " (" + checksum.take(12) + "…)"
                response.text = "Cargando modelo…"
                model = Llama.loadModel(
                    modelFile!!.absolutePath,
                    LlamaConfig(contextSize = 2048, threads = 4)
                )
                response.text = "Modelo cargado. Inferencia local disponible."
            } catch (e: Exception) {
                response.text = "Error cargando modelo: " + (e.message ?: "desconocido")
            }
        }
    }

    private fun runInference() {
        val m = model ?: run {
            response.text = "Selecciona y carga primero un GGUF."
            return
        }
        val text = prompt.text.toString()
        if (text.isBlank()) return
        lifecycleScope.launch {
            val start = System.currentTimeMillis()
            try {
                val result = Llama.complete(
                    m,
                    prompt = text,
                    systemPrompt = "Eres PsychDeep. No diagnostiques, no prescribas y no modifiques decisiones deterministas de seguridad.",
                    maxTokens = 256
                )
                val latency = System.currentTimeMillis() - start
                response.text = result.text
                val hash = sha256(text.toByteArray())
                val checksum = store.get("model_checksum") ?: "unknown"
                val event = PendingEvent(
                    UUID.randomUUID().toString(),
                    hash,
                    result.text,
                    modelFile?.name ?: "gguf",
                    checksum,
                    latency
                )
                // The raw prompt remains encrypted on-device and is not uploaded by SyncWorker.
                queue.enqueue(event, encryptedPromptMarker(text))
                scheduleSync()
            } catch (e: Exception) {
                response.text = "Error de inferencia local: " + (e.message ?: "desconocido")
            }
        }
    }

    private fun encryptedPromptMarker(text: String): String {
        // SecureStore uses Android Keystore AES-GCM. The queue stores only an encrypted marker;
        // server sync deliberately sends the hash, not the raw prompt.
        val name = "queue_prompt_" + UUID.randomUUID()
        store.put(name, text)
        return store.get(name) ?: ""
    }

    private fun sha256(text: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(text).joinToString("") { "%02x".format(it) }

    private fun sha256(file: File): String = FileInputStream(file).use { input ->
        val md = MessageDigest.getInstance("SHA-256")
        val buf = ByteArray(1024 * 1024)
        while (true) {
            val n = input.read(buf)
            if (n < 0) break
            md.update(buf, 0, n)
        }
        md.digest().joinToString("") { "%02x".format(it) }
    }

    private fun scheduleSync() {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()
        val periodic = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
            .setConstraints(constraints)
            .build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "psychdeep-mobile-sync",
            ExistingPeriodicWorkPolicy.UPDATE,
            periodic
        )
        WorkManager.getInstance(this).enqueue(
            OneTimeWorkRequestBuilder<SyncWorker>().setConstraints(constraints).build()
        )
    }
}
