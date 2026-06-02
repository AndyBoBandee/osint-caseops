import FraudMonitorCore
import Foundation
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
    @State private var showingDeleteAllConfirmation = false

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
                    QueueSummaryStrip(results: filteredResults)
                        .padding(.horizontal, 16)

                    reviewToolbar

                    List(selection: resultSelection) {
                        ForEach(filteredResults) { result in
                            TriageLeadRow(result: result)
                                .tag(result.id)
                        }
                    }
                    .listStyle(.inset)
                    .searchable(text: $query, prompt: "Search source, category, state")
                    .accessibilityLabel("Review queue")
                    .accessibilityHint("Use the arrow keys to select a lead, then use the inspector or Review menu actions.")
                }
                .frame(minWidth: 520)

                ResultInspectorView(result: selectedResult)
                    .frame(minWidth: 520)
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
        .alert("Delete all queue results?", isPresented: $showingDeleteAllConfirmation) {
            Button("Delete All", role: .destructive) {
                Task { await store.deleteAllResults() }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This removes every stored Review Queue result for the local monitor case, including saved evidence links and notes attached to those queue items.")
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

            Button(role: .destructive) {
                showingDeleteAllConfirmation = true
            } label: {
                Label(store.isDeletingQueue ? "Deleting" : "Delete All", systemImage: "trash")
            }
            .disabled(store.dashboard.results.isEmpty || store.isDeletingQueue)
            .accessibilityLabel("Delete all queue results")
            .accessibilityHint("Shows a confirmation before removing every stored Review Queue result.")

            if let selectedResult {
                Text(selectedResult.shortSourceLabel)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .textSelection(.enabled)
                    .accessibilityLabel("Selected source")
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
}

struct QueueSummaryStrip: View {
    let results: [NewsResult]

    var body: some View {
        HStack(spacing: 10) {
            QueueSummaryItem(title: "Pending", value: count(reviewStatus: "pending"), symbol: "clock")
            QueueSummaryItem(title: "Relevant", value: count(reviewStatus: "relevant"), symbol: "checkmark.circle")
            QueueSummaryItem(title: "Evidence", value: results.filter(\.savedAsEvidence).count, symbol: "link")
            QueueSummaryItem(title: "Needs Classification", value: results.filter(\.needsClassification).count, symbol: "tag")
            QueueSummaryItem(title: "Official/High", value: results.filter(\.isOfficialOrHighConfidence).count, symbol: "checkmark.shield")
            Spacer(minLength: 0)
        }
        .accessibilityElement(children: .contain)
    }

    private func count(reviewStatus: String) -> Int {
        results.filter { $0.reviewStatus == reviewStatus }.count
    }
}

struct QueueSummaryItem: View {
    let title: String
    let value: Int
    let symbol: String

    var body: some View {
        HStack(spacing: 7) {
            Image(systemName: symbol)
                .foregroundStyle(.cyan)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 1) {
                Text("\(value)")
                    .font(.headline)
                Text(title)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(.secondary.opacity(0.10), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .accessibilityLabel(title)
        .accessibilityValue("\(value)")
    }
}

struct TriageLeadRow: View {
    let result: NewsResult

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(result.displayTitle)
                    .font(.callout.weight(.semibold))
                    .lineLimit(2)
                Spacer(minLength: 8)
                Text(result.reviewStatus.displayLabel)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(result.reviewStatus == "relevant" ? .green : .secondary)
            }

            HStack(spacing: 8) {
                Text(result.publisherLabel)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                Text(result.publishedAt.readableDate)
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                    .lineLimit(1)
                if result.shouldShowProvider {
                    Text(result.provider.displayLabel)
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                        .lineLimit(1)
                }
            }

            Text(result.triageSummary)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(2)

            HStack(spacing: 6) {
                CompactStatusPill(result.categoryCue, symbol: result.needsClassification ? "tag" : "tag.fill")
                CompactStatusPill(result.sourceConfidence.displayLabel, symbol: result.isOfficialOrHighConfidence ? "checkmark.shield" : "antenna.radiowaves.left.and.right")
                if !result.state.isEmpty {
                    CompactStatusPill(result.state, symbol: "map")
                }
                if result.savedAsEvidence {
                    CompactStatusPill("Evidence saved", symbol: "link")
                }
                Spacer(minLength: 0)
            }
        }
        .padding(.vertical, 8)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(result.displayTitle)
        .accessibilityValue("\(result.publisherLabel), \(result.categoryCue), \(result.reviewStatus.displayLabel)")
    }
}

struct ResultInspectorView: View {
    @Environment(FraudMonitorStore.self) private var store
    let result: NewsResult?

    var body: some View {
        ScrollView {
            if let result {
                VStack(alignment: .leading, spacing: 16) {
                    ResultInspectorHeader(result: result)

                    MacCard("Source", symbol: "link") {
                        VStack(alignment: .leading, spacing: 10) {
                            DetailRow("Publisher", result.publisherLabel)
                            DetailRow("Readable URL", result.shortSourceLabel)
                            DisclosureGroup("Full source URL") {
                                Text(result.sourceURL)
                                    .font(.caption.monospaced())
                                    .foregroundStyle(.secondary)
                                    .textSelection(.enabled)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                            Grid(alignment: .leading, horizontalSpacing: 28, verticalSpacing: 8) {
                                GridRow {
                                    DetailRow("Published", result.publishedAt.readableDate)
                                    DetailRow("Retrieved", result.retrievedAt.readableDate)
                                }
                            }
                            Text(result.cleanedSnippet.isEmpty ? "No provider snippet returned." : result.cleanedSnippet)
                                .foregroundStyle(.secondary)
                                .textSelection(.enabled)
                        }
                    }

                    MacCard("Classification & Credibility", symbol: "tag") {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack(spacing: 8) {
                                CompactStatusPill(result.categoryCue, symbol: result.needsClassification ? "tag" : "tag.fill")
                                CompactStatusPill(result.sourceConfidence.displayLabel, symbol: result.isOfficialOrHighConfidence ? "checkmark.shield" : "antenna.radiowaves.left.and.right")
                                CompactStatusPill(result.classificationConfidence.displayLabel, symbol: "dial.low")
                            }

                            Text(result.queueReason)
                                .font(.caption)
                                .foregroundStyle(.secondary)

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
                                GridRow {
                                    DetailRow("State", result.state.isEmpty ? "Unknown" : result.state)
                                    DetailRow("Provider", result.provider.displayLabel)
                                }
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

struct ResultInspectorHeader: View {
    let result: NewsResult

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: "doc.text.magnifyingglass")
                    .font(.title2)
                    .foregroundStyle(.cyan)
                    .frame(width: 30, height: 30)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 5) {
                    Text(result.displayTitle)
                        .font(.title2.bold())
                        .lineLimit(3)
                        .textSelection(.enabled)
                    Text(result.publisherLabel)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                    Text(result.shortSourceLabel)
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                        .lineLimit(1)
                        .textSelection(.enabled)
                }
                Spacer()
            }
            HStack(spacing: 6) {
                CompactStatusPill(result.reviewStatus.displayLabel, symbol: result.reviewSymbol)
                CompactStatusPill(result.savedAsEvidence ? "Evidence saved" : "Evidence not saved", symbol: result.savedAsEvidence ? "link" : "link.badge.plus")
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Result detail")
        .accessibilityValue("\(result.displayTitle), \(result.publisherLabel)")
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

extension NewsResult {
    var displayTitle: String {
        title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? shortSourceLabel : title.cleanedHTMLText
    }

    var publisherLabel: String {
        publisher.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? provider.displayLabel : publisher.cleanedHTMLText
    }

    var cleanedSnippet: String {
        snippet.cleanedHTMLText
    }

    var categoryCue: String {
        needsClassification ? "Needs classification" : fraudCategory.displayLabel
    }

    var needsClassification: Bool {
        fraudCategory.isEmpty || fraudCategory == "unknown"
    }

    var isOfficialOrHighConfidence: Bool {
        sourceConfidence == "high" || sourceType.hasPrefix("official_")
    }

    var shouldShowProvider: Bool {
        provider != "google_news_rss" && provider != publisher
    }

    var shortSourceLabel: String {
        guard let components = URLComponents(string: sourceURL), let host = components.host else {
            return sourceURL
        }
        let cleanHost = host.replacingOccurrences(of: "www.", with: "")
        if cleanHost == "news.google.com", components.path.hasPrefix("/rss/articles") {
            return "Google News RSS link"
        }
        let path = components.path
        if path.isEmpty || path == "/" {
            return cleanHost
        }
        let trimmedPath = path.count > 48 ? "\(path.prefix(45))..." : path
        return "\(cleanHost)\(trimmedPath)"
    }

    var triageSummary: String {
        cleanedSnippet.isEmpty ? queueReason : cleanedSnippet
    }

    var queueReason: String {
        var cues: [String] = []
        cues.append(needsClassification ? "Needs analyst classification" : "Classified as \(fraudCategory.displayLabel)")
        cues.append(isOfficialOrHighConfidence ? "Higher-confidence source" : "Public-source lead")
        if !state.isEmpty {
            cues.append("State: \(state)")
        }
        if paymentRail != "unknown" && !paymentRail.isEmpty {
            cues.append("Payment rail: \(paymentRail.displayLabel)")
        }
        return cues.joined(separator: "; ")
    }

    var reviewSymbol: String {
        switch reviewStatus {
        case "relevant": "checkmark.circle"
        case "not_relevant": "xmark.circle"
        default: "clock"
        }
    }
}

extension String {
    var cleanedHTMLText: String {
        var text = replacingOccurrences(of: "<[^>]+>", with: " ", options: .regularExpression)
        let replacements = [
            "&nbsp;": " ",
            "&amp;": "&",
            "&quot;": "\"",
            "&#39;": "'",
            "&lt;": "<",
            "&gt;": ">",
        ]
        for (entity, value) in replacements {
            text = text.replacingOccurrences(of: entity, with: value)
        }
        return text.split(separator: " ").joined(separator: " ")
    }
}
