import FraudMonitorCore
import SwiftUI

struct MonitorView: View {
    @Environment(FraudMonitorStore.self) private var store
    @State private var intervalText = "60"

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                StatusBanner()
                MetricGrid(dashboard: store.dashboard)
                RunPanel(intervalText: $intervalText)
                LatestJobPanel(job: store.dashboard.latestJob)
            }
            .padding()
        }
        .background(AppTheme.background)
        .onChange(of: store.dashboard.schedule.intervalMinutes) { _, newValue in
            intervalText = String(newValue)
        }
    }
}

struct TrendsView: View {
    @Environment(FraudMonitorStore.self) private var store
    private var trends: TrendOverview { store.dashboard.trendOverview }

    var body: some View {
        List {
            TrendBucketSection("Top categories this week", buckets: trends.topCategoriesThisWeek, systemImage: "tag")
            OfficialAlertsSection(alerts: trends.officialSourceAlerts)
            TrendBucketSection("State activity", buckets: trends.stateActivity, systemImage: "map")
            TrendBucketSection("Payment rails", buckets: trends.paymentRailMentions, systemImage: "creditcard")
            TrendBucketSection("Emerging keywords", buckets: trends.emergingKeywords, systemImage: "sparkle.magnifyingglass")
        }
        .listStyle(.automatic)
        .scrollContentBackground(.hidden)
        .background(AppTheme.background)
    }
}

struct ResultsView: View {
    @Environment(FraudMonitorStore.self) private var store
    @State private var query = ""
    @State private var reviewFilter = "all"

    private var filteredResults: [NewsResult] {
        store.dashboard.results.filter { result in
            let matchesReview = reviewFilter == "all" || result.reviewStatus == reviewFilter
            let haystack = "\(result.title) \(result.publisher) \(result.fraudCategory) \(result.paymentRail) \(result.state)".lowercased()
            let matchesQuery = query.isEmpty || haystack.contains(query.lowercased())
            return matchesReview && matchesQuery
        }
    }

    var body: some View {
        List {
            Section {
                Picker("Review", selection: $reviewFilter) {
                    Text("All").tag("all")
                    Text("Pending").tag("pending")
                    Text("Relevant").tag("relevant")
                    Text("Not relevant").tag("not_relevant")
                }
                .pickerStyle(.segmented)
            }

            Section("Review queue") {
                if filteredResults.isEmpty {
                    ContentUnavailableView("No matching results", systemImage: "tray")
                }
                ForEach(filteredResults) { result in
                    Button {
                        store.selectedResult = result
                    } label: {
                        ResultRow(result: result)
                    }
                    .buttonStyle(.plain)
                    .swipeActions(edge: .trailing) {
                        Button("Relevant") {
                            Task { await store.review(result, as: "relevant") }
                        }
                        .tint(.green)
                        Button("Not relevant") {
                            Task { await store.review(result, as: "not_relevant") }
                        }
                        .tint(.gray)
                    }
                }
            }
        }
        .searchable(text: $query, prompt: "Search source, category, state")
        .listStyle(.automatic)
        .scrollContentBackground(.hidden)
        .background(AppTheme.background)
    }
}

struct ProvidersView: View {
    @Environment(FraudMonitorStore.self) private var store

    var body: some View {
        List {
            Section("Configured providers") {
                ForEach(store.dashboard.providers) { provider in
                    Button {
                        store.selectedProvider = provider
                    } label: {
                        ProviderRow(provider: provider)
                    }
                    .buttonStyle(.plain)
                }
            }

            Section("Detailed search") {
                Button {
                    store.selectedProvider = store.dashboard.detailedProvider
                } label: {
                    ProviderRow(provider: store.dashboard.detailedProvider)
                }
                .buttonStyle(.plain)
            }

            Section("Configuration") {
                Label(
                    store.dashboard.configurationValidation.isValid ? "Configuration ready" : "Configuration needs review",
                    systemImage: store.dashboard.configurationValidation.isValid ? "checkmark.seal" : "exclamationmark.triangle"
                )
                ForEach(store.dashboard.configurationValidation.issues) { issue in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(issue.provider).font(.headline)
                        Text(issue.message).font(.subheadline).foregroundStyle(.secondary)
                    }
                }
            }
        }
        .listStyle(.automatic)
        .scrollContentBackground(.hidden)
        .background(AppTheme.background)
    }
}

struct SettingsView: View {
    @Environment(FraudMonitorStore.self) private var store

    var body: some View {
        Form {
            Section("API") {
                TextField("Base URL", text: Bindable(store).baseURLText)
                Button("Reconnect") {
                    Task { await store.refresh() }
                }
            }

            Section("Scheduler") {
                Toggle(
                    "Cron enabled",
                    isOn: Binding(
                        get: { store.dashboard.schedule.enabled },
                        set: { enabled in Task { await store.setSchedule(enabled: enabled) } }
                    )
                )
                LabeledContent("Interval", value: "\(store.dashboard.schedule.intervalMinutes) min")
                LabeledContent("Last run", value: store.dashboard.schedule.lastCompletedAt.readableDate)
                LabeledContent("Next run", value: store.dashboard.schedule.nextRunAt.readableDate)
            }

            Section("Local-first boundary") {
                Label("Results stay in the local API SQLite store", systemImage: "externaldrive")
                Label("Evidence saves require analyst action", systemImage: "person.crop.circle.badge.checkmark")
                Label("Fixture mode is separate from real provider runs", systemImage: "testtube.2")
            }
        }
        .scrollContentBackground(.hidden)
        .background(AppTheme.background)
    }
}

struct RunPanel: View {
    @Environment(FraudMonitorStore.self) private var store
    @Binding var intervalText: String

    var body: some View {
        NativeCard {
            VStack(alignment: .leading, spacing: 14) {
                Text("Run control")
                    .font(.headline)
                HStack {
                    Button {
                        Task { await store.run(detailed: false) }
                    } label: {
                        Label("Run now", systemImage: "play.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(store.dashboard.runtime.isRunning)

                    Button {
                        Task { await store.run(detailed: true) }
                    } label: {
                        Label("Detailed", systemImage: "scope")
                    }
                    .buttonStyle(.bordered)
                    .disabled(store.dashboard.runtime.isRunning || store.dashboard.detailedProvider.status != "ready")
                }

                Toggle(
                    "Cron enabled",
                    isOn: Binding(
                        get: { store.dashboard.schedule.enabled },
                        set: { enabled in Task { await store.setSchedule(enabled: enabled) } }
                    )
                )

                HStack {
                    TextField("Minutes", text: $intervalText)
                        .textFieldStyle(.roundedBorder)
                    Button("Save interval") {
                        Task { await store.setSchedule(intervalMinutes: Int(intervalText)) }
                    }
                    .buttonStyle(.bordered)
                }
            }
        }
    }
}

struct LatestJobPanel: View {
    let job: MonitorJob?

    var body: some View {
        NativeCard {
            VStack(alignment: .leading, spacing: 10) {
                Text("Latest job").font(.headline)
                if let job {
                    HStack {
                        StatusBadge(text: job.status)
                        Text("\(job.resultCount) result(s)")
                            .foregroundStyle(.secondary)
                    }
                    ForEach(job.providerRunSummaries) { summary in
                        HStack {
                            Text(summary.provider.displayLabel)
                            Spacer()
                            Text("\(summary.storedResultCount)/\(summary.rawResultCount)")
                                .foregroundStyle(.secondary)
                        }
                    }
                } else {
                    Text("No run has been started yet.")
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}

struct StatusBanner: View {
    @Environment(FraudMonitorStore.self) private var store

    var body: some View {
        NativeCard {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: statusSymbol)
                    .font(.title2)
                    .foregroundStyle(statusColor)
                VStack(alignment: .leading, spacing: 4) {
                    Text(statusTitle).font(.headline)
                    Text(statusDetail).font(.subheadline).foregroundStyle(.secondary)
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
