import Foundation

extension Date {
    var startOfDay: Date {
        Calendar.current.startOfDay(for: self)
    }

    func formatted(style: DateFormatter.Style = .medium) -> String {
        let f = DateFormatter()
        f.dateStyle = style
        f.timeStyle = .none
        return f.string(from: self)
    }

    var iso8601String: String {
        ISO8601DateFormatter().string(from: self)
    }

    static func from(year: Int, month: Int, day: Int) -> Date {
        var comps = DateComponents()
        comps.year  = year
        comps.month = month
        comps.day   = day
        return Calendar.current.date(from: comps) ?? Date()
    }
}
