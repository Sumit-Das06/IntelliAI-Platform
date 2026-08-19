import UIKit

/// The minimum viable IntelliAI keyboard surface, iOS-idiomatic (this
/// is deliberately NOT a port of the Android layout): three letter
/// rows, a control row, a prominent mic key, the language chip, and a
/// one-line status area that doubles as the error surface. UIKit only;
/// no third-party UI.
final class KeyboardView: UIView {
    enum Key {
        case character(String)
        case space
        case backspace
        case returnKey
        case nextKeyboard
        case cycleLanguage
        case microphone
    }

    var onKey: ((Key) -> Void)?

    private let statusLabel = UILabel()
    private let languageChip = UIButton(type: .system)
    private let micButton = UIButton(type: .system)
    private var statusResetTask: Task<Void, Never>?

    private static let rows: [[String]] = [
        ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
        ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
        ["z", "x", "c", "v", "b", "n", "m"],
    ]

    override init(frame: CGRect) {
        super.init(frame: frame)
        backgroundColor = .systemGray5
        build()
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("not used") }

    // MARK: - State rendering

    func render(state: DictationController.State) {
        switch state {
        case .idle:
            micButton.tintColor = .label
            showStatus("IntelliAI")
        case .recording:
            micButton.tintColor = .systemRed
            showStatus("Listening… tap to finish")
        case .processing:
            micButton.tintColor = .systemOrange
            showStatus("Transcribing…")
        }
    }

    func render(language: DictationLanguage) {
        languageChip.setTitle(language.indicator, for: .normal)
    }

    /// One-line status/error surface; transient messages reset to the
    /// brand line after a few seconds.
    func showStatus(_ message: String) {
        statusLabel.text = message
        statusResetTask?.cancel()
        guard message != "IntelliAI" else { return }
        statusResetTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: 4_000_000_000)
            guard !Task.isCancelled else { return }
            await MainActor.run { self?.statusLabel.text = "IntelliAI" }
        }
    }

    // MARK: - Layout

    private func build() {
        let stack = UIStackView()
        stack.axis = .vertical
        stack.spacing = 6
        stack.distribution = .fillEqually
        stack.translatesAutoresizingMaskIntoConstraints = false
        addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 4),
            stack.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -4),
            stack.topAnchor.constraint(equalTo: topAnchor, constant: 4),
            stack.bottomAnchor.constraint(equalTo: bottomAnchor, constant: -4),
        ])

        // Status row: brand/status text + language chip.
        let statusRow = UIStackView()
        statusRow.axis = .horizontal
        statusRow.spacing = 8
        statusLabel.text = "IntelliAI"
        statusLabel.font = .preferredFont(forTextStyle: .footnote)
        statusLabel.textColor = .secondaryLabel
        statusLabel.adjustsFontSizeToFitWidth = true
        languageChip.setTitle(DictationLanguage.default.indicator, for: .normal)
        languageChip.titleLabel?.font = .preferredFont(forTextStyle: .footnote)
        languageChip.addAction(
            UIAction { [weak self] _ in self?.onKey?(.cycleLanguage) }, for: .touchUpInside
        )
        statusRow.addArrangedSubview(statusLabel)
        statusRow.addArrangedSubview(languageChip)
        stack.addArrangedSubview(statusRow)

        for row in Self.rows {
            let rowStack = UIStackView()
            rowStack.axis = .horizontal
            rowStack.spacing = 4
            rowStack.distribution = .fillEqually
            for letter in row {
                rowStack.addArrangedSubview(
                    keyButton(letter) { [weak self] in self?.onKey?(.character(letter)) }
                )
            }
            stack.addArrangedSubview(rowStack)
        }

        // Control row: globe · mic · space · backspace · return.
        let controls = UIStackView()
        controls.axis = .horizontal
        controls.spacing = 4
        let globe = symbolButton("globe") { [weak self] in self?.onKey?(.nextKeyboard) }
        micButton.setImage(UIImage(systemName: "mic.fill"), for: .normal)
        micButton.tintColor = .label
        micButton.backgroundColor = .systemBackground
        micButton.layer.cornerRadius = 6
        micButton.addAction(
            UIAction { [weak self] _ in self?.onKey?(.microphone) }, for: .touchUpInside
        )
        let space = keyButton("space") { [weak self] in self?.onKey?(.space) }
        let backspace = symbolButton("delete.left") { [weak self] in self?.onKey?(.backspace) }
        let returnKey = symbolButton("return") { [weak self] in self?.onKey?(.returnKey) }
        controls.addArrangedSubview(globe)
        controls.addArrangedSubview(micButton)
        controls.addArrangedSubview(space)
        controls.addArrangedSubview(backspace)
        controls.addArrangedSubview(returnKey)
        globe.widthAnchor.constraint(equalToConstant: 44).isActive = true
        micButton.widthAnchor.constraint(equalToConstant: 56).isActive = true
        backspace.widthAnchor.constraint(equalToConstant: 44).isActive = true
        returnKey.widthAnchor.constraint(equalToConstant: 44).isActive = true
        stack.addArrangedSubview(controls)
    }

    private func keyButton(_ title: String, action: @escaping () -> Void) -> UIButton {
        let button = UIButton(type: .system)
        button.setTitle(title, for: .normal)
        button.titleLabel?.font = .systemFont(ofSize: 18)
        button.backgroundColor = .systemBackground
        button.layer.cornerRadius = 6
        button.addAction(UIAction { _ in action() }, for: .touchUpInside)
        return button
    }

    private func symbolButton(_ symbol: String, action: @escaping () -> Void) -> UIButton {
        let button = UIButton(type: .system)
        button.setImage(UIImage(systemName: symbol), for: .normal)
        button.tintColor = .label
        button.backgroundColor = .systemBackground
        button.layer.cornerRadius = 6
        button.addAction(UIAction { _ in action() }, for: .touchUpInside)
        return button
    }
}
