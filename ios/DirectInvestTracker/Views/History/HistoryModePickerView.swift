import SwiftUI

struct HistoryModePickerView: View {
    @Binding var selectedMode: HistoryMode

    var body: some View {
        Picker("Mode", selection: $selectedMode) {
            ForEach(HistoryMode.allCases) { mode in
                Text(mode.rawValue).tag(mode)
            }
        }
        .pickerStyle(.segmented)
    }
}
