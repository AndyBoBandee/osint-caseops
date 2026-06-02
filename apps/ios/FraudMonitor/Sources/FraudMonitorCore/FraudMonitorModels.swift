import Foundation

public struct APIHealth: Codable, Sendable {
    public let status: String
    public let service: String
}

public struct DatabaseHealth: Codable, Sendable {
    public let status: String
    public let database: String
}

public struct DashboardData: Codable, Sendable {
    public let keyword: String
    public let providers: [ProviderInfo]
    public let detailedProvider: ProviderInfo
    public let configurationValidation: ConfigurationValidation
    public let schedule: MonitorSchedule
    public let latestJob: MonitorJob?
    public let jobs: [MonitorJob]
    public let results: [NewsResult]
    public let resultPage: ResultPage
    public let evidenceCount: Int
    public let runtime: MonitorRuntime
    public let trendOverview: TrendOverview
    public let totalResults: Int
    public let pendingResults: Int
    public let relevantResults: Int
    public let notRelevantResults: Int

    enum CodingKeys: String, CodingKey {
        case keyword
        case providers
        case detailedProvider = "detailed_provider"
        case configurationValidation = "configuration_validation"
        case schedule
        case latestJob = "latest_job"
        case jobs
        case results
        case resultPage = "result_page"
        case evidenceCount = "evidence_count"
        case runtime
        case trendOverview = "trend_overview"
        case totalResults = "total_results"
        case pendingResults = "pending_results"
        case relevantResults = "relevant_results"
        case notRelevantResults = "not_relevant_results"
    }

    public static let empty = DashboardData(
        keyword: "fraud",
        providers: [],
        detailedProvider: .placeholder(id: "brave", displayName: "Brave News Search"),
        configurationValidation: .empty,
        schedule: .empty,
        latestJob: nil,
        jobs: [],
        results: [],
        resultPage: .empty,
        evidenceCount: 0,
        runtime: .empty,
        trendOverview: .empty,
        totalResults: 0,
        pendingResults: 0,
        relevantResults: 0,
        notRelevantResults: 0
    )
}

public struct ProviderInfo: Codable, Identifiable, Sendable {
    public var id: String { providerID }
    public let name: String
    public let providerID: String
    public let displayName: String
    public let sourceType: String
    public let sourceConfidence: String
    public let enabled: Bool
    public let defaultEnabled: Bool
    public let requiresAPIKey: Bool
    public let fixtureModeAvailable: Bool
    public let fraudCategories: [String]
    public let safetyNotes: String
    public let tier: String
    public let status: String
    public let note: String
    public let requestLimit: String
    public let timeoutSeconds: Int
    public let lastRunStatus: String
    public let lastResultCount: Int
    public let lastErrorMessage: String
    public let nextRetryAt: String
    public let lastRunAt: String
    public let lastSuccessAt: String
    public let resultsLast24h: Int

    enum CodingKeys: String, CodingKey {
        case name
        case providerID = "provider_id"
        case displayName = "display_name"
        case sourceType = "source_type"
        case sourceConfidence = "source_confidence"
        case enabled
        case defaultEnabled = "default_enabled"
        case requiresAPIKey = "requires_api_key"
        case fixtureModeAvailable = "fixture_mode_available"
        case fraudCategories = "fraud_categories"
        case safetyNotes = "safety_notes"
        case tier
        case status
        case note
        case requestLimit = "request_limit"
        case timeoutSeconds = "timeout_seconds"
        case lastRunStatus = "last_run_status"
        case lastResultCount = "last_result_count"
        case lastErrorMessage = "last_error_message"
        case nextRetryAt = "next_retry_at"
        case lastRunAt = "last_run_at"
        case lastSuccessAt = "last_success_at"
        case resultsLast24h = "results_last_24h"
    }

    public static func placeholder(id: String, displayName: String) -> ProviderInfo {
        ProviderInfo(
            name: id,
            providerID: id,
            displayName: displayName,
            sourceType: "unknown",
            sourceConfidence: "unknown",
            enabled: false,
            defaultEnabled: false,
            requiresAPIKey: false,
            fixtureModeAvailable: false,
            fraudCategories: [],
            safetyNotes: "",
            tier: "unknown",
            status: "unsupported",
            note: "",
            requestLimit: "",
            timeoutSeconds: 0,
            lastRunStatus: "",
            lastResultCount: 0,
            lastErrorMessage: "",
            nextRetryAt: "",
            lastRunAt: "",
            lastSuccessAt: "",
            resultsLast24h: 0
        )
    }
}

public struct ConfigurationValidation: Codable, Sendable {
    public let isValid: Bool
    public let fixtureMode: Bool
    public let providerCount: Int
    public let readyProviderCount: Int
    public let issues: [ConfigurationIssue]
    public let recommendations: [String]

    enum CodingKeys: String, CodingKey {
        case isValid = "is_valid"
        case fixtureMode = "fixture_mode"
        case providerCount = "provider_count"
        case readyProviderCount = "ready_provider_count"
        case issues
        case recommendations
    }

    public static let empty = ConfigurationValidation(
        isValid: false,
        fixtureMode: false,
        providerCount: 0,
        readyProviderCount: 0,
        issues: [],
        recommendations: []
    )
}

public struct ConfigurationIssue: Codable, Identifiable, Sendable {
    public var id: String { "\(provider)-\(message)" }
    public let severity: String
    public let provider: String
    public let message: String
}

public struct MonitorSchedule: Codable, Sendable {
    public let enabled: Bool
    public let intervalMinutes: Int
    public let nextRunAt: String
    public let lastStartedAt: String
    public let lastCompletedAt: String
    public let updatedAt: String

    enum CodingKeys: String, CodingKey {
        case enabled
        case intervalMinutes = "interval_minutes"
        case nextRunAt = "next_run_at"
        case lastStartedAt = "last_started_at"
        case lastCompletedAt = "last_completed_at"
        case updatedAt = "updated_at"
    }

    public static let empty = MonitorSchedule(
        enabled: false,
        intervalMinutes: 60,
        nextRunAt: "",
        lastStartedAt: "",
        lastCompletedAt: "",
        updatedAt: ""
    )
}

public struct MonitorRuntime: Codable, Sendable {
    public let isRunning: Bool
    public let readyProviderCount: Int
    public let lastErrorMessage: String
    public let lastErrorAt: String

    enum CodingKeys: String, CodingKey {
        case isRunning = "is_running"
        case readyProviderCount = "ready_provider_count"
        case lastErrorMessage = "last_error_message"
        case lastErrorAt = "last_error_at"
    }

    public static let empty = MonitorRuntime(
        isRunning: false,
        readyProviderCount: 0,
        lastErrorMessage: "",
        lastErrorAt: ""
    )
}

public struct MonitorJob: Codable, Identifiable, Sendable {
    public let id: String
    public let keyword: String
    public let triggerType: String
    public let status: String
    public let completedAt: String
    public let providerCount: Int
    public let resultCount: Int
    public let errorMessage: String
    public let providerRuns: [String]
    public let providerRunSummaries: [ProviderRunSummary]

    enum CodingKeys: String, CodingKey {
        case id
        case keyword
        case triggerType = "trigger_type"
        case status
        case completedAt = "completed_at"
        case providerCount = "provider_count"
        case resultCount = "result_count"
        case errorMessage = "error_message"
        case providerRuns = "provider_runs"
        case providerRunSummaries = "provider_run_summaries"
    }
}

public struct ProviderRunSummary: Codable, Identifiable, Sendable {
    public var id: String { provider }
    public let provider: String
    public let status: String
    public let rawResultCount: Int
    public let storedResultCount: Int
    public let filteredResultCount: Int
    public let note: String

    enum CodingKeys: String, CodingKey {
        case provider
        case status
        case rawResultCount = "raw_result_count"
        case storedResultCount = "stored_result_count"
        case filteredResultCount = "filtered_result_count"
        case note
    }
}

public struct ResultPage: Codable, Sendable {
    public let totalMatching: Int
    public let limit: Int
    public let offset: Int
    public let hasNext: Bool
    public let hasPrevious: Bool
    public let search: String
    public let sort: String
    public let reviewFilter: String
    public let providerFilter: String
    public let evidenceFilter: String

    enum CodingKeys: String, CodingKey {
        case totalMatching = "total_matching"
        case limit
        case offset
        case hasNext = "has_next"
        case hasPrevious = "has_previous"
        case search
        case sort
        case reviewFilter = "review_filter"
        case providerFilter = "provider_filter"
        case evidenceFilter = "evidence_filter"
    }

    public static let empty = ResultPage(
        totalMatching: 0,
        limit: 25,
        offset: 0,
        hasNext: false,
        hasPrevious: false,
        search: "",
        sort: "retrieved_desc",
        reviewFilter: "all",
        providerFilter: "all",
        evidenceFilter: "all"
    )
}

public struct NewsResult: Codable, Identifiable, Sendable {
    public let id: String
    public let provider: String
    public let sourceURL: String
    public let publisher: String
    public let title: String
    public let snippet: String
    public let publishedAt: String
    public let retrievedAt: String
    public let reviewStatus: String
    public let savedAsEvidence: Bool
    public let evidenceAnalystNote: String
    public let fraudCategory: String
    public let paymentRail: String
    public let victimSegment: String
    public let sourceType: String
    public let sourceConfidence: String
    public let classificationConfidence: String
    public let state: String
    public let keywordsDetected: [String]

    enum CodingKeys: String, CodingKey {
        case id
        case provider
        case sourceURL = "source_url"
        case publisher
        case title
        case snippet
        case publishedAt = "published_at"
        case retrievedAt = "retrieved_at"
        case reviewStatus = "review_status"
        case savedAsEvidence = "saved_as_evidence"
        case evidenceAnalystNote = "evidence_analyst_note"
        case fraudCategory = "fraud_category"
        case paymentRail = "payment_rail"
        case victimSegment = "victim_segment"
        case sourceType = "source_type"
        case sourceConfidence = "source_confidence"
        case classificationConfidence = "classification_confidence"
        case state
        case keywordsDetected = "keywords_detected"
    }
}

public struct TrendOverview: Codable, Sendable {
    public let generatedAt: String
    public let topCategoriesThisWeek: [TrendBucket]
    public let officialSourceAlerts: [TrendAlert]
    public let stateActivity: [TrendBucket]
    public let paymentRailMentions: [TrendBucket]
    public let emergingKeywords: [TrendBucket]
    public let providerHealth: [ProviderHealthRecord]

    enum CodingKeys: String, CodingKey {
        case generatedAt = "generated_at"
        case topCategoriesThisWeek = "top_categories_this_week"
        case officialSourceAlerts = "official_source_alerts"
        case stateActivity = "state_activity"
        case paymentRailMentions = "payment_rail_mentions"
        case emergingKeywords = "emerging_keywords"
        case providerHealth = "provider_health"
    }

    public static let empty = TrendOverview(
        generatedAt: "",
        topCategoriesThisWeek: [],
        officialSourceAlerts: [],
        stateActivity: [],
        paymentRailMentions: [],
        emergingKeywords: [],
        providerHealth: []
    )
}

public struct TrendBucket: Codable, Identifiable, Sendable {
    public var id: String { label }
    public let label: String
    public let resultCount: Int
    public let sourceCount: Int
    public let sampleTitles: [String]

    enum CodingKeys: String, CodingKey {
        case label
        case resultCount = "result_count"
        case sourceCount = "source_count"
        case sampleTitles = "sample_titles"
    }
}

public struct TrendAlert: Codable, Identifiable, Sendable {
    public var id: String { sourceURL }
    public let title: String
    public let provider: String
    public let sourceType: String
    public let sourceConfidence: String
    public let fraudCategory: String
    public let state: String
    public let publishedDate: String
    public let sourceURL: String

    enum CodingKeys: String, CodingKey {
        case title
        case provider
        case sourceType = "source_type"
        case sourceConfidence = "source_confidence"
        case fraudCategory = "fraud_category"
        case state
        case publishedDate = "published_date"
        case sourceURL = "source_url"
    }
}

public struct ProviderHealthRecord: Codable, Identifiable, Sendable {
    public var id: String { provider }
    public let provider: String
    public let displayName: String
    public let sourceType: String
    public let sourceConfidence: String
    public let lastRunAt: String
    public let lastSuccessAt: String
    public let lastError: String
    public let resultsLast24h: Int
    public let enabled: Bool
    public let defaultEnabled: Bool
    public let fixtureModeAvailable: Bool
    public let requiresAPIKey: Bool
    public let tier: String

    enum CodingKeys: String, CodingKey {
        case provider
        case displayName = "display_name"
        case sourceType = "source_type"
        case sourceConfidence = "source_confidence"
        case lastRunAt = "last_run_at"
        case lastSuccessAt = "last_success_at"
        case lastError = "last_error"
        case resultsLast24h = "results_last_24h"
        case enabled
        case defaultEnabled = "default_enabled"
        case fixtureModeAvailable = "fixture_mode_available"
        case requiresAPIKey = "requires_api_key"
        case tier
    }
}

public struct ReviewPatch: Codable, Sendable {
    public let reviewStatus: String

    enum CodingKeys: String, CodingKey {
        case reviewStatus = "review_status"
    }

    public init(reviewStatus: String) {
        self.reviewStatus = reviewStatus
    }
}

public struct SchedulePatch: Codable, Sendable {
    public let enabled: Bool?
    public let intervalMinutes: Int?

    enum CodingKeys: String, CodingKey {
        case enabled
        case intervalMinutes = "interval_minutes"
    }

    public init(enabled: Bool? = nil, intervalMinutes: Int? = nil) {
        self.enabled = enabled
        self.intervalMinutes = intervalMinutes
    }
}
