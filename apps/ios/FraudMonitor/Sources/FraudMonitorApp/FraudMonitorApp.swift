import FraudMonitorCore
import SwiftUI

@main
struct FraudMonitorNativeApp: App {
    @State private var store = FraudMonitorStore()

    var body: some Scene {
        WindowGroup {
            AppShell()
                .environment(store)
                .tint(.cyan)
        }
    }
}

enum AppTab: String, CaseIterable, Identifiable {
    case monitor
    case trends
    case results
    case providers
    case settings

    var id: String { rawValue }

    var title: String {
        switch self {
        case .monitor: "Monitor"
        case .trends: "Trends"
        case .results: "Results"
        case .providers: "Providers"
        case .settings: "Settings"
        }
    }

    var symbol: String {
        switch self {
        case .monitor: "dot.radiowaves.left.and.right"
        case .trends: "chart.line.uptrend.xyaxis"
        case .results: "tray.full"
        case .providers: "antenna.radiowaves.left.and.right"
        case .settings: "gearshape"
        }
    }
}

struct AppShell: View {
    @State private var selectedTab: AppTab = .monitor
    @Environment(FraudMonitorStore.self) private var store

    var body: some View {
        TabView(selection: $selectedTab) {
                ForEach(AppTab.allCases) { tab in
                NavigationStack {
                    tabView(tab)
                        .navigationTitle(tab.title)
                        .toolbar {
                            ToolbarItem(placement: .primaryAction) {
                                Button {
                                    Task { await store.refresh() }
                                } label: {
                                    Label("Refresh", systemImage: "arrow.clockwise")
                                }
                            }
                        }
                }
                .tabItem {
                    Label(tab.title, systemImage: tab.symbol)
                }
                .tag(tab)
            }
        }
        .task {
            await store.refresh()
        }
        .sheet(item: selectedResultBinding) { result in
            ResultDetailSheet(result: result)
        }
        .sheet(item: selectedProviderBinding) { provider in
            ProviderDetailSheet(provider: provider)
        }
    }

    @ViewBuilder
    private func tabView(_ tab: AppTab) -> some View {
        switch tab {
        case .monitor:
            MonitorView()
        case .trends:
            TrendsView()
        case .results:
            ResultsView()
        case .providers:
            ProvidersView()
        case .settings:
            SettingsView()
        }
    }

    private var selectedResultBinding: Binding<NewsResult?> {
        Binding(
            get: { store.selectedResult },
            set: { store.selectedResult = $0 }
        )
    }

    private var selectedProviderBinding: Binding<ProviderInfo?> {
        Binding(
            get: { store.selectedProvider },
            set: { store.selectedProvider = $0 }
        )
    }
}
