import SwiftUI

struct RootView: View {
    var body: some View {
        TabView {
            AccountListView()
                .tabItem {
                    Label("Portfolio", systemImage: "briefcase.fill")
                }

            SummaryRootView()
                .tabItem {
                    Label("Summary", systemImage: "chart.pie.fill")
                }

            HistoryRootView()
                .tabItem {
                    Label("History", systemImage: "chart.line.uptrend.xyaxis")
                }

            MarketInsightRootView()
                .tabItem {
                    Label("Insight", systemImage: "chart.bar.fill")
                }

            SettingsRootView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape.fill")
                }
        }
    }
}
