import SwiftUI

struct ErrorBannerView: View {
    let message: String
    var onDismiss: (() -> Void)? = nil

    var body: some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.red)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.primary)
            Spacer()
            if let dismiss = onDismiss {
                Button(action: dismiss) {
                    Image(systemName: "xmark")
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding()
        .background(.red.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 10))
        .padding(.horizontal)
    }
}
