import { useState, useEffect } from "react";
import { api, type Account, type Position, type CategoryEnum } from "../api/client";

const CATEGORIES: CategoryEnum[] = ["Equity", "GIC", "Cash", "Dividend"];

type TxType = "deposit" | "withdraw" | "dividend";

const defaultTxForm = {
  account_id: 0,
  type: "deposit" as TxType,
  amount: "",
  symbol: "",
  date: new Date().toISOString().split("T")[0],
};

const CURRENCIES = ["USD", "CAD", "HKD", "GBP", "EUR", "JPY", "AUD", "CHF"];

const defaultPositionForm = {
  account_id: 0,
  symbol: "",
  category: "Equity" as CategoryEnum,
  quantity: "",
  cost_per_share: "",
  date_added: new Date().toISOString().split("T")[0],
  yield_rate: "",
  currency: "USD",
};

const defaultAccountForm = { name: "", base_currency: "CAD" };

export function PositionManager() {
  const [tab, setTab] = useState<"accounts" | "positions" | "transactions">("positions");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Position form
  const [posForm, setPosForm] = useState(defaultPositionForm);
  const [editingPos, setEditingPos] = useState<Position | null>(null);

  // Account form
  const [accForm, setAccForm] = useState(defaultAccountForm);
  const [editingAcc, setEditingAcc] = useState<Account | null>(null);

  // Transaction form
  const [txForm, setTxForm] = useState(defaultTxForm);

  const fetchData = async () => {
    const [accs, poss] = await Promise.all([api.getAccounts(), api.getPositions()]);
    setAccounts(accs);
    setPositions(poss);
  };

  useEffect(() => { fetchData(); }, []);

  const showSuccess = (msg: string) => {
    setSuccess(msg);
    setTimeout(() => setSuccess(""), 3000);
  };

  // ── Account handlers ─────────────────────────────────────────────────────

  const handleSaveAccount = async () => {
    setLoading(true);
    setError("");
    try {
      if (editingAcc) {
        await api.updateAccount(editingAcc.id, accForm);
        showSuccess("Account updated");
      } else {
        await api.createAccount(accForm);
        showSuccess("Account created");
      }
      setAccForm(defaultAccountForm);
      setEditingAcc(null);
      fetchData();
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error saving account");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAccount = async (id: number) => {
    if (!confirm("Delete this account and all its positions?")) return;
    await api.deleteAccount(id);
    fetchData();
  };

  // ── Position handlers ────────────────────────────────────────────────────

  const handleSavePosition = async () => {
    setLoading(true);
    setError("");
    try {
      const payload = {
        account_id: Number(posForm.account_id),
        symbol: posForm.symbol.toUpperCase(),
        category: posForm.category,
        quantity: Number(posForm.quantity),
        cost_per_share: Number(posForm.cost_per_share),
        date_added: posForm.date_added,
        yield_rate: posForm.yield_rate ? Number(posForm.yield_rate) : null,
        currency: posForm.currency,
      };
      if (editingPos) {
        await api.updatePosition(editingPos.id, payload);
        showSuccess("Position updated");
      } else {
        await api.createPosition(payload);
        showSuccess("Position created");
      }
      setPosForm(defaultPositionForm);
      setEditingPos(null);
      fetchData();
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error saving position");
    } finally {
      setLoading(false);
    }
  };

  const handleDeletePosition = async (id: number) => {
    if (!confirm("Delete this position?")) return;
    await api.deletePosition(id);
    fetchData();
  };

  const handleSaveTransaction = async () => {
    if (!txForm.account_id) { setError("Select an account"); return; }
    if (!txForm.amount || Number(txForm.amount) <= 0) { setError("Enter a positive amount"); return; }
    if (txForm.type === "dividend" && !txForm.symbol.trim()) { setError("Enter the dividend source symbol"); return; }
    setLoading(true);
    setError("");
    try {
      const account = accounts.find((a) => a.id === Number(txForm.account_id));
      const currency = account?.base_currency ?? "CAD";
      const payload = {
        account_id: Number(txForm.account_id),
        symbol: txForm.type === "dividend" ? txForm.symbol.trim().toUpperCase() : "CASH",
        category: (txForm.type === "dividend" ? "Dividend" : "Cash") as CategoryEnum,
        quantity: txForm.type === "withdraw" ? -Number(txForm.amount) : Number(txForm.amount),
        cost_per_share: 1,
        date_added: txForm.date,
        yield_rate: null,
        currency,
      };
      await api.createPosition(payload);
      showSuccess(
        txForm.type === "deposit" ? "Cash deposit recorded" :
        txForm.type === "withdraw" ? "Cash withdrawal recorded" :
        "Dividend recorded"
      );
      setTxForm({ ...defaultTxForm, account_id: txForm.account_id, type: txForm.type });
      fetchData();
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Error saving transaction");
    } finally {
      setLoading(false);
    }
  };

  const startEditPosition = (p: Position) => {
    setEditingPos(p);
    setPosForm({
      account_id: p.account_id,
      symbol: p.symbol,
      category: p.category,
      quantity: String(p.quantity),
      cost_per_share: String(p.cost_per_share),
      date_added: p.date_added,
      yield_rate: p.yield_rate != null ? String(p.yield_rate) : "",
      currency: p.currency ?? "USD",
    });
    setTab("positions");
  };

  const startEditAccount = (a: Account) => {
    setEditingAcc(a);
    setAccForm({ name: a.name, base_currency: a.base_currency });
    setTab("accounts");
  };

  const accountName = (id: number) => accounts.find((a) => a.id === id)?.name ?? `#${id}`;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-6">Position Manager</h1>

      {/* Alerts */}
      {error && <div className="mb-4 p-3 bg-red-900/40 border border-red-700 text-red-300 rounded">{error}</div>}
      {success && <div className="mb-4 p-3 bg-green-900/40 border border-green-700 text-green-300 rounded">{success}</div>}

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-gray-700">
        {(["positions", "transactions", "accounts"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 -mb-px capitalize text-sm font-medium border-b-2 transition-colors ${
              tab === t ? "border-blue-500 text-blue-400" : "border-transparent text-gray-400 hover:text-white"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ── Transactions Tab ── */}
      {tab === "transactions" && (
        <div className="space-y-6">
          {/* Form */}
          <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
            <h2 className="text-lg font-semibold mb-4">Record Transaction</h2>

            {/* Type selector */}
            <div className="flex gap-2 mb-5">
              {([
                { value: "deposit",  label: "Cash Deposit",   color: "bg-green-600 hover:bg-green-500"  },
                { value: "withdraw", label: "Cash Withdrawal", color: "bg-red-600 hover:bg-red-500"     },
                { value: "dividend", label: "Dividend",        color: "bg-purple-600 hover:bg-purple-500"},
              ] as { value: TxType; label: string; color: string }[]).map(({ value, label, color }) => (
                <button
                  key={value}
                  onClick={() => setTxForm({ ...txForm, type: value })}
                  className={`px-4 py-2 rounded text-sm font-medium transition-colors text-white ${
                    txForm.type === value ? color : "bg-gray-700 hover:bg-gray-600"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Account</label>
                <select
                  className="w-full bg-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={txForm.account_id}
                  onChange={(e) => setTxForm({ ...txForm, account_id: Number(e.target.value) })}
                >
                  <option value={0}>Select account…</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>{a.name} ({a.base_currency})</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1">Date</label>
                <input
                  type="date"
                  className="w-full bg-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={txForm.date}
                  onChange={(e) => setTxForm({ ...txForm, date: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-xs text-gray-400 mb-1">
                  {txForm.type === "withdraw" ? "Withdrawal Amount" : "Amount"}
                  {txForm.account_id ? ` (${accounts.find(a => a.id === txForm.account_id)?.base_currency ?? ""})` : ""}
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  className="w-full bg-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={txForm.amount}
                  onChange={(e) => setTxForm({ ...txForm, amount: e.target.value })}
                  placeholder="e.g. 5000.00"
                />
              </div>

              {txForm.type === "dividend" && (
                <div>
                  <label className="block text-xs text-gray-400 mb-1">From Symbol</label>
                  <input
                    className="w-full bg-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                    value={txForm.symbol}
                    onChange={(e) => setTxForm({ ...txForm, symbol: e.target.value.toUpperCase() })}
                    placeholder="e.g. AAPL"
                  />
                </div>
              )}
            </div>

            <button
              onClick={handleSaveTransaction}
              disabled={loading}
              className={`mt-4 px-5 py-2 disabled:opacity-50 text-white rounded text-sm font-medium transition-colors ${
                txForm.type === "deposit"  ? "bg-green-600 hover:bg-green-500" :
                txForm.type === "withdraw" ? "bg-red-600 hover:bg-red-500"    :
                                             "bg-purple-600 hover:bg-purple-500"
              }`}
            >
              {txForm.type === "deposit"  ? "Record Deposit" :
               txForm.type === "withdraw" ? "Record Withdrawal" :
               "Record Dividend"}
            </button>
          </div>

          {/* Recent cash & dividend transactions */}
          <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-700">
              <h3 className="text-sm font-semibold text-gray-300">Recent Cash &amp; Dividend Transactions</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-700/50 text-gray-300 uppercase text-xs">
                  <tr>
                    <th className="px-4 py-3 text-left">Date</th>
                    <th className="px-4 py-3 text-left">Type</th>
                    <th className="px-4 py-3 text-left">Account</th>
                    <th className="px-4 py-3 text-left">Symbol</th>
                    <th className="px-4 py-3 text-right">Amount</th>
                    <th className="px-4 py-3 text-left">CCY</th>
                    <th className="px-4 py-3 text-left">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {positions
                    .filter((p) => p.category === "Cash" || p.category === "Dividend")
                    .sort((a, b) => b.date_added.localeCompare(a.date_added))
                    .map((p) => {
                      const isWithdraw = p.category === "Cash" && p.quantity < 0;
                      return (
                        <tr key={p.id} className="hover:bg-gray-700/30">
                          <td className="px-4 py-3 text-gray-400">{p.date_added}</td>
                          <td className="px-4 py-3">
                            {p.category === "Dividend" ? (
                              <span className="px-2 py-0.5 bg-purple-900/50 text-purple-300 rounded text-xs">Dividend</span>
                            ) : isWithdraw ? (
                              <span className="px-2 py-0.5 bg-red-900/50 text-red-300 rounded text-xs">Withdrawal</span>
                            ) : (
                              <span className="px-2 py-0.5 bg-green-900/50 text-green-300 rounded text-xs">Deposit</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-gray-300">{accountName(p.account_id)}</td>
                          <td className="px-4 py-3 font-medium text-white">{p.symbol}</td>
                          <td className={`px-4 py-3 text-right font-medium ${isWithdraw ? "text-red-400" : "text-green-400"}`}>
                            {isWithdraw ? "-" : "+"}{Math.abs(p.quantity).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-0.5 bg-blue-900/50 text-blue-300 rounded text-xs">{p.currency}</span>
                          </td>
                          <td className="px-4 py-3">
                            <button onClick={() => handleDeletePosition(p.id)} className="text-red-400 hover:text-red-300 text-xs">Delete</button>
                          </td>
                        </tr>
                      );
                    })}
                  {!positions.filter((p) => p.category === "Cash" || p.category === "Dividend").length && (
                    <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-500">No cash or dividend transactions yet</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── Accounts Tab ── */}
      {tab === "accounts" && (
        <div className="space-y-6">
          {/* Form */}
          <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
            <h2 className="text-lg font-semibold mb-4">{editingAcc ? "Edit Account" : "Add Account"}</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Account Name</label>
                <input
                  className="w-full bg-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={accForm.name}
                  onChange={(e) => setAccForm({ ...accForm, name: e.target.value })}
                  placeholder="e.g. TFSA, RRSP"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Base Currency</label>
                <select
                  className="w-full bg-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={accForm.base_currency}
                  onChange={(e) => setAccForm({ ...accForm, base_currency: e.target.value })}
                >
                  {["CAD", "USD", "EUR", "GBP"].map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <div className="flex gap-3 mt-4">
              <button
                onClick={handleSaveAccount}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded text-sm font-medium transition-colors"
              >
                {editingAcc ? "Update" : "Create"} Account
              </button>
              {editingAcc && (
                <button
                  onClick={() => { setEditingAcc(null); setAccForm(defaultAccountForm); }}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm transition-colors"
                >
                  Cancel
                </button>
              )}
            </div>
          </div>

          {/* Account list */}
          <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-700/50 text-gray-300 uppercase text-xs">
                <tr>
                  <th className="px-4 py-3 text-left">ID</th>
                  <th className="px-4 py-3 text-left">Name</th>
                  <th className="px-4 py-3 text-left">Currency</th>
                  <th className="px-4 py-3 text-left">Positions</th>
                  <th className="px-4 py-3 text-left">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {accounts.map((a) => (
                  <tr key={a.id} className="hover:bg-gray-700/30">
                    <td className="px-4 py-3 text-gray-400">{a.id}</td>
                    <td className="px-4 py-3 font-medium text-white">{a.name}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 bg-blue-900/50 text-blue-300 rounded text-xs">{a.base_currency}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-400">{positions.filter((p) => p.account_id === a.id).length}</td>
                    <td className="px-4 py-3 flex gap-2">
                      <button onClick={() => startEditAccount(a)} className="text-blue-400 hover:text-blue-300 text-xs">Edit</button>
                      <button onClick={() => handleDeleteAccount(a.id)} className="text-red-400 hover:text-red-300 text-xs">Delete</button>
                    </td>
                  </tr>
                ))}
                {!accounts.length && (
                  <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-500">No accounts yet</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Positions Tab ── */}
      {tab === "positions" && (
        <div className="space-y-6">
          {/* Form */}
          <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
            <h2 className="text-lg font-semibold mb-4">{editingPos ? "Edit Position" : "Add Position"}</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Account</label>
                <select
                  className="w-full bg-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={posForm.account_id}
                  onChange={(e) => setPosForm({ ...posForm, account_id: Number(e.target.value) })}
                >
                  <option value={0}>Select account…</option>
                  {accounts.map((a) => <option key={a.id} value={a.id}>{a.name} ({a.base_currency})</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Category</label>
                <select
                  className="w-full bg-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={posForm.category}
                  onChange={(e) => setPosForm({ ...posForm, category: e.target.value as CategoryEnum })}
                >
                  {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Symbol</label>
                <input
                  className="w-full bg-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={posForm.symbol}
                  onChange={(e) => setPosForm({ ...posForm, symbol: e.target.value.toUpperCase() })}
                  placeholder={posForm.category === "Equity" ? "e.g. AAPL, TD.TO" : "e.g. BMO GIC 2025"}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Stock Currency</label>
                <select
                  className="w-full bg-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={posForm.currency}
                  onChange={(e) => setPosForm({ ...posForm, currency: e.target.value })}
                >
                  {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Quantity / Principal</label>
                <input
                  type="number"
                  className="w-full bg-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={posForm.quantity}
                  onChange={(e) => setPosForm({ ...posForm, quantity: e.target.value })}
                  placeholder="e.g. 100"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Cost per Share / Unit</label>
                <input
                  type="number"
                  step="0.01"
                  className="w-full bg-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={posForm.cost_per_share}
                  onChange={(e) => setPosForm({ ...posForm, cost_per_share: e.target.value })}
                  placeholder="e.g. 1.00 for Cash/GIC"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Date Added</label>
                <input
                  type="date"
                  className="w-full bg-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  value={posForm.date_added}
                  onChange={(e) => setPosForm({ ...posForm, date_added: e.target.value })}
                />
              </div>
              {posForm.category === "GIC" && (
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Annual Yield Rate (e.g. 0.045 for 4.5%)</label>
                  <input
                    type="number"
                    step="0.001"
                    className="w-full bg-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                    value={posForm.yield_rate}
                    onChange={(e) => setPosForm({ ...posForm, yield_rate: e.target.value })}
                    placeholder="e.g. 0.045"
                  />
                </div>
              )}
            </div>
            <div className="flex gap-3 mt-4">
              <button
                onClick={handleSavePosition}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded text-sm font-medium transition-colors"
              >
                {editingPos ? "Update" : "Add"} Position
              </button>
              {editingPos && (
                <button
                  onClick={() => { setEditingPos(null); setPosForm(defaultPositionForm); }}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm transition-colors"
                >
                  Cancel
                </button>
              )}
            </div>
          </div>

          {/* Position list */}
          <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-700/50 text-gray-300 uppercase text-xs">
                  <tr>
                    <th className="px-4 py-3 text-left">Symbol</th>
                    <th className="px-4 py-3 text-left">Category</th>
                    <th className="px-4 py-3 text-left">Account</th>
                    <th className="px-4 py-3 text-left">CCY</th>
                    <th className="px-4 py-3 text-right">Qty</th>
                    <th className="px-4 py-3 text-right">Cost/Share</th>
                    <th className="px-4 py-3 text-left">Date</th>
                    <th className="px-4 py-3 text-left">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {positions.map((p) => (
                    <tr key={p.id} className="hover:bg-gray-700/30">
                      <td className="px-4 py-3 font-medium text-white">{p.symbol}</td>
                      <td className="px-4 py-3">
                        <CategoryBadge category={p.category} />
                      </td>
                      <td className="px-4 py-3 text-gray-300">{accountName(p.account_id)}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 bg-purple-900/50 text-purple-300 rounded text-xs">{p.currency ?? "USD"}</span>
                      </td>
                      <td className="px-4 py-3 text-right text-gray-300">{p.quantity.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right text-gray-300">{p.cost_per_share.toFixed(2)}</td>
                      <td className="px-4 py-3 text-gray-400">{p.date_added}</td>
                      <td className="px-4 py-3 flex gap-2">
                        <button onClick={() => startEditPosition(p)} className="text-blue-400 hover:text-blue-300 text-xs">Edit</button>
                        <button onClick={() => handleDeletePosition(p.id)} className="text-red-400 hover:text-red-300 text-xs">Delete</button>
                      </td>
                    </tr>
                  ))}
                  {!positions.length && (
                    <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-500">No positions yet — add one above</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CategoryBadge({ category }: { category: CategoryEnum }) {
  const colors: Record<CategoryEnum, string> = {
    Equity: "bg-blue-900/50 text-blue-300",
    GIC: "bg-yellow-900/50 text-yellow-300",
    Cash: "bg-green-900/50 text-green-300",
    Dividend: "bg-purple-900/50 text-purple-300",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs ${colors[category]}`}>{category}</span>
  );
}
