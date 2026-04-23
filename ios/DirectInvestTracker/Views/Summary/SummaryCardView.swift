import SwiftUI

struct SummaryCardView: View {
    let group: SummaryGroup
    let reportingCurrency: String
    let positions: [EnrichedPosition]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(group.groupKey)
                    .font(.headline)
                Spacer()
                Text(String(format: "%.1f%%", group.proportion))
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            DonutChartView(group: group, positions: positions)
                .frame(height: 180)

            Divider()

            SummaryTableView(positions: positions, reportingCurrency: reportingCurrency)
        }
        .padding()
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .padding(.horizontal)
    }
}
