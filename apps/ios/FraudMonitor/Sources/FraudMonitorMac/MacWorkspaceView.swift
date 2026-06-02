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
                        .accessibilityLabel("Refresh dashboard")

                        Button {
                            Task { await store.run(detailed: false) }
                        } label: {
                            Label("Run Now", systemImage: "play.fill")
                        }
                        .disabled(store.dashboard.runtime.isRunning)
                        .accessibilityLabel("Run standard provider scan")

                        Button {
                            Task { await store.run(detailed: true) }
                        } label: {
                            Label("Detailed Run", systemImage: "scope")
                        }
                        .disabled(store.dashboard.runtime.isRunning || store.dashboard.detailedProvider.status != "ready")
                        .accessibilityLabel("Run detailed provider scan")
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
                VStack(spacing: 10) {
                    reviewToolbar

                    Table(filteredResults, selection: resultSelection) {
                        TableColumn("Source") { result in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(result.title.isEmpty ? result.sourceURL : result.title)
                                    .font(.callout.weight(.medium))
                                    .lineLimit(1)
                                Text(result.publisher.isEmpty ? result.provider.displayLabel : result.publisher)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .lineLimit(1)
                            }
                            .accessibilityElement(children: .combine)
                            .accessibilityLabel("Source \(result.title.isEmpty ? result.sourceURL : result.title)")
                            .accessibilityValue(result.publisher.isEmpty ? result.provider.displayLabel : result.publisher)
                        }
                        .width(min: 240, ideal: 340)

                        TableColumn("Provider") { result in
                            Text(result.provider.displayLabel)
                                .lineLimit(1)
                                .accessibilityLabel("Provider \(result.provider.displayLabel)")
                        }
                        .width(min: 95, ideal: 120)

                        TableColumn("Review") { result in
                            CompactStatusPill(result.reviewStatus, symbol: reviewSymbol(for: result.reviewStatus))
                                .accessibilityLabel("Review status")
                                .accessibilityValue(result.reviewStatus.displayLabel)
                        }
                        .width(min: 100, ideal: 120)

                        TableColumn("Category") { result in
                            Text(result.fraudCategory.displayLabel)
                                .lineLimit(1)
                                .accessibilityLabel("Category \(result.fraudCategory.displayLabel)")
                        }
                        .width(min: 120, ideal: 150)

                        TableColumn("Confidence") { result in
                            Text(result.sourceConfidence.displayLabel)
                                .lineLimit(1)
                                .accessibilityLabel("Source confidence \(result.sourceConfidence.displayLabel)")
                        }
                        .width(min: 90, ideal: 110)

                        TableColumn("State/Rail") { result in
                            Text("\(result.state.isEmpty ? "Unknown" : result.state) / \(result.paymentRail.displayLabel)")
                                .lineLimit(1)
                                .accessibilityLabel("State and payment rail")
                                .accessibilityValue("\(result.state.isEmpty ? "Unknown" : result.state), \(result.paymentRail.displayLabel)")
                        }
                        .width(min: 105, ideal: 130)

                        TableColumn("Evidence") { result in
                            CompactStatusPill(result.savedAsEvidence ? "Saved" : "Not saved", symbol: result.savedAsEvidence ? "link" : "link.badge.plus")
                                .accessibilityLabel("Evidence state")
                                .accessibilityValue(result.savedAsEvidence ? "Saved" : "Not saved")
                        }
                        .width(min: 90, ideal: 105)

                        TableColumn("Retrieved") { result in
                            Text(result.retrievedAt.readableDate)
                                .lineLimit(1)
                                .accessibilityLabel("Retrieved")
                                .accessibilityValue(result.retrievedAt.readableDate)
                        }
                        .width(min: 140, ideal: 170)
                    }
                    .searchable(text: $query, prompt: "Search source, category, state")
                    .accessibilityLabel("Review queue table")
                    .accessibilityHint("Use the arrow keys to select a result, then use the inspector or Review menu actions.")
                }
                .frame(minWidth: 720)

                ResultInspectorView(result: selectedResult)
                    .frame(minWidth: 460)
            }
        }
        .onChange(of: filteredResults.map(\.id)) { _, ids in
            if let selectedID = store.selectedResultID, ids.contains(selectedID) {
                return
            }
            store.selectResult(id: ids.first)
        }
        .onAppear {
            if store.selectedResultID == nil {
                store.selectResult(id: filteredResults.first?.id)
            }
        }
    }

    private var reviewToolbar: some View {
        HStack(spacing: 12) {
            Picker("Review filter", selection: $reviewFilter) {
                Text("All").tag("all")
                Text("Pending").tag("pending")
                Text("Relevant").tag("relevant")
                Text("Not Relevant").tag("not_relevant")
            }
            .pickerStyle(.segmented)
            .frame(maxWidth: 430)
            .accessibilityLabel("Review status filter")

            Spacer()

            if let selectedResult {
                Text(selectedResult.id)
                    .font(.caption2.monospaced())
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .textSelection(.enabled)
                    .accessibilityLabel("Selected result identifier")
            }
        }
        .padding(.horizontal, 16)
    }

    private var selectedResult: NewsResult? {
        guard let id = store.selectedResultID else { return nil }
        return store.dashboard.results.first { $0.id == id } ?? store.selectedResult
    }

    private var resultSelection: Binding<String?> {
        Binding(
            get: { store.selectedResultID },
            set: { store.selectResult(id: $0) }
        )
    }

    private func reviewSymbol(for status: String) -> String {
        switch status {
        case "relevant": "checkmark.circle"
        case "not_relevant": "xmark.circle"
        default: "clock"
        }
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
                                .textSelection(.enabled)
                            DetailRow("Provider", result.provider.displayLabel)
                            DetailRow("Publisher", result.publisher)
                            DetailRow("URL", result.sourceURL)
                            if !result.publishedAt.isEmpty || !result.retrievedAt.isEmpty {
                                Grid(alignment: .leading, horizontalSpacing: 28, verticalSpacing: 8) {
                                    GridRow {
                                        DetailRow("Published", result.publishedAt.readableDate)
                                        DetailRow("Retrieved", result.retrievedAt.readableDate)
                                    }
                                }
                            }
                            Text(result.snippet.isEmpty ? "No provider snippet returned." : result.snippet)
                                .foregroundStyle(.secondary)
                                .textSelection(.enabled)
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
                                Button {
                                    Task { await store.review(result, as: "relevant") }
                                } label: {
                                    Label("Mark Relevant", systemImage: "checkmark.circle")
                                }
                                .keyboardShortcut("1", modifiers: [.command])
                                .accessibilityLabel("Mark selected result relevant")

                                Button {
                                    Task { await store.review(result, as: "not_relevant") }
                                } label: {
                                    Label("Mark Not Relevant", systemImage: "xmark.circle")
                                }
                                .keyboardShortcut("0", modifiers: [.command])
                                .accessibilityLabel("Mark selected result not relevant")

                                Spacer()
                                CompactStatusPill(result.savedAsEvidence ? "Evidence saved" : "Evidence not saved", symbol: result.savedAsEvidence ? "link" : "link.badge.plus")
                            }

                            EvidenceNoteEditor(store: store, result: result)
                        }
                    }
                }
                .padding(24)
                .accessibilityElement(children: .contain)
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
                .accessibilityLabel("Evidence note editor")
                .accessibilityHint("Edit the analyst note saved with this source link.")
            if result.savedAsEvidence, !result.evidenceAnalystNote.isEmpty {
                Text("Saved note: \(result.evidenceAnalystNote)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                    .textSelection(.enabled)
                    .accessibilityLabel("Saved evidence note")
            }
            Button {
                Task { await store.saveEvidence(result, note: store.draftEvidenceNote) }
            } label: {
                Label("Save Evidence Note", systemImage: "square.and.arrow.down")
            }
            .buttonStyle(.borderedProminent)
            .disabled(store.draftEvidenceNote.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            .accessibilityLabel("Save evidence note")
            .accessibilityHint("Saves the current analyst note as evidence for the selected result.")
        }
    }
}
