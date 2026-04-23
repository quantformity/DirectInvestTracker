import SwiftUI

struct HistoryExtremesView: View {
    let peak: HistoryPoint?
    let trough: HistoryPoint?
    let currency: String

    var body: some View {
        HStack(spacing: 12) {
            if let peak {
                extremeCard(
                    title: "Peak MTM",
                    date: peak.date,
                    mtm: peak.mtm,
                    pnl: peak.pnl,
                    icon: "arrow.up.circle.fill",
                    iconColor: .green
                )
            }
            if let trough {
                extremeCard(
                    title: "Trough MTM",
                    date: trough.date,
                    mtm: trough.mtm,
                    pnl: trough.pnl,
                    icon: "arrow.down.circle.fill",
                    iconColor: .red
                )
            }
        }
    }

    private func extremeCard(title: String, date: Date, mtm: Double, pnl: Double, icon: String, iconColor: Color) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Label(title, systemImage: icon)
                .font(.caption)
                .foregroundStyle(iconColor)
            Text(date.formatted(style: .medium))
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(mtm.currencyFormatted(currency: currency, maximumFractionDigits: 0))
                .font(.subheadline.bold())
            PnLText(value: pnl, currency: currency)
                .font(.caption)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}
