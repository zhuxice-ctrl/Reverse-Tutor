package com.reversetutor.core.data.sources

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * NEWMP-V1-024: embedding blob codec round-trips and rejects malformed blobs
 * so a corrupted row degrades to keyword retrieval instead of crashing.
 */
class SourceEmbeddingCodecTest {

    @Test
    fun encodesAndDecodesRoundTrip() {
        val vector = floatArrayOf(0.25f, -1.5f, 3f, 0f)

        val decoded = SourceEmbeddingCodec.decode(SourceEmbeddingCodec.encode(vector))

        assertEquals(4, decoded?.size)
        assertTrue(vector.contentEquals(decoded))
    }

    @Test
    fun singleFloatRoundTrips() {
        val decoded = SourceEmbeddingCodec.decode(SourceEmbeddingCodec.encode(floatArrayOf(7f)))
        assertEquals(1, decoded?.size)
        assertEquals(7f, decoded!![0], 0.0001f)
    }

    @Test
    fun emptyVectorDecodesToNull() {
        assertNull(SourceEmbeddingCodec.decode(SourceEmbeddingCodec.encode(floatArrayOf())))
    }

    @Test
    fun malformedBlobsDecodeToNull() {
        assertNull(SourceEmbeddingCodec.decode(byteArrayOf(1, 2, 3)))
        assertNull(SourceEmbeddingCodec.decode(ByteArray(0)))
    }
}
