import FraudMonitorCore
import AppKit
import SwiftUI

@main
struct FraudMonitorMacApp: App {
    @NSApplicationDelegateAdaptor(MacAppDelegate.self) private var appDelegate
    @State private var store = FraudMonitorStore()

    var body: some Scene {
        WindowGroup("Fraud Monitor") {
            MacWorkspaceView()
                .environment(store)
                .frame(minWidth: 1120, minHeight: 720)
        }
        .commands {
            CommandMenu("Monitor") {
                Button("Refresh") {
                    Task { await store.refresh() }
                }
                .keyboardShortcut("r", modifiers: [.command])

                Button("Run Now") {
                    Task { await store.run(detailed: false) }
                }
                .keyboardShortcut("r", modifiers: [.command, .shift])
                .disabled(store.dashboard.runtime.isRunning)

                Button("Detailed Run") {
                    Task { await store.run(detailed: true) }
                }
                .keyboardShortcut("d", modifiers: [.command, .shift])
                .disabled(store.dashboard.runtime.isRunning || store.dashboard.detailedProvider.status != "ready")
            }

            CommandMenu("Review") {
                Button("Mark Relevant") {
                    guard let result = store.selectedResult else { return }
                    Task { await store.review(result, as: "relevant") }
                }
                .keyboardShortcut("1", modifiers: [.command])
                .disabled(store.selectedResult == nil)

                Button("Mark Not Relevant") {
                    guard let result = store.selectedResult else { return }
                    Task { await store.review(result, as: "not_relevant") }
                }
                .keyboardShortcut("0", modifiers: [.command])
                .disabled(store.selectedResult == nil)

                Button("Save Evidence Note") {
                    guard let result = store.selectedResult else { return }
                    Task { await store.saveEvidence(result, note: store.draftEvidenceNote) }
                }
                .keyboardShortcut("s", modifiers: [.command])
                .disabled(store.selectedResult == nil || store.draftEvidenceNote.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }

        Settings {
            MacSettingsView()
                .environment(store)
                .frame(width: 520)
                .padding()
        }
    }
}

final class MacAppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
}

enum MacSection: String, CaseIterable, Identifiable {
    case monitor
    case review
    case trends
    case providers
    case settings

    var id: String { rawValue }

    var title: String {
        switch self {
        case .monitor: "Monitor"
        case .review: "Review Queue"
        case .trends: "Trends"
        case .providers: "Providers"
        case .settings: "Settings"
        }
    }

    var symbol: String {
        switch self {
        case .monitor: "dot.radiowaves.left.and.right"
        case .review: "tray.full"
        case .trends: "chart.line.uptrend.xyaxis"
        case .providers: "antenna.radiowaves.left.and.right"
        case .settings: "gearshape"
        }
    }
}
