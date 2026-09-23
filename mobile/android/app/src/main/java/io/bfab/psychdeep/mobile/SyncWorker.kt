package io.bfab.psychdeep.mobile

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class SyncWorker(appContext: Context, params: WorkerParameters) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val store = SecureStore(applicationContext)
        val token = store.get("access_token") ?: return Result.failure()
        val baseUrl = store.get("api_url") ?: "https://psychdeep-api.onrender.com"
        val queue = InferenceQueue(applicationContext)
        return try {
            for (e in queue.pending()) {
                val body = JSONObject().apply {
                    put("event_id", e.eventId)
                    put("model_id", e.modelId)
                    put("model_version", e.modelVersion)
                    put("input_hash", e.inputHash)
                    put("output", JSONObject().put("text", e.outputText))
                    put("output_schema", "mobile-chat-v1")
                    put("client_platform", "android")
                    put("client_app_version", BuildConfig.VERSION_NAME)
                    put("inference_engine", "llama.cpp")
                    put("client_model_checksum", e.modelVersion)
                    put("latency_ms", e.latencyMs)
                }
                val conn = URL(baseUrl.trimEnd('/') + "/api/v1/mobile/inference-events").openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.connectTimeout = 15_000
                conn.readTimeout = 30_000
                conn.doOutput = true
                conn.setRequestProperty("Authorization", "Bearer " + token)
                conn.setRequestProperty("Content-Type", "application/json")
                conn.setRequestProperty("Idempotency-Key", e.eventId)
                conn.outputStream.use { it.write(body.toString().toByteArray()) }
                val code = conn.responseCode
                if (code in 200..299 || code == 409) queue.markSynced(e.eventId)
                else if (code == 401 || code == 403) return Result.failure()
                else return Result.retry()
                conn.disconnect()
            }
            Result.success()
        } catch (_: Exception) {
            Result.retry()
        }
    }
}
