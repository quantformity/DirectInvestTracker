import Foundation

/// Actor so crumb state is safe across concurrent callers.
actor YahooFinanceService: YahooFinanceServiceProtocol {

    private let summaryURL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/"
    private let crumbURL   = "https://query2.finance.yahoo.com/v1/test/getcrumb"
    private let chartURL   = "https://query1.finance.yahoo.com/v8/finance/chart/"

    private var crumb: String? = nil
    private var cookiesInitialised = false
    private let session: URLSession

    init() {
        let config = URLSessionConfiguration.default
        config.httpAdditionalHeaders = [
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        ]
        self.session = URLSession(configuration: config)
    }

    // MARK: - Cookie init

    /// Yahoo Finance requires a session cookie before the crumb endpoint returns a valid value.
    /// Visiting the main finance page sets the necessary cookies in the shared cookie store.
    private func ensureCookies() async {
        guard !cookiesInitialised else { return }
        cookiesInitialised = true
        let urls = [
            "https://finance.yahoo.com",
            "https://fc.yahoo.com"
        ]
        for urlString in urls {
            guard let url = URL(string: urlString) else { continue }
            _ = try? await session.data(from: url)
        }
    }

    // MARK: - Crumb

    private func getCrumb() async -> String? {
        if let c = crumb { return c }
        await ensureCookies()
        guard let url = URL(string: crumbURL) else { return nil }
        do {
            let (data, response) = try await session.data(from: url)
            if let http = response as? HTTPURLResponse, http.statusCode == 200,
               let text = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines),
               !text.isEmpty && !text.contains("<html") {
                crumb = text
                return text
            }
        } catch {
            print("[YahooFinanceService] crumb fetch error: \(error)")
        }
        return nil
    }

    // MARK: - Fetch Prices

    func fetchPrices(symbols: [String]) async throws -> [String: MarketQuote] {
        var results: [String: MarketQuote] = [:]
        for (i, symbol) in symbols.enumerated() {
            if i > 0 { try await Task.sleep(nanoseconds: 400_000_000) }
            results[symbol] = await fetchOne(symbol: symbol)
        }
        return results
    }

    private func fetchOne(symbol: String) async -> MarketQuote {
        // Try quoteSummary with crumb first
        if let c = await getCrumb() {
            var comps = URLComponents(string: summaryURL + symbol)!
            comps.queryItems = [
                URLQueryItem(name: "modules", value: "price,summaryDetail,defaultKeyStatistics"),
                URLQueryItem(name: "crumb",   value: c),
            ]
            if let url = comps.url {
                do {
                    let (data, response) = try await session.data(from: url)
                    if let http = response as? HTTPURLResponse, http.statusCode == 401 || http.statusCode == 403 {
                        crumb = nil
                        cookiesInitialised = false   // force cookie re-init on next attempt
                    } else if let http = response as? HTTPURLResponse, http.statusCode == 200 {
                        if let quote = parseQuoteSummary(data: data) { return quote }
                    }
                } catch {
                    print("[YahooFinanceService] quoteSummary error for \(symbol): \(error)")
                }
            }
        }

        // Fallback: v8/chart
        return await fetchChartPrice(symbol: symbol)
    }

    private func fetchChartPrice(symbol: String) async -> MarketQuote {
        var comps = URLComponents(string: chartURL + symbol)!
        comps.queryItems = [
            URLQueryItem(name: "interval", value: "1d"),
            URLQueryItem(name: "range",    value: "5d"),
        ]
        guard let url = comps.url else { return MarketQuote(lastPrice: nil, previousClose: nil, changePercent: nil, changePercentSource: nil, peRatio: nil, beta: nil, companyName: nil) }
        do {
            let (data, _) = try await session.data(from: url)
            let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            if let result = (json?["chart"] as? [String: Any])?["result"] as? [[String: Any]],
               let first = result.first,
               let meta = first["meta"] as? [String: Any] {
                let price = meta["regularMarketPrice"] as? Double

                // Use the closes array to find yesterday's close (second-to-last non-nil close).
                // `chartPreviousClose` in meta is the reference for the current session price,
                // not yesterday's session close — so it gives the wrong daily change in after-hours.
                var prevClose: Double? = nil
                if let quotes = (first["indicators"] as? [String: Any])?["quote"] as? [[String: Any]],
                   let rawCloses = quotes.first?["close"] as? [Any] {
                    let validCloses = rawCloses.compactMap { $0 as? Double }
                    if validCloses.count >= 2 {
                        prevClose = validCloses[validCloses.count - 2]
                    } else if validCloses.count == 1 {
                        prevClose = validCloses[0]
                    }
                }
                // Fall back to chartPreviousClose if the closes array is empty
                if prevClose == nil {
                    prevClose = meta["chartPreviousClose"] as? Double
                }

                var chg: Double? = nil
                if let p = price, let pr = prevClose, pr != 0 {
                    chg = (p - pr) / pr * 100.0
                }
                return MarketQuote(lastPrice: price, previousClose: prevClose, changePercent: chg, changePercentSource: chg != nil ? "chart" : nil, peRatio: nil, beta: nil, companyName: nil)
            }
        } catch {
            print("[YahooFinanceService] chart fallback error for \(symbol): \(error)")
        }
        return MarketQuote(lastPrice: nil, previousClose: nil, changePercent: nil, changePercentSource: nil, peRatio: nil, beta: nil, companyName: nil)
    }

    private func parseQuoteSummary(data: Data) -> MarketQuote? {
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let qsResult = (json["quoteSummary"] as? [String: Any])?["result"] as? [[String: Any]],
              let first = qsResult.first else { return nil }

        let priceD   = first["price"] as? [String: Any] ?? [:]
        let summary  = first["summaryDetail"] as? [String: Any] ?? [:]
        let stats    = first["defaultKeyStatistics"] as? [String: Any] ?? [:]

        // Yahoo Finance can return fields as {raw:, fmt:} dicts OR plain numbers — try both.
        func raw(_ dict: [String: Any], _ key: String) -> Double? {
            (dict[key] as? [String: Any])?["raw"] as? Double ?? dict[key] as? Double
        }

        let price     = raw(priceD, "regularMarketPrice")
        let prevClose = raw(priceD, "regularMarketPreviousClose")
                     ?? raw(summary, "previousClose")   // summaryDetail fallback
        let chgRaw    = raw(priceD, "regularMarketChangePercent")

        // Compute changePercent: prefer the API value; derive from prices if missing.
        let changePercent: Double?
        let changePercentSource: String?
        if let c = chgRaw {
            changePercent = c * 100          // API gives decimal (0.025 → 2.5 %)
            changePercentSource = "api"
        } else if let p = price, let pc = prevClose, pc > 0 {
            changePercent = (p - pc) / pc * 100
            changePercentSource = "derived"
        } else {
            changePercent = nil
            changePercentSource = nil
        }

        let pe   = raw(summary, "trailingPE") ?? raw(summary, "forwardPE")
        let beta = raw(stats,   "beta")
        let name = (priceD["longName"] as? String) ?? (priceD["shortName"] as? String)

        return MarketQuote(
            lastPrice:          price,
            previousClose:      prevClose,
            changePercent:      changePercent,
            changePercentSource: changePercentSource,
            peRatio:            pe,
            beta:               beta,
            companyName:        name
        )
    }

    // MARK: - Fetch FX Rates

    func fetchFxRates(pairs: [(String, String)]) async throws -> [String: Double] {
        var result: [String: Double] = [:]
        let toFetch = pairs.filter { $0.0.uppercased() != $0.1.uppercased() }
        for (i, (from, to)) in toFetch.enumerated() {
            if i > 0 { try await Task.sleep(nanoseconds: 400_000_000) }
            let fxSymbol = "\(from.uppercased())\(to.uppercased())=X"
            var comps = URLComponents(string: chartURL + fxSymbol)!
            comps.queryItems = [
                URLQueryItem(name: "interval", value: "1d"),
                URLQueryItem(name: "range",    value: "1d"),
            ]
            guard let url = comps.url else { continue }
            do {
                let (data, _) = try await session.data(from: url)
                let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
                if let res = (json?["chart"] as? [String: Any])?["result"] as? [[String: Any]],
                   let meta = res.first?["meta"] as? [String: Any],
                   let rate = meta["regularMarketPrice"] as? Double {
                    result["\(from.uppercased())/\(to.uppercased())"] = rate
                }
            } catch {
                print("[YahooFinanceService] FX error for \(from)/\(to): \(error)")
            }
        }
        return result
    }

    // MARK: - Fetch History

    func fetchHistory(symbol: String, from startDate: Date) async throws -> [Date: Double] {
        let period1 = Int(startDate.timeIntervalSince1970)
        let period2 = Int(Date().timeIntervalSince1970)

        var comps = URLComponents(string: chartURL + symbol)!
        comps.queryItems = [
            URLQueryItem(name: "interval", value: "1d"),
            URLQueryItem(name: "period1",  value: "\(period1)"),
            URLQueryItem(name: "period2",  value: "\(period2)"),
        ]
        guard let url = comps.url else { return [:] }
        let (data, _) = try await session.data(from: url)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        guard let result = (json?["chart"] as? [String: Any])?["result"] as? [[String: Any]],
              let first = result.first,
              let timestamps = first["timestamp"] as? [Int],
              let closes = (first["indicators"] as? [String: Any])?["quote"] as? [[String: Any]],
              let closePrices = closes.first?["close"] as? [Double?] else {
            return [:]
        }

        var out: [Date: Double] = [:]
        var lastClose: Double? = nil
        let cal = Calendar(identifier: .gregorian)
        for (i, ts) in timestamps.enumerated() {
            if i < closePrices.count, let c = closePrices[i] { lastClose = c }
            guard let close = lastClose else { continue }
            let date = Date(timeIntervalSince1970: TimeInterval(ts))
            let midnight = cal.startOfDay(for: date)
            out[midnight] = close
        }
        return out
    }
}
