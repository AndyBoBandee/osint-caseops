import FraudMonitorCore
import SwiftUI
#if canImport(UIKit)
import UIKit
#elseif canImport(AppKit)
import AppKit
#endif

enum AppTheme {
    #if canImport(UIKit)
    static let background = Color(uiColor: .systemGroupedBackground)
    #elseif canImport(AppKit)
    static let background = Color(nsColor: .windowBackgroundColor)
    #else
    static let background = Color.gray.opacity(0.08)
    #endif
}

struct NativeCard<Content: View>: View {
    @ViewBuilder let content: Content

    var body: some View {
        content
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}

struct MetricGrid: View {
    let dashboard: DashboardData

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 150), spacing: 12)], spacing: 12) {
            MetricTile(title: "Stored", value: dashboard.totalResults, symbol: "tray.full")
            MetricTile(title: "Pending", value: dashboard.pendingResults, symbol: "clock")
            MetricTile(title: "Relevant", value: dashboard.relevantResults, symbol: "checkmark.circle")
            MetricTile(title: "Evidence", value: dashboard.evidenceCount, symbol: "link")
        }
    }
}

struct MetricTile: View {
    let title: String
    let value: Int
    let symbol: String

    var body: some View {
        NativeCard {
            VStack(alignment: .leading, spacing: 10) {
                Image(systemName: symbol)
                    .foregroundStyle(.cyan)
                Text("\(value)")
                    .font(.system(.title, design: .rounded, weight: .bold))
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

struct TrendBucketSection: View {
    let title: String
    let buckets: [TrendBucket]
    let systemImage: String

    init(_ title: String, buckets: [TrendBucket], systemImage: String) {
        self.title = title
        self.buckets = buckets
        self.systemImage = systemImage
    }

    var body: some View {
        Section(title) {
            if buckets.isEmpty {
                ContentUnavailableView("No data yet", systemImage: systemImage)
            }
            ForEach(buckets) { bucket in
                HStack {
                    Label(bucket.label.displayLabel, systemImage: systemImage)
                    Spacer()
                    Text("\(bucket.resultCount)")
                        .font(.headline)
                        .foregroundStyle(.cyan)
                }
                if let sample = bucket.sampleTitles.first, !sample.isEmpty {
                    Text(sample)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}

struct OfficialAlertsSection: View {
    let alerts: [TrendAlert]

    var body: some View {
        Section("High-confidence official alerts") {
            if alerts.isEmpty {
                ContentUnavailableView("No official alerts", systemImage: "checkmark.shield")
            }
            ForEach(alerts) { alert in
                VStack(alignment: .leading, spacing: 6) {
                    Text(alert.title)
                        .font(.headline)
                    HStack {
                        StatusBadge(text: alert.sourceConfidence)
                        Text(alert.fraudCategory.displayLabel)
                        Spacer()
                        Text(alert.state.isEmpty ? "Unknown" : alert.state)
                    }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
            }
        }
    }
}

struct ResultRow: View {
    let result: NewsResult

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(result.title.isEmpty ? result.sourceURL : result.title)
                        .font(.headline)
                    Text(result.publisher.isEmpty ? result.provider.displayLabel : result.publisher)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                StatusBadge(text: result.reviewStatus.displayLabel)
            }
            Text(result.snippet.isEmpty ? "No provider snippet returned." : result.snippet)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineLimit(3)
            HStack {
                StatusBadge(text: result.fraudCategory.displayLabel)
                StatusBadge(text: result.paymentRail.displayLabel)
                StatusBadge(text: result.sourceConfidence)
            }
        }
        .padding(.vertical, 4)
    }
}

struct ProviderRow: View {
    let provider: ProviderInfo

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            Image(systemName: provider.status == "ready" ? "checkmark.seal.fill" : "exclamationmark.triangle.fill")
                .foregroundStyle(provider.status == "ready" ? .green : .orange)
            VStack(alignment: .leading, spacing: 4) {
                Text(provider.displayName)
                    .font(.headline)
                Text(provider.note)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                Text("\(provider.sourceType.displayLabel) · \(provider.resultsLast24h) in 24h")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            StatusBadge(text: provider.status.displayLabel)
        }
    }
}

struct StatusBadge: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(.cyan.opacity(0.16), in: Capsule())
            .foregroundStyle(.cyan)
    }
}

struct ResultDetailSheet: View {
    @Environment(FraudMonitorStore.self) private var store
    @Environment(\.dismiss) private var dismiss
    let result: NewsResult
    @State private var note = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Source") {
                    Text(result.title.isEmpty ? result.sourceURL : result.title)
                    LabeledContent("Publisher", value: result.publisher)
                    LabeledContent("Provider", value: result.provider.displayLabel)
                    LabeledContent("URL", value: result.sourceURL)
                }
                Section("Classification") {
                    LabeledContent("Category", value: result.fraudCategory.displayLabel)
                    LabeledContent("Payment rail", value: result.paymentRail.displayLabel)
                    LabeledContent("Victim segment", value: result.victimSegment.displayLabel)
                    LabeledContent("Confidence", value: result.classificationConfidence)
                }
                Section("Actions") {
                    Button("Mark relevant") {
                        Task {
                            await store.review(result, as: "relevant")
                            dismiss()
                        }
                    }
                    Button("Mark not relevant") {
                        Task {
                            await store.review(result, as: "not_relevant")
                            dismiss()
                        }
                    }
                    TextField("Evidence note", text: $note, axis: .vertical)
                    Button("Save evidence") {
                        Task {
                            await store.saveEvidence(result, note: note)
                            dismiss()
                        }
                    }
                }
            }
            .navigationTitle("Result")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

struct ProviderDetailSheet: View {
    @Environment(\.dismiss) private var dismiss
    let provider: ProviderInfo

    var body: some View {
        NavigationStack {
            Form {
                Section("Provider") {
                    LabeledContent("Name", value: provider.displayName)
                    LabeledContent("Status", value: provider.status.displayLabel)
                    LabeledContent("Source type", value: provider.sourceType.displayLabel)
                    LabeledContent("Confidence", value: provider.sourceConfidence)
                    LabeledContent("Requires key", value: provider.requiresAPIKey ? "Yes" : "No")
                    LabeledContent("Fixture mode", value: provider.fixtureModeAvailable ? "Available" : "Unavailable")
                }
                Section("Health") {
                    LabeledContent("Last run", value: provider.lastRunAt.readableDate)
                    LabeledContent("Last success", value: provider.lastSuccessAt.readableDate)
                    LabeledContent("24h results", value: "\(provider.resultsLast24h)")
                    if !provider.lastErrorMessage.isEmpty {
                        Text(provider.lastErrorMessage)
                            .foregroundStyle(.orange)
                    }
                }
                Section("Safety") {
                    Text(provider.safetyNotes)
                }
            }
            .navigationTitle(provider.displayName)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
            }
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
