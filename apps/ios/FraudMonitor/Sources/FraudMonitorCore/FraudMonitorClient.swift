import Foundation

public enum FraudMonitorClientError: Error, LocalizedError, Sendable {
    case invalidBaseURL
    case invalidResponse
    case httpStatus(Int, String)

    public var errorDescription: String? {
        switch self {
        case .invalidBaseURL:
            "The API base URL is not valid."
        case .invalidResponse:
            "The API returned an invalid response."
        case .httpStatus(let status, let body):
            "The API returned HTTP \(status): \(body)"
        }
    }
}

public struct FraudMonitorClient: Sendable {
    public var baseURL: URL
    public var session: URLSession
    public var decoder: JSONDecoder
    public var encoder: JSONEncoder

    public init(baseURL: URL = URL(string: "http://127.0.0.1:8000")!, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
        self.decoder = JSONDecoder()
        self.encoder = JSONEncoder()
    }

    public func dashboard() async throws -> DashboardData {
        try await request(path: "/fraud-monitor/dashboard", method: "GET")
    }

    public func apiHealth() async throws -> APIHealth {
        try await request(path: "/health", method: "GET")
    }

    public func databaseHealth() async throws -> DatabaseHealth {
        try await request(path: "/health/db", method: "GET")
    }

    public func runJob(detailed: Bool) async throws -> MonitorJob {
        let body = detailed ? ["search_mode": "detailed"] : ["search_mode": "standard"]
        return try await request(path: "/fraud-monitor/jobs", method: "POST", body: body)
    }

    public func updateSchedule(_ patch: SchedulePatch) async throws -> MonitorSchedule {
        try await request(path: "/fraud-monitor/schedule", method: "PATCH", body: patch)
    }

    public func updateReview(resultID: String, status: String) async throws -> NewsResult {
        try await request(path: "/fraud-monitor/results/\(resultID)", method: "PATCH", body: ReviewPatch(reviewStatus: status))
    }

    public func saveEvidence(resultID: String, note: String) async throws {
        let _: EmptyResponse = try await request(
            path: "/fraud-monitor/results/\(resultID)/evidence-links",
            method: "POST",
            body: ["analyst_note": note]
        )
    }

    private func request<Response: Decodable>(path: String, method: String) async throws -> Response {
        try await request(path: path, method: method, body: Optional<String>.none)
    }

    private func request<Response: Decodable, Body: Encodable>(
        path: String,
        method: String,
        body: Body?
    ) async throws -> Response {
        guard let url = URL(string: path, relativeTo: baseURL) else {
            throw FraudMonitorClientError.invalidBaseURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try encoder.encode(body)
        }
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw FraudMonitorClientError.invalidResponse
        }
        guard 200..<300 ~= httpResponse.statusCode else {
            throw FraudMonitorClientError.httpStatus(
                httpResponse.statusCode,
                String(data: data, encoding: .utf8) ?? ""
            )
        }
        if Response.self == EmptyResponse.self, data.isEmpty {
            return EmptyResponse() as! Response
        }
        return try decoder.decode(Response.self, from: data)
    }
}

private struct EmptyResponse: Decodable {}
