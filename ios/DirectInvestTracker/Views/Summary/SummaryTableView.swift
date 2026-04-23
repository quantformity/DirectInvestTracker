import SwiftUI

struct SummaryTableView: View {
    let positions: [EnrichedPosition]
    let reportingCurrency: String

    private let defaultVisible = 3
    @State private var expanded = false

    private struct AggRow: Identifiable {
        let id: String   // symbol
        let symbol: String
        let mtmReporting: Double
        let pnlReporting: Double
        let proportion: Double
    }

    private var aggregated: [AggRow] {
        var dict: [String: (mtm: Double, pnl: Double, prop: Double)] = [:]
        for p in positions {
            // Use category name for Cash/GIC to normalise symbol variants ("CASH", "Cash", etc.)
            let key = (p.category == .cash || p.category == .gic) ? p.category.rawValue : p.symbol
            let e = dict[key] ?? (0, 0, 0)
            dict[key] = (e.mtm + p.mtmReporting, e.pnl + p.pnlReporting, e.prop + p.proportion)
        }
        return dict.map { sym, v in AggRow(id: sym, symbol: sym, mtmReporting: v.mtm, pnlReporting: v.pnl, proportion: v.prop) }
                   .sorted { $0.mtmReporting > $1.mtmReporting }
    }

    private var visibleRows: [AggRow] {
        expanded ? aggregated : Array(aggregated.prefix(defaultVisible))
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Symbol").frame(maxWidth: .infinity, alignment: .leading)
                Text("MTM / PnL").frame(maxWidth: .infinity, alignment: .trailing)
                Text("Wt%").frame(width: 44, alignment: .trailing)
            }
            .font(.caption)
            .foregroundStyle(.secondary)
            .padding(.bottom, 4)

            Divider()

            ForEach(visibleRows) { row in
                HStack(alignment: .center) {
                    Text(row.symbol)
                        .font(.caption)
                        .fontWeight(.medium)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    VStack(alignment: .trailing, spacing: 1) {
                        Text(row.mtmReporting.currencyFormatted(currency: reportingCurrency, maximumFractionDigits: 0))
                            .font(.caption)
                        PnLText(value: row.pnlReporting, currency: reportingCurrency)
                            .font(.caption2)
                    }
                    .frame(maxWidth: .infinity, alignment: .trailing)

                    Text(String(format: "%.1f%%", row.proportion))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .frame(width: 44, alignment: .trailing)
                }
                .padding(.vertical, 4)
                Divider()
            }

            if aggregated.count > defaultVisible {
                Button(action: { withAnimation(.easeInOut(duration: 0.2)) { expanded.toggle() } }) {
                    HStack(spacing: 4) {
                        Text(expanded ? "Show less" : "Show all \(aggregated.count) entries")
                        Image(systemName: expanded ? "chevron.up" : "chevron.down")
                    }
                    .font(.caption)
                    .foregroundStyle(.blue)
                    .frame(maxWidth: .infinity)
                    .padding(.top, 6)
                }
                .buttonStyle(.plain)
            }
        }
    }
}
