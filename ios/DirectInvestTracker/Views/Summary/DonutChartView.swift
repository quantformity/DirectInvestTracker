import SwiftUI
import Charts

private let palette: [Color] = [
    .blue, .green, .orange, .purple, .pink,
    .teal, .indigo, .yellow, .mint, .cyan,
    .red, Color(hue: 0.08, saturation: 0.8, brightness: 0.9),
    Color(hue: 0.55, saturation: 0.6, brightness: 0.8),
    Color(hue: 0.75, saturation: 0.7, brightness: 0.8),
]

struct DonutChartView: View {
    let group: SummaryGroup
    let positions: [EnrichedPosition]

    private var chartData: [(label: String, value: Double, color: Color)] {
        let entries: [(String, Double)]
        if positions.isEmpty {
            entries = [(group.groupKey, group.totalMTM)]
        } else {
            // Aggregate by symbol; use category name for Cash/GIC (normalises "CASH"/"Cash")
            var dict: [String: Double] = [:]
            for p in positions {
                let key = (p.category == .cash || p.category == .gic) ? p.category.rawValue : p.symbol
                dict[key, default: 0] += p.mtmReporting
            }
            entries = dict.sorted { $0.value > $1.value }.map { ($0.key, $0.value) }
        }
        return entries.enumerated().map { i, pair in
            (label: pair.0, value: pair.1, color: palette[i % palette.count])
        }
    }

    var body: some View {
        Chart(chartData, id: \.label) { item in
            SectorMark(
                angle: .value("MTM", item.value),
                innerRadius: .ratio(0.55),
                angularInset: 1.5
            )
            .foregroundStyle(item.color)
            .cornerRadius(4)
        }
        .chartLegend(.hidden)
        .overlay {
            VStack(spacing: 2) {
                Text(group.totalMTM.currencyFormatted(currency: AppSettingsStore.reportingCurrency, maximumFractionDigits: 0))
                    .font(.caption.bold())
                PnLText(value: group.totalPnL, currency: AppSettingsStore.reportingCurrency)
                    .font(.caption2)
            }
        }
    }
}
