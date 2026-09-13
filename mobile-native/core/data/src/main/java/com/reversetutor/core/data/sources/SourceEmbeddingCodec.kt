package com.reversetutor.core.data.sources

import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * NEWMP-V1-024: float-vector <-> BLOB codec for source chunk embeddings.
 *
 * Vectors are stored little-endian IEEE 754, one float after another; the
 * dimension is implied by the blob length. A blob whose length is not a
 * multiple of 4 decodes to null so a corrupted row degrades to keyword
 * retrieval instead of crashing the context read.
 */
object SourceEmbeddingCodec {
    fun encode(vector: FloatArray): ByteArray =
        ByteBuffer.allocate(vector.size * java.lang.Float.BYTES)
            .order(ByteOrder.LITTLE_ENDIAN)
            .apply { vector.forEach(::putFloat) }
            .array()

    fun decode(blob: ByteArray): FloatArray? {
        if (blob.isEmpty() || blob.size % java.lang.Float.BYTES != 0) return null
        val buffer = ByteBuffer.wrap(blob).order(ByteOrder.LITTLE_ENDIAN)
        return FloatArray(blob.size / java.lang.Float.BYTES) { buffer.float }
    }
}
