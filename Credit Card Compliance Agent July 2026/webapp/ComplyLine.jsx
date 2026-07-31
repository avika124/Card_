import React, { useState, useEffect, useCallback } from "react";
import {
  LayoutGrid, FilePlus2, Building2, Library, History, Settings2,
  Trash2, Loader2, ShieldCheck, ScrollText, Plus, Download, AlertTriangle,
  TrendingUp, Ban,
} from "lucide-react";

/* ─────────────────────────────────────────────────────────────
   Design tokens — ComplyLine identity (navy / teal / gold)
   ───────────────────────────────────────────────────────────── */
const T = {
  navy: "#1C2D4F", navyDeep: "#16243F", navyMid: "#243761",
  teal: "#2A9D8F", tealDeep: "#1D7A6E", gold: "#E9C46A",
  ink: "#1C2D4F", body: "#3A4658", mute: "#7B8798",
  page: "#F5F7FB", card: "#FFFFFF", line: "#E3E8F0",
  high: "#B3261E", med: "#9A6B00", low: "#2E7D32", pass: "#2E7D32",
  highBg: "#FDF3F2", medBg: "#FDF8EC", lowBg: "#F1F8F2",
};
const SERIF = "Georgia, 'Iowan Old Style', 'Times New Roman', serif";
const MONO = "'SF Mono', ui-monospace, Menlo, Consolas, monospace";

const SEV = {
  high:   { c: T.high, bg: T.highBg, label: "High" },
  medium: { c: T.med,  bg: T.medBg,  label: "Medium" },
  low:    { c: T.low,  bg: T.lowBg,  label: "Low" },
  pass:   { c: T.pass, bg: T.lowBg,  label: "Pass" },
};

const REGS = [
  { id: "udaap",       label: "UDAAP",        full: "Unfair, Deceptive, or Abusive Acts or Practices" },
  { id: "tila",        label: "TILA / Reg Z", full: "Truth in Lending Act and CARD Act" },
  { id: "ecoa",        label: "ECOA / Reg B", full: "Equal Credit Opportunity Act" },
  { id: "fcra",        label: "FCRA / Reg V", full: "Fair Credit Reporting Act" },
  { id: "bsa",         label: "BSA / AML",    full: "Bank Secrecy Act, OFAC, CIP" },
  { id: "pci",         label: "PCI DSS",      full: "Payment Card Industry Data Security Standard" },
  { id: "scra",        label: "SCRA / MLA",   full: "Servicemembers Civil Relief Act, Military Lending Act" },
  { id: "collections", label: "FDCPA",        full: "Fair Debt Collection Practices Act" },
  { id: "sr117",       label: "SR 11-7",      full: "Model Risk Management" },
];

const DOC_TYPES = [
  ["marketing", "Marketing material"], ["policy", "Internal policy"],
  ["disclosure", "Customer disclosure"], ["agreement", "Cardholder agreement"],
  ["script", "Call or collections script"], ["settlement", "Settlement or consent order"],
];

const AGENCIES = ["CFPB", "Federal Reserve", "OCC", "FDIC", "FFIEC", "FTC", "State regulator"];

const KEYS = {
  checks: "complyline:checks", memory: "complyline:memory",
  library: "complyline:library", revenue: "complyline:revenue",
};

/* Pricing term status — a violation is a wall, not a suggestion */
const STATUS = {
  violation:    { c: "#B3261E", bg: "#FDF3F2", label: "Over regulatory cap" },
  above_market: { c: "#9A6B00", bg: "#FDF8EC", label: "Above market" },
  opportunity:  { c: "#1D7A6E", bg: "#EDF7F5", label: "Below market" },
  at_market:    { c: "#5B6B7F", bg: "#F3F5F9", label: "At market" },
};

/* ─────────────────────────────────────────────────────────────
   Storage helpers
   ───────────────────────────────────────────────────────────── */
async function loadKey(key, fallback) {
  try {
    const r = await window.storage.get(key);
    return r ? JSON.parse(r.value) : fallback;
  } catch { return fallback; }
}
async function saveKey(key, value) {
  try { await window.storage.set(key, JSON.stringify(value)); } catch { /* non-fatal */ }
}

const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
const today = () => new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

/* ─────────────────────────────────────────────────────────────
   Claude call — runs inside Claude, so no key and no CORS
   ───────────────────────────────────────────────────────────── */
function extractJSON(raw) {
  const cleaned = raw.replace(/```json/gi, "").replace(/```/g, "").trim();
  try { return JSON.parse(cleaned); } catch { /* fall through */ }
  const a = cleaned.indexOf("{"), b = cleaned.lastIndexOf("}");
  if (a !== -1 && b > a) return JSON.parse(cleaned.slice(a, b + 1));
  throw new Error("The analysis came back in an unexpected format. Run the check again.");
}

async function askClaude(prompt) {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-6",
      max_tokens: 1000,
      messages: [{ role: "user", content: prompt }],
    }),
  });
  const data = await res.json();
  if (data?.error) throw new Error(data.error.message || "The request was rejected.");
  const text = (data.content || []).filter(b => b.type === "text").map(b => b.text).join("");
  if (!text) throw new Error("No analysis was returned. Run the check again.");
  return extractJSON(text);
}

/* ─────────────────────────────────────────────────────────────
   Primitives
   ───────────────────────────────────────────────────────────── */
const Card = ({ children, style, className = "" }) => (
  <div className={`rounded-lg ${className}`}
    style={{ background: T.card, border: `1px solid ${T.line}`, ...style }}>{children}</div>
);

const Badge = ({ sev, children }) => {
  const s = SEV[sev] || { c: T.mute, bg: "#F1F3F7" };
  return (
    <span className="inline-block rounded px-2 py-0.5 text-xs font-semibold tracking-wide"
      style={{ color: s.c, background: s.bg }}>
      {children || s.label}
    </span>
  );
};

const Label = ({ children }) => (
  <label className="block text-xs font-semibold mb-1 mt-4 uppercase"
    style={{ color: T.mute, letterSpacing: ".06em" }}>{children}</label>
);

const inputStyle = {
  width: "100%", padding: "8px 10px", borderRadius: 6,
  border: `1px solid ${T.line}`, fontSize: 13, color: T.ink,
  background: "#fff", fontFamily: "inherit", outline: "none",
};

const Button = ({ kind = "primary", children, ...rest }) => {
  const styles = {
    primary: { background: T.navy, color: "#fff", border: "1px solid transparent" },
    teal:    { background: T.teal, color: "#fff", border: "1px solid transparent" },
    ghost:   { background: "#fff", color: T.ink, border: `1px solid ${T.line}` },
    danger:  { background: "#fff", color: T.high, border: `1px solid #F0D5D3` },
  }[kind];
  return (
    <button {...rest}
      className="rounded-md px-4 py-2 text-sm font-medium inline-flex items-center gap-2 disabled:opacity-40"
      style={{ ...styles, cursor: rest.disabled ? "not-allowed" : "pointer" }}>
      {children}
    </button>
  );
};

const Empty = ({ icon: Icon, title, hint }) => (
  <div className="text-center py-12 px-6">
    <Icon size={22} style={{ color: T.mute }} className="mx-auto mb-3" />
    <div className="text-sm font-semibold" style={{ color: T.ink }}>{title}</div>
    <div className="text-xs mt-1" style={{ color: T.mute }}>{hint}</div>
  </div>
);

const PageTitle = ({ children, sub }) => (
  <div className="mb-5">
    <h1 style={{ fontFamily: SERIF, color: T.ink }} className="text-2xl font-bold">{children}</h1>
    {sub && <p className="text-sm mt-1" style={{ color: T.mute }}>{sub}</p>}
  </div>
);

/* ─────────────────────────────────────────────────────────────
   Finding & conflict cards — the signature elements
   ───────────────────────────────────────────────────────────── */
const Finding = ({ f }) => {
  const s = SEV[f.sev] || SEV.low;
  return (
    <div className="mb-2 rounded-r-md px-4 py-3"
      style={{ borderLeft: `3px solid ${s.c}`, background: s.bg }}>
      <div className="flex items-start justify-between gap-3">
        <div className="text-sm font-semibold" style={{ color: T.ink }}>{f.issue}</div>
        <div className="flex items-center gap-2 shrink-0">
          {f.ref && (
            <span className="text-xs px-1.5 py-0.5 rounded"
              style={{ fontFamily: MONO, color: T.mute, background: "#fff", border: `1px solid ${T.line}` }}>
              {f.ref}
            </span>
          )}
          <Badge sev={f.sev} />
        </div>
      </div>
      <div className="text-xs mt-0.5 font-medium" style={{ color: s.c }}>{f.reg}</div>
      <p className="text-sm mt-2 leading-relaxed" style={{ color: T.body }}>{f.detail}</p>
      {f.cite && (
        <div className="mt-2 text-xs" style={{ fontFamily: MONO, color: T.navyMid }}>{f.cite}</div>
      )}
      {f.fix && (
        <p className="text-xs mt-2 leading-relaxed" style={{ color: T.tealDeep }}>
          <span className="font-semibold">Fix — </span>{f.fix}
        </p>
      )}
    </div>
  );
};

const Conflict = ({ c }) => (
  <div className="mb-2 rounded-r-md px-4 py-3"
    style={{ borderLeft: `3px solid ${T.gold}`, background: "#FCF8EE" }}>
    <div className="flex items-start justify-between gap-3">
      <div className="text-sm font-semibold" style={{ color: T.ink }}>{c.title}</div>
      <Badge sev={c.sev} />
    </div>
    <div className="grid gap-2 mt-3" style={{ gridTemplateColumns: "1fr 1fr" }}>
      <div className="rounded p-2.5" style={{ background: "#fff", border: `1px solid ${T.line}` }}>
        <div className="text-xs font-semibold mb-1" style={{ color: T.mute }}>This document</div>
        <div className="text-xs leading-relaxed" style={{ color: T.body }}>{c.new}</div>
      </div>
      <div className="rounded p-2.5" style={{ background: T.highBg, border: "1px solid #F0D5D3" }}>
        <div className="text-xs font-semibold mb-1" style={{ color: T.high }}>
          {c.source || "Prior communication"}
        </div>
        <div className="text-xs leading-relaxed" style={{ color: T.high }}>{c.prior}</div>
      </div>
    </div>
    <p className="text-xs mt-2.5 leading-relaxed" style={{ color: T.body }}>{c.why}</p>
    {c.fix && (
      <p className="text-xs mt-1.5 leading-relaxed" style={{ color: T.tealDeep }}>
        <span className="font-semibold">Fix — </span>{c.fix}
      </p>
    )}
  </div>
);

const ResultPanel = ({ r }) => {
  const s = SEV[r.risk] || SEV.low;
  const findings = r.findings || [];
  const conflicts = r.conflicts || [];
  return (
    <div className="mt-4">
      <Card style={{ background: s.bg, borderColor: s.c + "40" }} className="px-5 py-4 mb-4">
        <div className="flex items-center justify-between gap-4">
          <div className="text-xs font-semibold uppercase" style={{ color: s.c, letterSpacing: ".08em" }}>
            Overall risk
          </div>
          <Badge sev={r.risk} />
        </div>
        <p className="text-sm mt-2 leading-relaxed" style={{ color: T.body }}>{r.summary}</p>
      </Card>

      {findings.length > 0 && (
        <>
          <SectionLabel>Regulatory findings ({findings.length})</SectionLabel>
          {findings.map((f, i) => <Finding key={i} f={f} />)}
        </>
      )}

      {conflicts.length > 0 && (
        <>
          <SectionLabel>Conflicts with prior communications ({conflicts.length})</SectionLabel>
          {conflicts.map((c, i) => <Conflict key={i} c={c} />)}
        </>
      )}

      {(r.visual?.length > 0 || r.operational?.length > 0) && (
        <>
          <SectionLabel>Cannot be verified from text</SectionLabel>
          <div className="grid gap-3" style={{ gridTemplateColumns: r.visual?.length && r.operational?.length ? "1fr 1fr" : "1fr" }}>
            {r.visual?.length > 0 && <Queue title="Visual check" items={r.visual}
              hint="Type sizes, footnote proximity, layout — confirm against final artwork." />}
            {r.operational?.length > 0 && <Queue title="Operational check" items={r.operational}
              hint="Benefit terms, QR destinations, origination systems — confirm with the owning team." />}
          </div>
        </>
      )}

      {r.passed?.length > 0 && (
        <p className="text-xs mt-3 leading-relaxed" style={{ color: T.mute }}>
          <span className="font-semibold">Reviewed and satisfactory: </span>
          <span style={{ fontFamily: MONO }}>{r.passed.join(" · ")}</span>
        </p>
      )}

      {findings.length === 0 && conflicts.length === 0 && (
        <Card><Empty icon={ShieldCheck} title="No issues found"
          hint="Nothing in this document tripped the selected frameworks." /></Card>
      )}
    </div>
  );
};

const Queue = ({ title, items, hint }) => (
  <Card className="px-4 py-3">
    <div className="text-sm font-semibold" style={{ color: T.ink }}>{title}</div>
    <div className="text-xs mt-0.5 mb-2" style={{ color: T.mute }}>{hint}</div>
    {items.map((it, i) => (
      <div key={i} className="flex gap-2 py-1">
        <span style={{ color: T.gold }}>▢</span>
        <span className="text-xs leading-relaxed" style={{ color: T.body }}>{it}</span>
      </div>
    ))}
  </Card>
);

const SectionLabel = ({ children }) => (
  <div className="text-xs font-semibold uppercase mt-5 mb-2"
    style={{ color: T.mute, letterSpacing: ".08em" }}>{children}</div>
);

/* ─────────────────────────────────────────────────────────────
   App
   ───────────────────────────────────────────────────────────── */
export default function ComplyLine() {
  const [page, setPage] = useState("dashboard");
  const [ready, setReady] = useState(false);
  const [checks, setChecks] = useState([]);
  const [memory, setMemory] = useState([]);
  const [library, setLibrary] = useState([]);
  const [revenue, setRevenue] = useState([]);

  useEffect(() => {
    (async () => {
      const [c, m, l, r] = await Promise.all([
        loadKey(KEYS.checks, []), loadKey(KEYS.memory, []),
        loadKey(KEYS.library, []), loadKey(KEYS.revenue, []),
      ]);
      setChecks(c); setMemory(m); setLibrary(l); setRevenue(r); setReady(true);
    })();
  }, []);

  const persistChecks  = useCallback(v => { setChecks(v);  saveKey(KEYS.checks, v.slice(0, 60)); }, []);
  const persistMemory  = useCallback(v => { setMemory(v);  saveKey(KEYS.memory, v); }, []);
  const persistLibrary = useCallback(v => { setLibrary(v); saveKey(KEYS.library, v); }, []);
  const persistRevenue = useCallback(v => { setRevenue(v); saveKey(KEYS.revenue, v.slice(0, 30)); }, []);

  const NAV = [
    { id: "dashboard", label: "Dashboard",           icon: LayoutGrid },
    { id: "check",     label: "Check a document",    icon: FilePlus2 },
    { id: "revenue",   label: "Pricing benchmark",   icon: TrendingUp, count: revenue.length },
    { id: "memory",    label: "Company memory",      icon: Building2, count: memory.length },
    { id: "library",   label: "Regulatory library",  icon: Library,   count: library.length },
    { id: "history",   label: "History",             icon: History,   count: checks.length },
    { id: "settings",  label: "Settings",            icon: Settings2 },
  ];

  return (
    <div className="flex" style={{ background: T.page, minHeight: 640, fontFamily: "ui-sans-serif, system-ui, sans-serif" }}>
      {/* Sidebar */}
      <aside className="shrink-0 flex flex-col" style={{ width: 208, background: T.navy }}>
        <div className="px-4 py-4 flex items-center gap-2.5"
          style={{ borderBottom: "1px solid rgba(255,255,255,.1)" }}>
          <div className="rounded flex items-center justify-center shrink-0"
            style={{ width: 28, height: 28, background: T.teal }}>
            <ShieldCheck size={16} color="#fff" />
          </div>
          <div>
            <div style={{ fontFamily: SERIF, color: "#fff" }} className="text-sm font-bold leading-none">
              ComplyLine
            </div>
            <div className="text-xs mt-0.5" style={{ color: "rgba(255,255,255,.45)" }}>Card compliance</div>
          </div>
        </div>

        <nav className="py-2 flex-1">
          {NAV.map(n => {
            const on = page === n.id;
            return (
              <button key={n.id} onClick={() => setPage(n.id)}
                className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-left"
                style={{
                  color: on ? "#fff" : "rgba(255,255,255,.62)",
                  background: on ? "rgba(255,255,255,.09)" : "transparent",
                  borderLeft: `2px solid ${on ? T.teal : "transparent"}`,
                  fontWeight: on ? 600 : 400, cursor: "pointer",
                }}>
                <n.icon size={15} className="shrink-0" />
                <span className="truncate">{n.label}</span>
                {n.count > 0 && (
                  <span className="ml-auto text-xs rounded-full px-1.5"
                    style={{ background: "rgba(255,255,255,.14)", color: "rgba(255,255,255,.8)" }}>
                    {n.count}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="px-4 py-3 text-xs leading-relaxed"
          style={{ borderTop: "1px solid rgba(255,255,255,.1)", color: "rgba(255,255,255,.4)" }}>
          Runs on Claude. No API key needed.
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-auto" style={{ maxHeight: "88vh" }}>
        <div className="px-7 py-6">
          {!ready ? (
            <div className="flex items-center gap-2 text-sm" style={{ color: T.mute }}>
              <Loader2 size={15} className="animate-spin" /> Loading your saved work…
            </div>
          ) : (
            <>
              {page === "dashboard" && <Dashboard checks={checks} memory={memory} library={library} revenue={revenue} go={setPage} />}
              {page === "check"     && <CheckView checks={checks} setChecks={persistChecks} memory={memory} library={library} />}
              {page === "revenue"   && <RevenueView runs={revenue} setRuns={persistRevenue} checks={checks} />}
              {page === "memory"    && <MemoryView memory={memory} setMemory={persistMemory} />}
              {page === "library"   && <LibraryView library={library} setLibrary={persistLibrary} />}
              {page === "history"   && <HistoryView checks={checks} setChecks={persistChecks} />}
              {page === "settings"  && <SettingsView checks={checks} memory={memory} library={library} revenue={revenue}
                                          reset={() => { persistChecks([]); persistMemory([]); persistLibrary([]); persistRevenue([]); }} />}
            </>
          )}
        </div>
      </main>
    </div>
  );
}

/* ── Dashboard ───────────────────────────────────────────────── */
function Dashboard({ checks, memory, library, revenue, go }) {
  const high = checks.filter(c => c.risk === "high").length;
  const conflicts = checks.reduce((n, c) => n + (c.conflicts?.length || 0), 0);
  const upside = (revenue[0]?.terms || [])
    .filter(t => t.status === "opportunity")
    .reduce((n, t) => n + (Number(t.impactUsd) || 0), 0);
  const stats = [
    ["Documents checked", checks.length, T.ink],
    ["High risk", high, T.high],
    ["Conflicts found", conflicts, T.med],
    [revenue.length ? "Annual pricing upside" : "Prior documents stored",
     revenue.length ? (upside ? `$${Math.round(upside / 1000)}k` : "—") : memory.length, T.teal],
  ];

  return (
    <>
      <PageTitle sub={today()}>Compliance overview</PageTitle>

      <div className="grid gap-3 mb-5" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        {stats.map(([label, n, color]) => (
          <Card key={label} className="px-4 py-3">
            <div style={{ fontFamily: SERIF, color, fontSize: 26, fontWeight: 700, lineHeight: 1.1 }}>{n}</div>
            <div className="text-xs mt-1" style={{ color: T.mute }}>{label}</div>
          </Card>
        ))}
      </div>

      <Card className="p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold" style={{ color: T.ink }}>Recent checks</div>
          <Button kind="teal" onClick={() => go("check")}><Plus size={14} /> Check a document</Button>
        </div>
        {checks.length === 0 ? (
          <Empty icon={FilePlus2} title="Nothing checked yet"
            hint="Paste marketing copy, a disclosure, or a script to run your first review." />
        ) : (
          <div>
            {checks.slice(0, 6).map(c => (
              <div key={c.id} className="flex items-center justify-between py-2.5"
                style={{ borderBottom: `1px solid ${T.line}` }}>
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate" style={{ color: T.ink }}>{c.title}</div>
                  <div className="text-xs" style={{ color: T.mute }}>
                    {c.date} · {c.findings?.length || 0} findings · {c.conflicts?.length || 0} conflicts
                  </div>
                </div>
                <Badge sev={c.risk} />
              </div>
            ))}
          </div>
        )}
      </Card>

      {memory.length === 0 && (
        <Card className="p-4 mt-4" style={{ background: "#FCF8EE", borderColor: "#EFE0BC" }}>
          <div className="flex gap-2.5">
            <AlertTriangle size={16} style={{ color: T.med }} className="shrink-0 mt-0.5" />
            <div className="text-xs leading-relaxed" style={{ color: T.body }}>
              <span className="font-semibold">Conflict detection is idle.</span>{" "}
              Add your prior marketing, policies, and agreements under Company memory. Every new
              document is then compared against them for contradictions.
            </div>
          </div>
        </Card>
      )}
    </>
  );
}

/* ── Check a document ────────────────────────────────────────── */
function CheckView({ checks, setChecks, memory, library }) {
  const [title, setTitle] = useState("");
  const [product, setProduct] = useState("");
  const [text, setText] = useState("");
  const [sel, setSel] = useState(new Set(REGS.map(r => r.id)));
  const [useMem, setUseMem] = useState(true);
  const [useLib, setUseLib] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState(null);

  const toggle = id => {
    const next = new Set(sel);
    next.has(id) ? next.delete(id) : next.add(id);
    setSel(next);
  };

  async function run() {
    if (!text.trim()) { setErr("Paste the document text before running a check."); return; }
    if (sel.size === 0) { setErr("Pick at least one framework to check against."); return; }
    setBusy(true); setErr(""); setResult(null);

    const regList = REGS.filter(r => sel.has(r.id)).map(r => `${r.label} (${r.full})`).join("; ");
    const memCtx = useMem && memory.length
      ? "\n\nPRIOR COMPANY COMMUNICATIONS (check the document for contradictions against these):\n" +
        memory.slice(0, 6).map(m => `[${m.name} — ${m.type}${m.product ? `, ${m.product}` : ""}]\n${m.text.slice(0, 400)}`).join("\n\n")
      : "";
    const libCtx = useLib && library.length
      ? "\n\nREGULATORY REFERENCE (use for precise citations):\n" +
        library.slice(0, 4).map(d => `[${d.agency} — ${d.name}]\n${d.text.slice(0, 400)}`).join("\n\n")
      : "";

    const prompt =
`You are a senior in-house counsel reviewing a credit card mailing before it drops. Apply the specificity a regulator or plaintiffs' attorney would.

FRAMEWORKS: ${regList}
PRODUCT: ${product || "unspecified"}${libCtx}${memCtx}

DOCUMENT:
"""
${text.slice(0, 3500)}
"""

CHECKLIST — work through every item that applies. Put the item that fired in "ref".
A1 headline vs footnote numeric or temporal drift ("first three months" vs "90 days")
A2 footnote symbol (*, dagger) with no footnote text on that same piece
A3 prominent claim whose required disclosure sits on a different piece
B1 Schumer Box rows complete (purchase/BT/cash APR, penalty APR, grace, min interest, annual fee, transaction fees, penalty fees, CFPB URL)
B2 variable APR "accurate as of [date]" statement — Reg Z 1026.60(b)(4), 1026.5(d)(1)
B3 late fee vs CARD Act safe harbor ($32 first / $43 subsequent, post-5th-Circuit vacatur)
B4 payment allocation above-minimum to highest APR — 1026.53
B5 rate-increase triggers vs 1026.55 first-year restriction and 1026.9(c) 45-day notice
B6 grace period at least 21 days — 1026.5(b)(2)(ii)
B7 CFPB URL references consumerfinance.gov — 1026.60(a)(2)
B8 balance calculation method disclosed — 1026.60(b)(4)
B9 penalty APR trigger event and duration disclosed
C1 FCRA short prescreen notice type size vs body text — 16 CFR 642.3(a) — VISUAL
C2 FCRA long notice boxed, 12pt minimum, contrasting type — 642.3(b) — VISUAL
C3 long notice content: credit-report basis, criteria, right to terminate, opt-out phone, optoutprescreen.com, all three CRA addresses
C4 firm-offer narrow grounds — FCRA 604(c) — flag language implying discretionary denial
D1 rewards claim ("UNLIMITED", "X% cash back") footnote adjacent on EVERY piece
D2 benefit claims (price match, extended warranty, trip protection) tie to documented terms — OPERATIONAL
D3 definitive operational claims ("start shopping ASAP", "same day") — soften unless guaranteed
D4 urgency and exclusivity supported by actual program structure
D5 prequalification language not readable as guaranteed approval
E1 state equal-credit notices (CA, OH, NY minimum)
E2 geographic exclusions — flag for disparate-impact review
E4 "subject to credit approval" or equivalent present
F1 MLA disclosure with 36% MAPR language and audio-access phone — 32 CFR 232.6
F2 MLA database check at origination — OPERATIONAL
G1 multi-piece package (artwork codes -OE envelope, -LT letter, -FC cover, -BS buckslip, -DS disclosure): check footnote coverage per piece
G2 version codes match across pieces
H1 QR or URL destination repeats Schumer Box and prescreen notice — OPERATIONAL

Return ONLY minified JSON, no prose and no markdown fence:
{"risk":"high|medium|low|pass","summary":"1-2 sentences","findings":[{"reg":"framework","ref":"A1","sev":"high|medium|low|pass","issue":"short title","detail":"1-2 sentences","cite":"exact CFR section","fix":"1 sentence"}],"conflicts":[{"sev":"high|medium|low","title":"","new":"what this document says","prior":"what the prior document says","source":"prior document name","why":"1 sentence","fix":"1 sentence"}],"visual":["item that text extraction cannot verify"],"operational":["item needing external systems"],"passed":["B1","B4"]}

Rules: at most 6 findings, most severe first. Every string under 180 characters. Never silently assume compliance — anything you cannot confirm from text goes in "visual" or "operational". "passed" lists refs you reviewed and found satisfactory. ${memCtx ? "Populate conflicts only for real contradictions with the prior communications above." : "Leave conflicts as an empty array."}`;

    try {
      const r = await askClaude(prompt);
      const entry = {
        id: uid(),
        title: title.trim() || "Untitled document",
        product: product.trim(),
        date: today(),
        risk: r.risk || "low",
        summary: r.summary || "",
        findings: r.findings || [],
        conflicts: r.conflicts || [],
        visual: r.visual || [],
        operational: r.operational || [],
        passed: r.passed || [],
        excerpt: text.slice(0, 400),
      };
      setResult(entry);
      setChecks([entry, ...checks]);
    } catch (e) {
      setErr(e.message);
    }
    setBusy(false);
  }

  return (
    <>
      <PageTitle sub="Checked against the frameworks you select, your stored policies, and your regulatory library.">
        Check a document
      </PageTitle>

      <Card className="p-5">
        <div className="grid gap-3" style={{ gridTemplateColumns: "2fr 1fr" }}>
          <div>
            <Label>Document title</Label>
            <input style={inputStyle} value={title} onChange={e => setTitle(e.target.value)}
              placeholder="Q3 acquisition mailer" />
          </div>
          <div>
            <Label>Product</Label>
            <input style={inputStyle} value={product} onChange={e => setProduct(e.target.value)}
              placeholder="Premier card" />
          </div>
        </div>

        <Label>Document text</Label>
        <textarea style={{ ...inputStyle, minHeight: 150, lineHeight: 1.5, resize: "vertical" }}
          value={text} onChange={e => setText(e.target.value)}
          placeholder="Paste marketing copy, a disclosure, a cardholder agreement, or a collections script…" />
        <div className="text-xs mt-1 text-right" style={{ color: T.mute }}>
          {text.length.toLocaleString()} characters
        </div>

        <Label>Frameworks</Label>
        <div className="flex flex-wrap gap-1.5">
          {REGS.map(r => {
            const on = sel.has(r.id);
            return (
              <button key={r.id} onClick={() => toggle(r.id)} title={r.full}
                className="rounded-full px-3 py-1 text-xs font-medium"
                style={{
                  cursor: "pointer",
                  color: on ? "#fff" : T.mute,
                  background: on ? T.navyMid : "#fff",
                  border: `1px solid ${on ? T.navyMid : T.line}`,
                }}>
                {r.label}
              </button>
            );
          })}
        </div>

        <div className="flex flex-wrap gap-5 mt-4">
          <Check label={`Compare against company memory (${memory.length})`} on={useMem} set={setUseMem} disabled={!memory.length} />
          <Check label={`Cite from regulatory library (${library.length})`} on={useLib} set={setUseLib} disabled={!library.length} />
        </div>

        {err && (
          <div className="mt-4 rounded-md px-3 py-2 text-xs"
            style={{ background: T.highBg, color: T.high, border: "1px solid #F0D5D3" }}>{err}</div>
        )}

        <div className="mt-4 flex gap-2">
          <Button onClick={run} disabled={busy}>
            {busy ? <><Loader2 size={14} className="animate-spin" /> Analyzing…</> : <><ShieldCheck size={14} /> Run compliance check</>}
          </Button>
          <Button kind="ghost" onClick={() => { setText(""); setTitle(""); setProduct(""); setResult(null); setErr(""); }}>
            Clear
          </Button>
        </div>
      </Card>

      {result && <ResultPanel r={result} />}
    </>
  );
}

const Check = ({ label, on, set, disabled }) => (
  <label className="flex items-center gap-2 text-xs" style={{ color: disabled ? T.mute : T.body, cursor: disabled ? "default" : "pointer" }}>
    <input type="checkbox" checked={on && !disabled} disabled={disabled}
      onChange={e => set(e.target.checked)} style={{ accentColor: T.teal }} />
    {label}
  </label>
);

/* ── Company memory ──────────────────────────────────────────── */
function MemoryView({ memory, setMemory }) {
  const [f, setF] = useState({ name: "", type: "marketing", product: "", date: "", text: "" });
  const set = (k, v) => setF({ ...f, [k]: v });

  const add = () => {
    if (!f.name.trim() || !f.text.trim()) return;
    setMemory([{ id: uid(), ...f, name: f.name.trim(), text: f.text.trim() }, ...memory]);
    setF({ name: "", type: "marketing", product: "", date: "", text: "" });
  };

  return (
    <>
      <PageTitle sub="Your prior marketing, policies, agreements, and scripts. Every new check looks for contradictions against these.">
        Company memory
      </PageTitle>

      <Card className="p-5 mb-4">
        <div className="grid gap-3" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <div>
            <Label>Document name</Label>
            <input style={inputStyle} value={f.name} onChange={e => set("name", e.target.value)}
              placeholder="Q1 rewards email" />
          </div>
          <div>
            <Label>Type</Label>
            <select style={inputStyle} value={f.type} onChange={e => set("type", e.target.value)}>
              {DOC_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div>
            <Label>Product</Label>
            <input style={inputStyle} value={f.product} onChange={e => set("product", e.target.value)}
              placeholder="Premier card" />
          </div>
          <div>
            <Label>Date</Label>
            <input style={inputStyle} value={f.date} onChange={e => set("date", e.target.value)}
              placeholder="2025-03-01" />
          </div>
        </div>
        <Label>Content</Label>
        <textarea style={{ ...inputStyle, minHeight: 100, lineHeight: 1.5, resize: "vertical" }}
          value={f.text} onChange={e => set("text", e.target.value)}
          placeholder="Paste what this document actually said to customers…" />
        <div className="mt-3">
          <Button onClick={add} disabled={!f.name.trim() || !f.text.trim()}>
            <Plus size={14} /> Add to memory
          </Button>
        </div>
      </Card>

      <Card>
        {memory.length === 0 ? (
          <Empty icon={Building2} title="No prior documents stored"
            hint="Add past campaigns and policies so contradictions surface automatically." />
        ) : memory.map(m => (
          <Row key={m.id} onDelete={() => setMemory(memory.filter(x => x.id !== m.id))}
            title={m.name}
            meta={[DOC_TYPES.find(d => d[0] === m.type)?.[1], m.product, m.date].filter(Boolean).join(" · ")}
            body={m.text.slice(0, 120) + (m.text.length > 120 ? "…" : "")} />
        ))}
      </Card>
    </>
  );
}

/* ── Regulatory library ──────────────────────────────────────── */
function LibraryView({ library, setLibrary }) {
  const [f, setF] = useState({ name: "", agency: "CFPB", cat: "udaap", url: "", text: "" });
  const set = (k, v) => setF({ ...f, [k]: v });

  const add = () => {
    if (!f.name.trim() || !f.text.trim()) return;
    setLibrary([{ id: uid(), ...f, name: f.name.trim(), text: f.text.trim() }, ...library]);
    setF({ name: "", agency: f.agency, cat: f.cat, url: "", text: "" });
  };

  const byAgency = library.reduce((acc, d) => {
    (acc[d.agency] = acc[d.agency] || []).push(d);
    return acc;
  }, {});

  return (
    <>
      <PageTitle sub="Official rule text, grouped by the agency that issued it. Checks cite from these instead of relying on memory alone.">
        Regulatory library
      </PageTitle>

      <Card className="p-5 mb-4">
        <div className="grid gap-3" style={{ gridTemplateColumns: "2fr 1fr 1fr" }}>
          <div>
            <Label>Title</Label>
            <input style={inputStyle} value={f.name} onChange={e => set("name", e.target.value)}
              placeholder="Reg Z §1026.16 advertising rules" />
          </div>
          <div>
            <Label>Agency</Label>
            <select style={inputStyle} value={f.agency} onChange={e => set("agency", e.target.value)}>
              {AGENCIES.map(a => <option key={a}>{a}</option>)}
            </select>
          </div>
          <div>
            <Label>Framework</Label>
            <select style={inputStyle} value={f.cat} onChange={e => set("cat", e.target.value)}>
              {REGS.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
            </select>
          </div>
        </div>
        <Label>Rule text</Label>
        <textarea style={{ ...inputStyle, minHeight: 100, lineHeight: 1.5, resize: "vertical" }}
          value={f.text} onChange={e => set("text", e.target.value)}
          placeholder="Paste the section text, guidance, or exam manual excerpt…" />
        <div className="mt-3">
          <Button onClick={add} disabled={!f.name.trim() || !f.text.trim()}>
            <Plus size={14} /> Add to library
          </Button>
        </div>
      </Card>

      {library.length === 0 ? (
        <Card><Empty icon={Library} title="The library is empty"
          hint="Paste rule text from CFPB, the Fed, OCC, or your state regulator to ground every citation." /></Card>
      ) : Object.entries(byAgency).map(([agency, docs]) => (
        <Card key={agency} className="mb-3">
          <div className="px-4 py-2.5 flex items-center gap-2"
            style={{ borderBottom: `1px solid ${T.line}`, background: "#FAFBFD" }}>
            <ScrollText size={14} style={{ color: T.teal }} />
            <span className="text-sm font-semibold" style={{ color: T.ink }}>{agency}</span>
            <span className="text-xs" style={{ color: T.mute }}>{docs.length}</span>
          </div>
          {docs.map(d => (
            <Row key={d.id} onDelete={() => setLibrary(library.filter(x => x.id !== d.id))}
              title={d.name}
              meta={`${REGS.find(r => r.id === d.cat)?.label || d.cat} · ${d.text.length.toLocaleString()} characters`}
              body={d.text.slice(0, 120) + (d.text.length > 120 ? "…" : "")} />
          ))}
        </Card>
      ))}
    </>
  );
}

/* ── History ─────────────────────────────────────────────────── */
function HistoryView({ checks, setChecks }) {
  const [open, setOpen] = useState(null);
  const shown = checks.find(c => c.id === open);

  if (shown) return (
    <>
      <Button kind="ghost" onClick={() => setOpen(null)}>← Back to history</Button>
      <div className="mt-4">
        <PageTitle sub={`${shown.date}${shown.product ? ` · ${shown.product}` : ""}`}>{shown.title}</PageTitle>
        <ResultPanel r={shown} />
      </div>
    </>
  );

  return (
    <>
      <PageTitle sub="Every check you have run, kept between sessions.">History</PageTitle>
      <Card>
        {checks.length === 0 ? (
          <Empty icon={History} title="No checks yet" hint="Your completed reviews will collect here." />
        ) : checks.map(c => (
          <div key={c.id} className="flex items-center justify-between px-4 py-3"
            style={{ borderBottom: `1px solid ${T.line}` }}>
            <button onClick={() => setOpen(c.id)} className="text-left min-w-0 flex-1" style={{ cursor: "pointer" }}>
              <div className="text-sm font-medium truncate" style={{ color: T.ink }}>{c.title}</div>
              <div className="text-xs" style={{ color: T.mute }}>
                {c.date} · {c.findings?.length || 0} findings · {c.conflicts?.length || 0} conflicts
              </div>
            </button>
            <div className="flex items-center gap-3 shrink-0 ml-3">
              <Badge sev={c.risk} />
              <button onClick={() => setChecks(checks.filter(x => x.id !== c.id))}
                style={{ cursor: "pointer", background: "none", border: "none" }}>
                <Trash2 size={14} style={{ color: T.mute }} />
              </button>
            </div>
          </div>
        ))}
      </Card>
    </>
  );
}

/* ── Settings ────────────────────────────────────────────────── */
function SettingsView({ checks, memory, library, revenue = [], reset }) {
  const [confirm, setConfirm] = useState(false);

  const download = () => {
    const blob = new Blob([JSON.stringify({ checks, memory, library, revenue }, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "complyline-export.json";
    a.click();
  };

  return (
    <>
      <PageTitle sub="Everything is stored privately to your account and persists between sessions.">Settings</PageTitle>

      <Card className="p-5 mb-4">
        <div className="text-sm font-semibold mb-3" style={{ color: T.ink }}>What is stored</div>
        {[["Checks", checks.length], ["Pricing benchmarks", revenue.length],
          ["Prior documents", memory.length], ["Library entries", library.length]].map(([l, n]) => (
          <div key={l} className="flex justify-between py-1.5 text-sm" style={{ color: T.body }}>
            <span>{l}</span><span style={{ fontFamily: MONO }}>{n}</span>
          </div>
        ))}
        <div className="mt-4 flex gap-2">
          <Button kind="ghost" onClick={download}><Download size={14} /> Export as JSON</Button>
          {confirm ? (
            <>
              <Button kind="danger" onClick={() => { reset(); setConfirm(false); }}>Yes, delete everything</Button>
              <Button kind="ghost" onClick={() => setConfirm(false)}>Keep it</Button>
            </>
          ) : (
            <Button kind="danger" onClick={() => setConfirm(true)}><Trash2 size={14} /> Clear all data</Button>
          )}
        </div>
      </Card>

      <Card className="p-5">
        <div className="text-sm font-semibold mb-2" style={{ color: T.ink }}>How the analysis runs</div>
        <p className="text-xs leading-relaxed" style={{ color: T.body }}>
          Checks are analyzed by Claude from inside this app, so there is no API key to manage and
          nothing to install. Document text is sent to Anthropic for the analysis and is not stored
          on a server beyond that call. This tool supports review work; it is not legal advice.
        </p>
      </Card>
    </>
  );
}

/* ── Pricing benchmark ───────────────────────────────────────── */
function RevenueView({ runs, setRuns, checks }) {
  const [text, setText] = useState("");
  const [accounts, setAccounts] = useState("100000");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState(runs[0]?.id || null);

  const shown = runs.find(r => r.id === open) || runs[0];

  async function run() {
    if (!text.trim()) { setErr("Paste the product terms — the Schumer box, fee schedule, or rewards terms."); return; }
    setBusy(true); setErr("");

    const n = Number(accounts.replace(/\D/g, "")) || 100000;
    const prompt =
`You are a credit card pricing analyst benchmarking a product against US market norms and federal ceilings.

PORTFOLIO: ${n.toLocaleString()} active accounts

PRODUCT TERMS:
"""
${text.slice(0, 3500)}
"""

Return ONLY minified JSON, no prose and no markdown fence:
{"tier":"no-fee|mid-fee|premium","summary":"2 sentences","terms":[{"name":"","current":"","benchmark":"","regMax":"","status":"violation|above_market|opportunity|at_market","impactUsd":0,"impact":"$45k/yr","rec":"","risk":""}]}

HARD RULES — these override any revenue consideration:
1. Total first-year fees may not exceed 25% of the initial credit line (12 CFR 1026.52(a)). If the terms breach it, status is "violation" and rec is the remediation, not an opportunity.
2. The 36% Military Lending Act ceiling is MAPR — all-in including fees, not an APR ceiling. Card fees escape MAPR only under the bona fide fee exception, which requires the fee be reasonable against what other issuers charge. Any above-market fee puts that exception at risk; say so in "risk".
3. Never justify a recommendation on consumers failing to understand a cost. That is the abusive prong of 12 U.S.C. 5531(d). Justify on transaction economics instead.
4. impactUsd is the annual dollar impact for the stated portfolio as a plain number, 0 if unquantifiable. "impact" is that figure formatted.
5. At most 8 terms, ordered by impactUsd descending, violations first. Every string under 150 characters.
6. "risk" carries any UDAAP, MLA, fair-lending, or CARD Act caution attached to acting on the term. Empty string if none.`;

    try {
      const r = await askClaude(prompt);
      const entry = {
        id: uid(), date: today(), accounts: n,
        tier: r.tier || "unknown", summary: r.summary || "",
        terms: (r.terms || []).sort((a, b) =>
          (a.status === "violation" ? -1 : b.status === "violation" ? 1 : 0) ||
          (Number(b.impactUsd) || 0) - (Number(a.impactUsd) || 0)),
      };
      const next = [entry, ...runs];
      setRuns(next); setOpen(entry.id);
    } catch (e) { setErr(e.message); }
    setBusy(false);
  }

  const lastCheck = checks[0];
  const tally = shown ? shown.terms.reduce((a, t) => ({ ...a, [t.status]: (a[t.status] || 0) + 1 }), {}) : {};
  const upside = shown ? shown.terms.filter(t => t.status === "opportunity")
    .reduce((n, t) => n + (Number(t.impactUsd) || 0), 0) : 0;

  return (
    <>
      <PageTitle sub="Benchmarks pricing terms against market norms and federal ceilings. Regulatory caps are walls, not suggestions.">
        Pricing benchmark
      </PageTitle>

      <Card className="p-5">
        <Label>Product terms</Label>
        <textarea style={{ ...inputStyle, minHeight: 120, lineHeight: 1.5, resize: "vertical" }}
          value={text} onChange={e => setText(e.target.value)}
          placeholder="Paste the Schumer box, fee schedule, APR table, and rewards terms…" />
        {lastCheck && !text && (
          <button onClick={() => setText(lastCheck.excerpt || "")}
            className="text-xs mt-1.5" style={{ color: T.teal, cursor: "pointer", background: "none", border: "none", padding: 0 }}>
            Use the last document you checked — {lastCheck.title}
          </button>
        )}

        <div className="grid gap-3 mt-1" style={{ gridTemplateColumns: "200px 1fr" }}>
          <div>
            <Label>Active accounts</Label>
            <input style={inputStyle} value={accounts} onChange={e => setAccounts(e.target.value)} placeholder="100000" />
          </div>
          <div className="flex items-end">
            <p className="text-xs leading-relaxed pb-2" style={{ color: T.mute }}>
              Every opportunity is sized in annual dollars against this portfolio, so a $3 fee change
              can't outrank a structural one.
            </p>
          </div>
        </div>

        {err && (
          <div className="mt-3 rounded-md px-3 py-2 text-xs"
            style={{ background: T.highBg, color: T.high, border: "1px solid #F0D5D3" }}>{err}</div>
        )}

        <div className="mt-4">
          <Button onClick={run} disabled={busy}>
            {busy ? <><Loader2 size={14} className="animate-spin" /> Benchmarking…</> : <><TrendingUp size={14} /> Run benchmark</>}
          </Button>
        </div>
      </Card>

      {!shown ? (
        <Card className="mt-4"><Empty icon={TrendingUp} title="No benchmark yet"
          hint="Paste a fee schedule or Schumer box to see where the product sits against market." /></Card>
      ) : (
        <>
          <Card className="px-5 py-4 mt-4">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <div>
                <div className="text-xs uppercase font-semibold" style={{ color: T.mute, letterSpacing: ".08em" }}>
                  {shown.tier} tier · {shown.terms.length} terms · {shown.accounts.toLocaleString()} accounts
                </div>
                <p className="text-sm mt-1.5 leading-relaxed" style={{ color: T.body }}>{shown.summary}</p>
              </div>
              <div className="text-right shrink-0">
                <div style={{ fontFamily: SERIF, color: T.teal, fontSize: 26, fontWeight: 700, lineHeight: 1 }}>
                  {upside ? `$${Math.round(upside / 1000)}k` : "—"}
                </div>
                <div className="text-xs" style={{ color: T.mute }}>annual upside</div>
              </div>
            </div>
            <div className="flex gap-1.5 mt-3 flex-wrap">
              {Object.entries(STATUS).map(([k, s]) => tally[k] ? (
                <span key={k} className="text-xs rounded px-2 py-0.5 font-semibold"
                  style={{ color: s.c, background: s.bg }}>{tally[k]} {s.label.toLowerCase()}</span>
              ) : null)}
            </div>
          </Card>

          {shown.terms.map((t, i) => <Term key={i} t={t} />)}

          <p className="text-xs mt-4 leading-relaxed" style={{ color: T.mute }}>
            Repricing an existing account needs 45 days' notice under Reg Z §1026.9(c) and is
            restricted in the first year by CARD Act §171. Nothing here substitutes for pricing
            committee and fair-lending review.
          </p>

          {runs.length > 1 && (
            <>
              <SectionLabel>Earlier benchmarks</SectionLabel>
              <Card>
                {runs.map(r => (
                  <div key={r.id} className="flex items-center justify-between px-4 py-2.5"
                    style={{ borderBottom: `1px solid ${T.line}` }}>
                    <button onClick={() => setOpen(r.id)} className="text-left flex-1"
                      style={{ cursor: "pointer", background: "none", border: "none", padding: 0 }}>
                      <div className="text-sm" style={{ color: r.id === shown.id ? T.teal : T.ink, fontWeight: r.id === shown.id ? 600 : 400 }}>
                        {r.date} · {r.tier} tier · {r.terms.length} terms
                      </div>
                    </button>
                    <button onClick={() => setRuns(runs.filter(x => x.id !== r.id))}
                      style={{ cursor: "pointer", background: "none", border: "none" }}>
                      <Trash2 size={14} style={{ color: T.mute }} />
                    </button>
                  </div>
                ))}
              </Card>
            </>
          )}
        </>
      )}
    </>
  );
}

const Term = ({ t }) => {
  const s = STATUS[t.status] || STATUS.at_market;
  const isViolation = t.status === "violation";
  return (
    <div className="mt-2 rounded-r-md px-4 py-3"
      style={{ borderLeft: `3px solid ${s.c}`, background: s.bg }}>
      <div className="flex items-start justify-between gap-3">
        <div className="text-sm font-semibold flex items-center gap-1.5" style={{ color: T.ink }}>
          {isViolation && <Ban size={13} style={{ color: s.c }} />}
          {t.name}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {t.impact && t.impact !== "N/A" && !isViolation && (
            <span className="text-xs font-semibold" style={{ color: T.tealDeep, fontFamily: MONO }}>{t.impact}</span>
          )}
          <span className="text-xs rounded px-2 py-0.5 font-semibold" style={{ color: s.c, background: "#fff" }}>
            {s.label}
          </span>
        </div>
      </div>

      <div className="grid gap-x-4 gap-y-1 mt-2.5" style={{ gridTemplateColumns: "auto 1fr" }}>
        {[["Current", t.current], ["Market", t.benchmark], ["Ceiling", t.regMax]].map(([k, v]) => v ? (
          <React.Fragment key={k}>
            <div className="text-xs" style={{ color: T.mute }}>{k}</div>
            <div className="text-xs" style={{ color: T.body, fontFamily: k === "Current" ? MONO : "inherit" }}>{v}</div>
          </React.Fragment>
        ) : null)}
      </div>

      {t.rec && (
        <p className="text-xs mt-2.5 leading-relaxed" style={{ color: isViolation ? s.c : T.body }}>
          <span className="font-semibold">{isViolation ? "Required — " : "Move — "}</span>{t.rec}
        </p>
      )}
      {t.risk && (
        <div className="flex gap-1.5 mt-2 rounded px-2.5 py-1.5" style={{ background: "#fff", border: `1px solid ${T.line}` }}>
          <AlertTriangle size={12} style={{ color: T.med }} className="shrink-0 mt-0.5" />
          <p className="text-xs leading-relaxed" style={{ color: T.body }}>{t.risk}</p>
        </div>
      )}
    </div>
  );
};

/* ── Shared row ──────────────────────────────────────────────── */
const Row = ({ title, meta, body, onDelete }) => (
  <div className="flex items-start justify-between gap-3 px-4 py-3" style={{ borderBottom: `1px solid ${T.line}` }}>
    <div className="min-w-0">
      <div className="text-sm font-medium" style={{ color: T.ink }}>{title}</div>
      {meta && <div className="text-xs mt-0.5" style={{ color: T.mute }}>{meta}</div>}
      {body && <div className="text-xs mt-1 leading-relaxed" style={{ color: T.body }}>{body}</div>}
    </div>
    <button onClick={onDelete} className="shrink-0" style={{ cursor: "pointer", background: "none", border: "none" }}>
      <Trash2 size={14} style={{ color: T.mute }} />
    </button>
  </div>
);
