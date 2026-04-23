import SwiftUI

extension Color {
    static func forCategory(_ category: Category) -> Color {
        switch category {
        case .equity:   return .blue
        case .gic:      return .green
        case .cash:     return .orange
        case .dividend: return .purple
        }
    }

    static func forGroupKey(_ key: String) -> Color {
        let palette: [Color] = [.blue, .green, .orange, .purple, .pink, .teal, .indigo, .yellow]
        let hash = abs(key.hashValue) % palette.count
        return palette[hash]
    }

    static func pnl(_ value: Double) -> Color {
        value >= 0 ? .green : .red
    }
}
