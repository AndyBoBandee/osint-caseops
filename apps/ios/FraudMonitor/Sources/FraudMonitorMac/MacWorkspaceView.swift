import FraudMonitorCore
import SwiftUI

struct MacWorkspaceView: View {
    @Environment(FraudMonitorStore.self) private var store
    @SceneStorage("selectedSection") private var selectedSectionID = MacSection.monitor.rawValue

    private var selectedSection: Binding<MacSection> {
        Binding(
            get: { MacSection(rawValue: selectedSectionID) ?? .monitor },
            set: { selectedSectionID = $0.rawValue }
        )
    }

    var body: some View {
        NavigationSplitView {
            List(selection: selectedSection) {
                Section("Workspace") {
                    ForEach(MacSection.allCases) { section in
                        Label(section.title, systemImage: section.symbol)
                            .tag(section)
                    }
                }
            }
            .listStyle(.sidebar)
            .navigationTitle("Fraud Monitor")
        } detail: {
            sectionView(selectedSection.wrappedValue)
                .toolbar {
                    ToolbarItemGroup(placement: .primaryAction) {
                        Button {
                            Task { await store.refresh() }
                        } label: {
                            Label("Refresh", systemImage: "arrow.clockwise")
                        }

                        Button {
                            Task { await store.run(detailed: false) }
                        } label: {
                            Label("Run Now", systemImage: "play.fill")
                        }
                        .disabled(store.dashboard.runtime.isRunning)

                        Button {
                            Task { await store.run(detailed: true) }
                        } label: {
                            Label("Detailed Run", systemImage: "scope")
                        }
                        .disabled(store.dashboard.runtime.isRunning || store.dashboard.detailedProvider.status != "ready")
                    }
                }
        }
        .task {
            await store.refresh()
        }
    }

    @ViewBuilder
    private func sectionView(_ section: MacSection) -> some View {
        switch section {
        case .monitor:
            MacMonitorView()
        case .review:
            MacReviewQueueView()
        case .trends:
            MacTrendsView()
        case .providers:
            MacProvidersView()
        case .settings:
            MacSettingsOverviewView()
        }
    }
}

struct MacMonitorView: View {
    @Environment(FraudMonitorStore.self) private var store
    @State private var intervalText = "60"

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                MacHeader(
                    title: "Monitor",
                    subtitle: "Local-first fraud intelligence collection and review.",
                    symbol: "dot.radiowaves.left.and.right"
                )
                MacConnectionBanner()
                MetricGridView(dashboard: store.dashboard)

                HStack(alignment: .top, spacing: 16) {
                    MacCard("Run Control", symbol: "play.circle") {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                Button {
                                    Task { await store.run(detailed: false) }
                                } label: {
                                    Label("Run Now", systemImage: "play.fill")
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
                                TextField("Interval minutes", text: $intervalText)
                                    .frame(width: 120)
                                Button("Save Interval") {
                                    Task { await store.setSchedule(intervalMinutes: Int(intervalText)) }
                                }
                            }
                        }
                    }

                    MacCard("Latest Job", symbol: "clock.arrow.circlepath") {
                        if let job = store.dashboard.latestJob {
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    StatusPill(job.status)
                                    Text("\(job.resultCount) stored result(s)")
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
                            }
                        } else {
                            ContentUnavailableView("No run has been started yet", systemImage: "clock")
                        }
                    }
                }
            }
            .padding(24)
        }
        .onChange(of: store.dashboard.schedule.intervalMinutes) { _, value in
            intervalText = String(value)
        }
    }
}

struct MacReviewQueueView: View {
    @Environment(FraudMonitorStore.self) private var store
    @State private var query = ""
    @State private var reviewFilter = "all"

    private var filteredResults: [NewsResult] {
        store.dashboard.results.filter { result in
            let matchesReview = reviewFilter == "all" || result.reviewStatus == reviewFilter
            let searchText = "\(result.title) \(result.publisher) \(result.provider) \(result.fraudCategory) \(result.paymentRail) \(result.state)".lowercased()
            let matchesQuery = query.isEmpty || searchText.contains(query.lowercased())
            return matchesReview && matchesQuery
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            MacHeader(
                title: "Review Queue",
                subtitle: "\(filteredResults.count) matching result(s)",
                symbol: "tray.full"
            )
            .padding(24)

            HSplitView {
                VStack(spacing: 12) {
                    Picker("Review", selection: $reviewFilter) {
                        Text("All").tag("all")
                        Text("Pending").tag("pending")
                        Text("Relevant").tag("relevant")
                        Text("Not Relevant").tag("not_relevant")
                    }
                    .pickerStyle(.segmented)
                    .padding(.horizontal, 16)

                    List(filteredResults, selection: resultSelection) { result in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text(result.title.isEmpty ? result.sourceURL : result.title)
                                    .font(.headline)
                                    .lineLimit(2)
                                Spacer()
                                StatusPill(result.reviewStatus.displayLabel)
                            }
                            Text(result.publisher.isEmpty ? result.provider.displayLabel : result.publisher)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Text(result.snippet.isEmpty ? "No provider snippet returned." : result.snippet)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                            HStack {
                                StatusPill(result.fraudCategory.displayLabel)
                                StatusPill(result.paymentRail.displayLabel)
                                StatusPill(result.sourceConfidence)
                            }
                        }
                        .padding(.vertical, 4)
                        .tag(result.id)
                    }
                    .searchable(text: $query, prompt: "Search source, category, state")
                }
                .frame(minWidth: 420)

                ResultInspectorView(result: selectedResult)
                    .frame(minWidth: 460)
            }
        }
    }

    private var selectedResult: NewsResult? {
        guard let id = store.selectedResult?.id else { return nil }
        return store.dashboard.results.first { $0.id == id } ?? store.selectedResult
    }

    private var resultSelection: Binding<String?> {
        Binding(
            get: { store.selectedResult?.id },
            set: { id in
                store.selectResult(store.dashboard.results.first { $0.id == id })
            }
        )
    }
}

struct ResultInspectorView: View {
    @Environment(FraudMonitorStore.self) private var store
    let result: NewsResult?

    var body: some View {
        ScrollView {
            if let result {
                VStack(alignment: .leading, spacing: 16) {
                    MacHeader(title: "Result Detail", subtitle: result.publisher, symbol: "doc.text.magnifyingglass")

                    MacCard("Source", symbol: "link") {
                        VStack(alignment: .leading, spacing: 10) {
                            Text(result.title.isEmpty ? result.sourceURL : result.title)
                                .font(.headline)
                            DetailRow("Provider", result.provider.displayLabel)
                            DetailRow("Publisher", result.publisher)
                            DetailRow("URL", result.sourceURL)
                            Text(result.snippet.isEmpty ? "No provider snippet returned." : result.snippet)
                                .foregroundStyle(.secondary)
                        }
                    }

                    MacCard("Classification", symbol: "tag") {
                        Grid(alignment: .leading, horizontalSpacing: 28, verticalSpacing: 10) {
                            GridRow {
                                DetailRow("Category", result.fraudCategory.displayLabel)
                                DetailRow("Payment rail", result.paymentRail.displayLabel)
                            }
                            GridRow {
                                DetailRow("Victim segment", result.victimSegment.displayLabel)
                                DetailRow("Confidence", result.classificationConfidence)
                            }
                            GridRow {
                                DetailRow("Source type", result.sourceType.displayLabel)
                                DetailRow("Source confidence", result.sourceConfidence)
                            }
                        }
                    }

                    MacCard("Review Actions", symbol: "checkmark.circle") {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                Button("Mark Relevant") {
                                    Task { await store.review(result, as: "relevant") }
                                }
                                .keyboardShortcut("1", modifiers: [.command])

                                Button("Mark Not Relevant") {
                                    Task { await store.review(result, as: "not_relevant") }
                                }
                                .keyboardShortcut("0", modifiers: [.command])
                            }

                            EvidenceNoteEditor(store: store, result: result)
                        }
                    }
                }
                .padding(24)
            } else {
                ContentUnavailableView("Select a result", systemImage: "tray.full", description: Text("Choose a result from the review queue to inspect source metadata, classification, and evidence notes."))
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
    }
}

struct EvidenceNoteEditor: View {
    @Bindable var store: FraudMonitorStore
    let result: NewsResult

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Evidence note")
                .font(.caption)
                .foregroundStyle(.secondary)
            TextEditor(text: $store.draftEvidenceNote)
                .font(.body)
                .frame(minHeight: 110)
                .overlay {
                    RoundedRectangle(cornerRadius: 6)
                        .stroke(.quaternary)
                }
            Button {
                Task { await store.saveEvidence(result, note: store.draftEvidenceNote) }
            } label: {
                Label("Save Evidence Note", systemImage: "square.and.arrow.down")
            }
            .buttonStyle(.borderedProminent)
            .disabled(store.draftEvidenceNote.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
    }
}
