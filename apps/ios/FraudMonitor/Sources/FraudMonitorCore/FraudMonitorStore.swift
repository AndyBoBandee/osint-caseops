import Foundation
import Observation

@MainActor
@Observable
public final class FraudMonitorStore {
    public enum LoadPhase: Equatable {
        case idle
        case loading
        case loaded
        case failed(String)
    }

    public var dashboard: DashboardData = .empty
    public var phase: LoadPhase = .idle
    public var selectedResult: NewsResult?
    public var selectedProvider: ProviderInfo?
    public var baseURLText = "http://127.0.0.1:8000"
    public var draftEvidenceNote = ""

    public init() {}

    private var client: FraudMonitorClient {
        FraudMonitorClient(baseURL: URL(string: baseURLText) ?? URL(string: "http://127.0.0.1:8000")!)
    }

    public func selectResult(_ result: NewsResult?) {
        selectedResult = result
        draftEvidenceNote = result?.evidenceAnalystNote ?? ""
    }

    public func refresh() async {
        phase = .loading
        do {
            dashboard = try await client.dashboard()
            refreshSelections()
            phase = .loaded
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    public func run(detailed: Bool) async {
        phase = .loading
        do {
            _ = try await client.runJob(detailed: detailed)
            dashboard = try await client.dashboard()
            refreshSelections()
            phase = .loaded
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    public func setSchedule(enabled: Bool? = nil, intervalMinutes: Int? = nil) async {
        do {
            _ = try await client.updateSchedule(SchedulePatch(enabled: enabled, intervalMinutes: intervalMinutes))
            dashboard = try await client.dashboard()
            refreshSelections()
            phase = .loaded
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    public func review(_ result: NewsResult, as status: String) async {
        do {
            _ = try await client.updateReview(resultID: result.id, status: status)
            dashboard = try await client.dashboard()
            refreshSelections()
            phase = .loaded
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    public func saveEvidence(_ result: NewsResult, note: String) async {
        do {
            try await client.saveEvidence(resultID: result.id, note: note)
            dashboard = try await client.dashboard()
            refreshSelections()
            if selectedResult?.id == result.id {
                draftEvidenceNote = note
            }
            phase = .loaded
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    private func refreshSelections() {
        if let selectedResult {
            self.selectedResult = dashboard.results.first { $0.id == selectedResult.id } ?? selectedResult
        }
        if let selectedProvider {
            self.selectedProvider = dashboard.providers.first { $0.id == selectedProvider.id } ?? selectedProvider
        }
    }
}
