import SwiftUI
import Charts

struct HistoryChartView: View {
    let points: [HistoryPoint]

    @State private var selectedDate: Date? = nil

    /// Forward-fill PnL so gaps (dates where equity price was missing → pnl==0 while mtm>0)
    /// don't break the line. A zero PnL that has no previous value to fill from is left as-is.
    private var pnlFilled: [HistoryPoint] {
        var lastKnown: Double? = nil
        return points.map { pt in
            if pt.pnl != 0 {
                lastKnown = pt.pnl
                return pt
            }
            // Keep genuine leading zeros (no positions yet)
            guard let fill = lastKnown else { return pt }
            return HistoryPoint(date: pt.date, pnl: fill, mtm: pt.mtm, cashGIC: pt.cashGIC)
        }
    }

    // Snap selected date to the nearest actual data point (use filled PnL for display)
    private var selectedPoint: HistoryPoint? {
        guard let sel = selectedDate else { return nil }
        return pnlFilled.min(by: {
            abs($0.date.timeIntervalSince(sel)) < abs($1.date.timeIntervalSince(sel))
        })
    }

    private var lastPnL: Double { points.last?.pnl ?? 0 }
    private var pnlColor: Color { Color.pnl(lastPnL) }
    private var hasCash: Bool { points.contains { $0.cashGIC > 0 } }

    var body: some View {
        Chart {
            // ── Area fill under MTM ──────────────────────────────────────────
            ForEach(points) { pt in
                AreaMark(
                    x: .value("Date", pt.date),
                    y: .value("MTM",  pt.mtm)
                )
                .foregroundStyle(.blue.opacity(0.10))
                .interpolationMethod(.catmullRom)
            }

            // ── MTM line ────────────────────────────────────────────────────
            ForEach(points) { pt in
                LineMark(
                    x: .value("Date",  pt.date),
                    y: .value("Value", pt.mtm),
                    series: .value("Series", "MTM")
                )
                .foregroundStyle(.blue)
                .interpolationMethod(.catmullRom)
                .lineStyle(StrokeStyle(lineWidth: 2))
            }

            // ── PnL line (gap-filled) ────────────────────────────────────────
            ForEach(pnlFilled) { pt in
                LineMark(
                    x: .value("Date",  pt.date),
                    y: .value("Value", pt.pnl),
                    series: .value("Series", "PnL")
                )
                .foregroundStyle(pnlColor)
                .interpolationMethod(.catmullRom)
                .lineStyle(StrokeStyle(lineWidth: 1.5))
            }

            // ── Cash + GIC line ──────────────────────────────────────────────
            if hasCash {
                ForEach(points) { pt in
                    LineMark(
                        x: .value("Date",  pt.date),
                        y: .value("Value", pt.cashGIC),
                        series: .value("Series", "Cash+GIC")
                    )
                    .foregroundStyle(Color.orange)
                    .interpolationMethod(.catmullRom)
                    .lineStyle(StrokeStyle(lineWidth: 1.5))
                }
            }

            // ── Hair cursor ─────────────────────────────────────────────────
            if let snap = selectedPoint {
                RuleMark(x: .value("Date", snap.date))
                    .foregroundStyle(.gray.opacity(0.4))
                    .lineStyle(StrokeStyle(lineWidth: 1))
                    .annotation(
                        position: annotationPosition(for: snap.date),
                        alignment: .top,
                        spacing: 6
                    ) {
                        cursorTooltip(snap)
                    }

                PointMark(
                    x: .value("Date",  snap.date),
                    y: .value("Value", snap.mtm)
                )
                .foregroundStyle(.blue)
                .symbolSize(36)

                PointMark(
                    x: .value("Date",  snap.date),
                    y: .value("Value", snap.pnl)
                )
                .foregroundStyle(pnlColor)
                .symbolSize(36)

                if hasCash {
                    PointMark(
                        x: .value("Date",  snap.date),
                        y: .value("Value", snap.cashGIC)
                    )
                    .foregroundStyle(Color.orange)
                    .symbolSize(36)
                }
            }
        }
        .chartXSelection(value: $selectedDate)
        .chartXAxis {
            AxisMarks(values: .stride(by: .month, count: 3)) { _ in
                AxisGridLine()
                AxisTick()
                AxisValueLabel(format: .dateTime.month(.abbreviated).year(.twoDigits))
            }
        }
        .chartYAxis {
            AxisMarks { value in
                AxisGridLine()
                AxisValueLabel {
                    if let v = value.as(Double.self) {
                        Text(NumberFormatters.compact(v))
                    }
                }
            }
        }
        .chartLegend(position: .top, alignment: .leading) {
            HStack(spacing: 12) {
                legendItem(color: .blue,        label: "MTM",      dashed: false)
                legendItem(color: pnlColor,     label: "PnL",      dashed: false)
                if hasCash {
                    legendItem(color: .orange,  label: "Cash+GIC", dashed: false)
                }
            }
            .font(.caption)
        }
    }

    // MARK: - Tooltip

    private func cursorTooltip(_ pt: HistoryPoint) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(pt.date.formatted(.dateTime.month(.abbreviated).day().year()))
                .font(.caption2)
                .foregroundStyle(Color(.secondaryLabel))
            HStack(spacing: 6) {
                Circle().fill(.blue).frame(width: 6, height: 6)
                Text("MTM")
                    .font(.caption2).foregroundStyle(Color(.secondaryLabel))
                Text(NumberFormatters.compact(pt.mtm))
                    .font(.caption2.bold())
                    .foregroundStyle(Color(.label))
            }
            HStack(spacing: 6) {
                Circle().fill(pnlColor).frame(width: 6, height: 6)
                Text("PnL")
                    .font(.caption2).foregroundStyle(Color(.secondaryLabel))
                Text((pt.pnl >= 0 ? "+" : "") + NumberFormatters.compact(pt.pnl))
                    .font(.caption2.bold())
                    .foregroundStyle(pnlColor)
            }
            if hasCash && pt.cashGIC > 0 {
                HStack(spacing: 6) {
                    Circle().fill(Color.orange).frame(width: 6, height: 6)
                    Text("Cash+GIC")
                        .font(.caption2).foregroundStyle(Color(.secondaryLabel))
                    Text(NumberFormatters.compact(pt.cashGIC))
                        .font(.caption2.bold())
                        .foregroundStyle(Color.orange)
                }
            }
        }
        .padding(8)
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .shadow(color: .black.opacity(0.15), radius: 4, x: 0, y: 2)
    }

    /// Keep tooltip inside the chart by flipping to .leading when near the right edge.
    private func annotationPosition(for date: Date) -> AnnotationPosition {
        guard let first = points.first?.date, let last = points.last?.date else { return .leading }
        let total = last.timeIntervalSince(first)
        guard total > 0 else { return .leading }
        let fraction = date.timeIntervalSince(first) / total
        return fraction > 0.75 ? .leading : .trailing
    }

    // MARK: - Legend

    private func legendItem(color: Color, label: String, dashed: Bool) -> some View {
        HStack(spacing: 4) {
            Rectangle()
                .frame(width: 16, height: 2)
                .foregroundStyle(color)
                .overlay {
                    if dashed {
                        GeometryReader { geo in
                            Path { path in
                                path.move(to: .zero)
                                path.addLine(to: CGPoint(x: geo.size.width, y: 0))
                            }
                            .stroke(color, style: StrokeStyle(lineWidth: 2, dash: [3, 2]))
                        }
                    }
                }
            Text(label)
        }
    }
}
