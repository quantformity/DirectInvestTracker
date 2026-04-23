import SwiftUI

struct CategoryBadge: View {
    let category: Category

    var body: some View {
        Text(category.rawValue)
            .font(.caption2)
            .fontWeight(.semibold)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(Color.forCategory(category).opacity(0.2))
            .foregroundStyle(Color.forCategory(category))
            .clipShape(Capsule())
    }
}
