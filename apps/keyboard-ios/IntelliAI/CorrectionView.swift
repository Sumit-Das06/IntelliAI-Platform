import SwiftUI

/// "Improve this transcription": edit the LAST collected dictation and
/// send the correction through the existing public endpoint
/// (`POST /v1/audio/transcriptions/{sample_id}/correction`) — the same
/// contract as Web and Android; nothing iOS-specific. The server keeps
/// the original transcript immutable and evolves the current one.
/// Offered only when a sample id exists (no id → nothing to correct →
/// the section never appears).
struct CorrectionView: View {
    let sampleId: String
    let originalTranscript: String
    let onDone: () -> Void

    private let settings = SettingsStore()
    private let keychain = KeychainStore()

    @State private var corrected: String = ""
    @State private var sending = false
    @State private var status: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Your dictation") {
                    Text(originalTranscript).font(.footnote)
                }
                Section("Corrected text") {
                    TextEditor(text: $corrected).frame(minHeight: 120)
                }
                if let status {
                    Section { Text(status).font(.footnote) }
                }
                Button(sending ? "Sending…" : "Send correction") { send() }
                    .disabled(
                        sending
                            || corrected.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    )
            }
            .navigationTitle("Improve")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close", action: onDone)
                }
            }
            .onAppear { corrected = originalTranscript }
        }
    }

    private func send() {
        sending = true
        status = nil
        let debugBuild: Bool
        #if DEBUG
            debugBuild = true
        #else
            debugBuild = false
        #endif
        let client = IntelliAIApiClient(
            baseUrl: { settings.serverAddress },
            apiKey: { keychain.read() },
            debugBuild: debugBuild
        )
        let text = corrected
        Task {
            let outcome = await client.correct(sampleId: sampleId, correctedText: text)
            await MainActor.run {
                sending = false
                switch outcome {
                case .success:
                    status = "Correction saved. Thank you!"
                    onDone()
                case .failure(let kind):
                    status = FailureWording.message(for: kind, serverMessage: nil)
                }
            }
        }
    }
}
