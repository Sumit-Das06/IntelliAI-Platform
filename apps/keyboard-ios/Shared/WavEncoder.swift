import Foundation

/// PCM16 → WAV container, as a pure function — no Apple audio types,
/// fully unit-testable. Canonicalization happens server-side, so the
/// keyboard ships exactly what it recorded: 16 kHz, mono, 16-bit
/// little-endian PCM in a standard RIFF/WAVE/fmt/data layout —
/// byte-compatible with the Android client's encoder and the backend's
/// canonical audio path.
enum WavEncoder {
    static let sampleRateHz: Int = 16_000
    static let channels: Int = 1
    static let bitsPerSample: Int = 16

    /// Wrap little-endian PCM16 sample bytes in a RIFF/WAVE header.
    static func wav(fromPCM pcm: Data) -> Data {
        let byteRate = sampleRateHz * channels * bitsPerSample / 8
        let blockAlign = channels * bitsPerSample / 8

        var data = Data(capacity: 44 + pcm.count)
        data.append(contentsOf: Array("RIFF".utf8))
        data.appendUInt32LE(UInt32(36 + pcm.count))
        data.append(contentsOf: Array("WAVE".utf8))
        data.append(contentsOf: Array("fmt ".utf8))
        data.appendUInt32LE(16) // fmt chunk size
        data.appendUInt16LE(1) // PCM
        data.appendUInt16LE(UInt16(channels))
        data.appendUInt32LE(UInt32(sampleRateHz))
        data.appendUInt32LE(UInt32(byteRate))
        data.appendUInt16LE(UInt16(blockAlign))
        data.appendUInt16LE(UInt16(bitsPerSample))
        data.append(contentsOf: Array("data".utf8))
        data.appendUInt32LE(UInt32(pcm.count))
        data.append(pcm)
        return data
    }
}

private extension Data {
    mutating func appendUInt32LE(_ value: UInt32) {
        var little = value.littleEndian
        Swift.withUnsafeBytes(of: &little) { append(contentsOf: $0) }
    }

    mutating func appendUInt16LE(_ value: UInt16) {
        var little = value.littleEndian
        Swift.withUnsafeBytes(of: &little) { append(contentsOf: $0) }
    }
}
