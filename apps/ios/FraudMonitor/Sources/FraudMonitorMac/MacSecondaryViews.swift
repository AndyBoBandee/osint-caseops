import FraudMonitorCore
import SwiftUI

struct MacTrendsView: View {
    @Environment(FraudMonitorStore.self) private var store
    private var trends: TrendOverview { store.dashboard.trendOverview }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                MacHeader(
                    title: "Trends",
                    subtitle: "Summaries from normalized local results.",
                    symbol: "chart.line.uptrend.xyaxis"
                )

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 320), spacing: 16)], spacing: 16) {
                    TrendPanel("Top Categories", symbol: "tag", buckets: trends.topCategoriesThisWeek)
                    OfficialAlertPanel(alerts: trends.officialSourceAlerts)
                    TrendPanel("State Activity", symbol: "map", buckets: trends.stateActivity)
                    TrendPanel("Payment Rails", symbol: "creditcard", buckets: trends.paymentRailMentions)
                    TrendPanel("Emerging Keywords", symbol: "sparkle.magnifyingglass", buckets: trends.emergingKeywords)
                }
            }
            .padding(24)
        }
    }
}

struct MacProvidersView: View {
    @Environment(FraudMonitorStore.self) private var store

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                MacHeader(
                    title: "Providers",
                    subtitle: "Configured source readiness and registry health.",
                    symbol: "antenna.radiowaves.left.and.right"
                )
                MacConnectionBanner()

                LazyVGrid(columns: [GridItem(.adaptive(minimum: 360), spacing: 16)], spacing: 16) {
                    ForEach(store.dashboard.providers) { provider in
                        ProviderHealthCard(provider: provider)
                            .onTapGesture {
                                store.selectedProvider = provider
                            }
                    }
                    ProviderHealthCard(provider: store.dashboard.detailedProvider)
                        .onTapGesture {
                            store.selectedProvider = store.dashboard.detailedProvider
                        }
                }

                MacCard("Configuration", symbol: store.dashboard.configurationValidation.isValid ? "checkmark.seal" : "exclamationmark.triangle") {
                    VStack(alignment: .leading, spacing: 10) {
                        Label(
                            store.dashboard.configurationValidation.isValid ? "Configuration ready" : "Configuration needs review",
                            systemImage: store.dashboard.configurationValidation.isValid ? "checkmark.seal.fill" : "exclamationmark.triangle.fill"
                        )
                        .foregroundStyle(store.dashboard.configurationValidation.isValid ? .green : .orange)

                        ForEach(store.dashboard.configurationValidation.issues) { issue in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(issue.provider)
                                    .font(.headline)
                                Text(issue.message)
                                    .foregroundStyle(.secondary)
                            }
                            Divider()
                        }
                    }
                }
            }
            .padding(24)
        }
    }
}

struct MacSettingsOverviewView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            MacHeader(
                title: "Settings",
                subtitle: "Connection settings are available in the macOS Settings window.",
                symbol: "gearshape"
            )
            MacConnectionBanner()

            MacCard("Open Settings", symbol: "slider.horizontal.3") {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Use Fraud Monitor settings to change the local API base URL and review local-first boundaries.")
                        .foregroundStyle(.secondary)
                    SettingsLink {
                        Label("Open Settings", systemImage: "gearshape")
                    }
                }
            }
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }
}

struct MacSettingsView: View {
    @Environment(FraudMonitorStore.self) private var store

    var body: some View {
        @Bindable var store = store

        Form {
            Section("API") {
                TextField("Base URL", text: $store.baseURLText)
                    .accessibilityLabel("API base URL")
                Button("Reconnect") {
                    Task { await store.refresh() }
                }
                .accessibilityLabel("Reconnect to local API")
            }

            Section("Scheduler") {
                Toggle(
                    "Cron enabled",
                    isOn: Binding(
                        get: { store.dashboard.schedule.enabled },
                        set: { enabled in Task { await store.setSchedule(enabled: enabled) } }
                    )
                )
                .accessibilityLabel("Enable scheduled scans")
                LabeledContent("Interval", value: "\(store.dashboard.schedule.intervalMinutes) min")
                LabeledContent("Last run", value: store.dashboard.schedule.lastCompletedAt.readableDate)
                LabeledContent("Next run", value: store.dashboard.schedule.nextRunAt.readableDate)
            }

            Section("Local-first Boundary") {
                Label("Results stay in the local API SQLite store", systemImage: "externaldrive")
                Label("Evidence saves require analyst action", systemImage: "person.crop.circle.badge.checkmark")
                Label("Fixture mode is separate from real provider runs", systemImage: "testtube.2")
            }
        }
    }
}

struct TrendPanel: View {
    let title: String
    let symbol: String
    let buckets: [TrendBucket]

    init(_ title: String, symbol: String, buckets: [TrendBucket]) {
        self.title = title
        self.symbol = symbol
        self.buckets = buckets
    }

    var body: some View {
        MacCard(title, symbol: symbol) {
            VStack(alignment: .leading, spacing: 10) {
                if buckets.isEmpty {
                    ContentUnavailableView("No data yet", systemImage: symbol)
                        .frame(minHeight: 120)
                }
                ForEach(buckets.prefix(6)) { bucket in
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(bucket.label.displayLabel)
                                .font(.headline)
                            if let sample = bucket.sampleTitles.first, !sample.isEmpty {
                                Text(sample)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .lineLimit(2)
                            }
                        }
                        Spacer()
                        Text("\(bucket.resultCount)")
                            .font(.title3.bold())
                            .foregroundStyle(.cyan)
                    }
                    Divider()
                }
            }
        }
    }
}

struct OfficialAlertPanel: View {
    let alerts: [TrendAlert]

    var body: some View {
        MacCard("Official Alerts", symbol: "checkmark.shield") {
            VStack(alignment: .leading, spacing: 10) {
                if alerts.isEmpty {
                    ContentUnavailableView("No official alerts", systemImage: "checkmark.shield")
                        .frame(minHeight: 120)
                }
                ForEach(alerts.prefix(6)) { alert in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(alert.title)
                            .font(.headline)
                            .lineLimit(2)
                        HStack {
                            StatusPill(alert.sourceConfidence)
                            Text(alert.fraudCategory.displayLabel)
                            Spacer()
                            Text(alert.state.isEmpty ? "Unknown" : alert.state)
                        }
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    }
                    Divider()
                }
            }
        }
    }
}

struct ProviderHealthCard: View {
    let provider: ProviderInfo

    var body: some View {
        MacCard(provider.displayName, symbol: provider.status == "ready" ? "checkmark.seal" : "exclamationmark.triangle") {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    StatusPill(provider.status.displayLabel)
                    StatusPill(provider.sourceConfidence)
                    Spacer()
                    Text("\(provider.resultsLast24h) in 24h")
                        .foregroundStyle(.secondary)
                }
                Text(provider.note)
                    .foregroundStyle(.secondary)
                    .lineLimit(3)
                DetailRow("Source type", provider.sourceType.displayLabel)
                DetailRow("Requires key", provider.requiresAPIKey ? "Yes" : "No")
                DetailRow("Last success", provider.lastSuccessAt.readableDate)
                if !provider.lastErrorMessage.isEmpty {
                    Text(provider.lastErrorMessage)
                        .foregroundStyle(.orange)
                        .lineLimit(3)
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Provider \(provider.displayName)")
        .accessibilityValue("\(provider.status.displayLabel), \(provider.sourceConfidence.displayLabel), \(provider.resultsLast24h) results in 24 hours")
    }
}
