import SwiftUI

struct AccountRowView: View {
    let account: Account
    let positionCount: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(account.name)
                .font(.headline)
            HStack {
                Text(account.baseCurrency)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Spacer()
                Text("\(positionCount) position\(positionCount == 1 ? "" : "s")")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}
