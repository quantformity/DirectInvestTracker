import SwiftUI

struct PositionRowView: View {
    let position: Position

    private var category: Category? { Category(rawValue: position.category) }

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            if let cat = category {
                CategoryBadge(category: cat)
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(position.symbol)
                    .font(.headline)
                HStack {
                    Text("Qty: \(position.quantity.formatted(.number.precision(.fractionLength(2))))")
                    Text("@ \(position.costPerShare.formatted(.number.precision(.fractionLength(4))))")
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text(position.currency)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(position.dateAdded.formatted(style: .short))
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(.vertical, 4)
    }
}
