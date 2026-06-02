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

    public enum BackendConnectionState: Equatable {
        case unknown
        case checking
        case connected
        case degraded(String)
        case offline(String)
    }

    public var dashboard: DashboardData = .empty
    public var phase: LoadPhase = .idle
    public var selectedResult: NewsResult?
    public var selectedResultID: String?
    public var selectedProvider: ProviderInfo?
    public var baseURLText = "http://127.0.0.1:8000"
    public var draftEvidenceNote = ""
    public var backendConnectionState: BackendConnectionState = .unknown
    public var apiHealth: APIHealth?
    public var databaseHealth: DatabaseHealth?
    public var lastBackendCheckText = "Never"
    public var isDeletingQueue = false

    public let apiLaunchCommand = "make api"
    public let fixtureAPILaunchCommand = """
    OSINT_CASEOPS_DATA_DIR=/tmp/osint-caseops-mac-data \\
    OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER=1 \\
    OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS=fixture \\
    make api
    """
    public let macRunCommand = "make mac-run"

    public init() {}

    private var client: FraudMonitorClient {
        FraudMonitorClient(baseURL: URL(string: baseURLText) ?? URL(string: "http://127.0.0.1:8000")!)
    }

    public func selectResult(_ result: NewsResult?) {
        selectedResult = result
        selectedResultID = result?.id
        draftEvidenceNote = result?.evidenceAnalystNote ?? ""
    }

    public func selectResult(id: String?) {
        selectedResultID = id
        selectedResult = dashboard.results.first { $0.id == id }
        draftEvidenceNote = selectedResult?.evidenceAnalystNote ?? ""
    }

    public func checkBackendHealth() async {
        backendConnectionState = .checking
        do {
            async let api = client.apiHealth()
            async let database = client.databaseHealth()
            let (apiHealth, databaseHealth) = try await (api, database)
            self.apiHealth = apiHealth
            self.databaseHealth = databaseHealth
            lastBackendCheckText = Date.now.formatted(date: .omitted, time: .shortened)
            if apiHealth.status == "ok" && databaseHealth.status == "ok" {
                backendConnectionState = .connected
            } else {
                backendConnectionState = .degraded("API: \(apiHealth.status), database: \(databaseHealth.status)")
            }
        } catch {
            apiHealth = nil
            databaseHealth = nil
            lastBackendCheckText = Date.now.formatted(date: .omitted, time: .shortened)
            backendConnectionState = .offline(error.localizedDescription)
        }
    }

    public func refresh() async {
        phase = .loading
        await checkBackendHealth()
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
        await checkBackendHealth()
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

    public func deleteAllResults() async {
        isDeletingQueue = true
        defer { isDeletingQueue = false }
        do {
            _ = try await client.deleteAllResults()
            dashboard = try await client.dashboard()
            selectResult(nil)
            phase = .loaded
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }

    private func refreshSelections() {
        if let selectedResultID {
            self.selectedResult = dashboard.results.first { $0.id == selectedResultID }
            if selectedResult == nil {
                self.selectedResultID = nil
                draftEvidenceNote = ""
            } else {
                draftEvidenceNote = selectedResult?.evidenceAnalystNote ?? draftEvidenceNote
            }
        }
        if let selectedProvider {
            self.selectedProvider = dashboard.providers.first { $0.id == selectedProvider.id } ?? selectedProvider
        }
    }
}
