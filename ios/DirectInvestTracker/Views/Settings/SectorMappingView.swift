import SwiftUI

struct SectorMappingView: View {
    @Bindable var viewModel: SettingsViewModel
    @State private var showAddMapping = false
    @State private var newSymbol = ""
    @State private var newSector = ""

    var body: some View {
        List {
            ForEach(viewModel.sectorMappings, id: \.symbol) { mapping in
                HStack {
                    Text(mapping.symbol)
                        .font(.headline)
                    Spacer()
                    Text(mapping.sector)
                        .foregroundStyle(.secondary)
                }
            }
            .onDelete { indexSet in
                indexSet.forEach { viewModel.deleteSectorMapping(viewModel.sectorMappings[$0]) }
            }
        }
        .navigationTitle("Sector Mappings")
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button(action: { showAddMapping = true }) {
                    Image(systemName: "plus")
                }
            }
        }
        .sheet(isPresented: $showAddMapping) {
            NavigationStack {
                Form {
                    TextField("Symbol (e.g. AAPL)", text: $newSymbol)
                        .textInputAutocapitalization(.characters)
                    TextField("Sector (e.g. Technology)", text: $newSector)
                }
                .navigationTitle("Add Mapping")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { showAddMapping = false }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Add") {
                            viewModel.addSectorMapping(symbol: newSymbol, sector: newSector)
                            newSymbol = ""
                            newSector = ""
                            showAddMapping = false
                        }
                        .disabled(newSymbol.isEmpty || newSector.isEmpty)
                    }
                }
            }
        }
        .onAppear { viewModel.fetchSectorMappings() }
    }
}
