import FraudMonitorCore
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
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: statusSymbol)
                    .foregroundStyle(statusColor)
                VStack(alignment: .leading, spacing: 4) {
                    Text(statusTitle)
                        .font(.headline)
                    Text(statusDetail)
                        .foregroundStyle(.secondary)
                }
                Spacer()
            }
        }
    }

    private var statusSymbol: String {
        switch store.phase {
        case .failed: "exclamationmark.triangle.fill"
        case .loading: "arrow.triangle.2.circlepath"
        default: "checkmark.seal.fill"
        }
    }

    private var statusColor: Color {
        switch store.phase {
        case .failed: .orange
        case .loading: .cyan
        default: .green
        }
    }

    private var statusTitle: String {
        switch store.phase {
        case .failed: "API needs attention"
        case .loading: "Syncing Fraud Monitor"
        case .loaded: "Connected to Fraud Monitor"
        case .idle: "Ready"
        }
    }

    private var statusDetail: String {
        if case .failed(let message) = store.phase {
            return message
        }
        return "\(store.dashboard.runtime.readyProviderCount) ready provider(s), \(store.dashboard.pendingResults) pending result(s)"
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
