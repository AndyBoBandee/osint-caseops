import FraudMonitorCore
import AppKit
import SwiftUI

struct MacHeader: View {
    let title: String
    let subtitle: String
    let symbol: String

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            Image(systemName: symbol)
                .font(.title2)
                .foregroundStyle(.cyan)
                .frame(width: 34, height: 34)
            VStack(alignment: .leading, spacing: 3) {
                Text(title)
                    .font(.largeTitle.bold())
                Text(subtitle)
                    .foregroundStyle(.secondary)
            }
            Spacer()
        }
    }
}

struct MacConnectionBanner: View {
    @Environment(FraudMonitorStore.self) private var store

    var body: some View {
        MacCard(statusTitle, symbol: statusSymbol) {
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .top, spacing: 12) {
                    Image(systemName: statusSymbol)
                        .foregroundStyle(statusColor)
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(statusTitle)
                            .font(.headline)
                        Text(statusDetail)
                            .foregroundStyle(.secondary)
                        Text("Base URL: \(store.baseURLText)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .textSelection(.enabled)
                    }
                    Spacer()
                    Button {
                        Task { await store.checkBackendHealth() }
                    } label: {
                        Label("Check Status", systemImage: "stethoscope")
                    }
                    .accessibilityLabel("Check local API status")
                    .accessibilityHint("Checks the API and database health endpoints without starting or stopping the backend.")
                }

                Divider()

                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    CopyCommandButton(title: "Copy make api", command: store.apiLaunchCommand)
                    CopyCommandButton(title: "Copy fixture API", command: store.fixtureAPILaunchCommand)
                    CopyCommandButton(title: "Copy make mac-run", command: store.macRunCommand)
                }
                .accessibilityElement(children: .contain)
            }
            .accessibilityElement(children: .contain)
            .accessibilityLabel(statusTitle)
            .accessibilityValue(statusDetail)
        }
    }

    private var statusSymbol: String {
        switch store.backendConnectionState {
        case .offline, .degraded: "exclamationmark.triangle.fill"
        case .checking: "arrow.triangle.2.circlepath"
        case .connected: "checkmark.seal.fill"
        case .unknown:
            switch store.phase {
            case .failed: "exclamationmark.triangle.fill"
            case .loading: "arrow.triangle.2.circlepath"
            default: "checkmark.seal.fill"
            }
        }
    }

    private var statusColor: Color {
        switch store.backendConnectionState {
        case .offline, .degraded: .orange
        case .checking: .cyan
        case .connected: .green
        case .unknown:
            switch store.phase {
            case .failed: .orange
            case .loading: .cyan
            default: .green
            }
        }
    }

    private var statusTitle: String {
        switch store.backendConnectionState {
        case .offline: "Local API offline"
        case .degraded: "Local API degraded"
        case .checking: "Checking local API"
        case .connected: "Local API connected"
        case .unknown:
            switch store.phase {
            case .failed: "API needs attention"
            case .loading: "Syncing Fraud Monitor"
            case .loaded: "Connected to Fraud Monitor"
            case .idle: "Ready"
            }
        }
    }

    private var statusDetail: String {
        switch store.backendConnectionState {
        case .offline(let message):
            return "Could not reach \(store.baseURLText). \(message)"
        case .degraded(let message):
            return "\(message). Last checked \(store.lastBackendCheckText)."
        case .checking:
            return "Checking API and database health at \(store.baseURLText)."
        case .connected:
            return "API and database are healthy. \(store.dashboard.runtime.readyProviderCount) ready provider(s), \(store.dashboard.pendingResults) pending result(s). Last checked \(store.lastBackendCheckText)."
        case .unknown:
            if case .failed(let message) = store.phase {
                return message
            }
            return "\(store.dashboard.runtime.readyProviderCount) ready provider(s), \(store.dashboard.pendingResults) pending result(s)"
        }
    }
}

struct CopyCommandButton: View {
    let title: String
    let command: String
    @State private var copied = false

    var body: some View {
        Button {
            NSPasteboard.general.clearContents()
            NSPasteboard.general.setString(command, forType: .string)
            copied = true
        } label: {
            Label(copied ? "Copied" : title, systemImage: copied ? "checkmark" : "doc.on.doc")
        }
        .buttonStyle(.bordered)
        .accessibilityLabel(title)
        .accessibilityHint("Copies \(command.replacingOccurrences(of: "\n", with: " ")) to the clipboard.")
        .onChange(of: copied) { _, value in
            guard value else { return }
            Task {
                try? await Task.sleep(for: .seconds(2))
                copied = false
            }
        }
    }
}

struct CompactStatusPill: View {
    let text: String
    let symbol: String?

    init(_ text: String, symbol: String? = nil) {
        self.text = text
        self.symbol = symbol
    }

    var body: some View {
        HStack(spacing: 4) {
            if let symbol {
                Image(systemName: symbol)
                    .accessibilityHidden(true)
            }
            Text(text.displayLabel)
                .lineLimit(1)
        }
        .font(.caption.weight(.semibold))
        .padding(.horizontal, 7)
        .padding(.vertical, 3)
        .background(.secondary.opacity(0.12), in: Capsule())
        .foregroundStyle(.secondary)
        .accessibilityLabel(text.displayLabel)
    }
}

struct MacCard<Content: View>: View {
    let title: String
    let symbol: String
    @ViewBuilder let content: Content

    init(_ title: String, symbol: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.symbol = symbol
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label(title, systemImage: symbol)
                .font(.headline)
            content
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

struct MetricGridView: View {
    let dashboard: DashboardData

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 180), spacing: 14)], spacing: 14) {
            MetricCard(title: "Stored", value: dashboard.totalResults, symbol: "tray.full")
            MetricCard(title: "Pending", value: dashboard.pendingResults, symbol: "clock")
            MetricCard(title: "Relevant", value: dashboard.relevantResults, symbol: "checkmark.circle")
            MetricCard(title: "Evidence", value: dashboard.evidenceCount, symbol: "link")
        }
    }
}

struct MetricCard: View {
    let title: String
    let value: Int
    let symbol: String

    var body: some View {
        MacCard(title, symbol: symbol) {
            Text("\(value)")
                .font(.system(.largeTitle, design: .rounded, weight: .bold))
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

struct StatusPill: View {
    let text: String

    init(_ text: String) {
        self.text = text
    }

    var body: some View {
        Text(text)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(.cyan.opacity(0.16), in: Capsule())
            .foregroundStyle(.cyan)
            .accessibilityLabel(text.displayLabel)
    }
}

struct DetailRow: View {
    let label: String
    let value: String

    init(_ label: String, _ value: String) {
        self.label = label
        self.value = value
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value.isEmpty ? "Unknown" : value)
                .textSelection(.enabled)
        }
    }
}

extension String {
    var displayLabel: String {
        replacingOccurrences(of: "_", with: " ")
    }

    var readableDate: String {
        guard !isEmpty else { return "Never" }
        return replacingOccurrences(of: "T", with: " ").replacingOccurrences(of: "Z", with: " UTC")
    }
}
