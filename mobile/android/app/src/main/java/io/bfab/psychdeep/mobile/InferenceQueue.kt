package io.bfab.psychdeep.mobile

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

data class PendingEvent(
    val eventId: String,
    val inputHash: String,
    val outputText: String,
    val modelId: String,
    val modelVersion: String,
    val latencyMs: Long
)

class InferenceQueue(context: Context) : SQLiteOpenHelper(context, "psychdeep_local.db", null, 1) {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""CREATE TABLE inference_events(
            event_id TEXT PRIMARY KEY,
            encrypted_prompt TEXT NOT NULL,
            input_hash TEXT NOT NULL,
            output_text TEXT NOT NULL,
            model_id TEXT NOT NULL,
            model_version TEXT NOT NULL,
            latency_ms INTEGER NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            synced INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        )""")
    }
    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {}

    fun enqueue(event: PendingEvent, encryptedPrompt: String) {
        val v = ContentValues().apply {
            put("event_id", event.eventId); put("encrypted_prompt", encryptedPrompt)
            put("input_hash", event.inputHash); put("output_text", event.outputText)
            put("model_id", event.modelId); put("model_version", event.modelVersion)
            put("latency_ms", event.latencyMs); put("idempotency_key", event.eventId)
            put("created_at", System.currentTimeMillis())
        }
        writableDatabase.insertOrThrow("inference_events", null, v)
    }

    fun pending(limit: Int = 20): List<PendingEvent> {
        val out = mutableListOf<PendingEvent>()
        readableDatabase.query("inference_events",
            arrayOf("event_id","input_hash","output_text","model_id","model_version","latency_ms"),
            "synced=0", null, null, null, "created_at ASC", limit.toString()).use { c ->
            while (c.moveToNext()) out += PendingEvent(
                c.getString(0), c.getString(1), c.getString(2),
                c.getString(3), c.getString(4), c.getLong(5)
            )
        }
        return out
    }

    fun markSynced(eventId: String) {
        writableDatabase.update("inference_events", ContentValues().apply { put("synced", 1) }, "event_id=?", arrayOf(eventId))
    }
}
