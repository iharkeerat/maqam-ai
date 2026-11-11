"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  eventSyllables, solveFormal, solveFormalBudgeted, validateFormalCase,
  type FormalCase, type FormalResult,
} from "../lib/formal-alignment";
import "./alignment-lab.css";

type Preset = {
  label: string;
  explanation: string;
  candidates: string;
  events: string;
  cycle: string;
  boundary: string;
  lockIndex: string;
  lockSyllable: string;
};
const presets: Preset[] = [
  { label: "Early commitment", explanation: "Top-1 has three constructed syllables but only two events; second candidate can align.",
    candidates: "a b c\na b", events: "1,1", cycle: "2", boundary: "", lockIndex: "", lockSyllable: "" },
  { label: "Locked event", explanation: "A locked token eliminates the first candidate; a different formal path remains feasible.",
    candidates: "a b\na c", events: "1,1", cycle: "2", boundary: "", lockIndex: "1", lockSyllable: "c" },
  { label: "Boundary", explanation: "A mid-phrase boundary changes which groupings are allowed.",
    candidates: "a b\na b c d", events: "1,1,1,1", cycle: "4", boundary: "2", lockIndex: "", lockSyllable: "" },
  { label: "Impossible", explanation: "Neither constructed option can satisfy the locked token.",
    candidates: "x\ny", events: "1,1,1,1", cycle: "4", boundary: "2", lockIndex: "0", lockSyllable: "z" },
];

function parseIntegers(raw: string, separator: RegExp): number[] {
  if (!raw.trim()) return [];
  const parts = raw.trim().split(separator).filter(Boolean);
  if (parts.some(p => !/^\d+$/.test(p))) throw new Error("Durations, boundaries and indexes must be non-negative integers.");
  return parts.map(Number);
}
function constructCase(p: Preset, maxPerSyllable: number): FormalCase {
  const events = parseIntegers(p.events, /[,\s]+/);
  const cycle = Number(p.cycle);
  if (!/^\d+$/.test(p.cycle.trim())) throw new Error("Cycle length must be an integer.");
  const rows = p.candidates.split("\n").map(row => row.trim()).filter(Boolean);
  if (rows.length > 16) throw new Error("Maximum 16 formal candidates.");
  const candidates = rows.map((row, i) => ({ key: `p${i + 1}`, syllables: row.split(/\s+/), prior: i }));
  const lockedEvents = (p.lockIndex.trim() || p.lockSyllable.trim()) ? [
    { event: parseIntegers(p.lockIndex, /[,\s]+/)[0], syllable: p.lockSyllable.trim() },
  ] : [];
  const caseObj: FormalCase = {
    key: "interactive_formal_demo",
    candidates,
    rhythm: {
      events, cycleTicks: cycle, minSyllableTicks: 1,
      maxSyllableTicks: 16, maxEventsPerSyllable: maxPerSyllable,
      boundaries: parseIntegers(p.boundary, /[,\s]+/), lockedEvents,
    },
    provenance: "constructed_formal_only",
  };
  const issues = validateFormalCase(caseObj);
  if (issues.length) throw new Error(issues.join(" "));
  return caseObj;
}

function Answer({ label, result, basis }: { label: string; result: FormalResult; basis?: FormalCase }) {
  const colors = result.status === "FEASIBLE" ? "success" : result.status === "INCOMPLETE" ? "caution" : "failure";
  return <article className={`formal-result formal-${colors}`}>
    <div className="formal-result-head"><strong>{label}</strong><span>{result.status}</span></div>
    {result.solution ? <>
      <p><b>{result.solution.candidateKey}</b> · cost {result.solution.cost} · event ends [{result.solution.ends.join(", ")}]</p>
      {basis && <div className="formal-tick-row" aria-label="Syllables aligned to events">
        {eventSyllables(basis, result.solution).map((token, i) => <div key={i}><small>e{i}</small><strong>{token}</strong><small>{basis.rhythm.events[i]}t</small></div>)}
      </div>}
    </> : <p>{result.note ?? (result.status === "INFEASIBLE" ? "No solution satisfies the stated formal constraints." : "Formal search unfinished.")}</p>}
    <small>{result.expansions} algorithm operations / states (not a comparable runtime metric)</small>
  </article>;
}

export default function AlignmentLabPage() {
  const [selectedPreset, setSelectedPreset] = useState(0);
  const [values, setValues] = useState<Preset>(presets[0]);
  const [maxSpan, setMaxSpan] = useState(2);
  const [budget, setBudget] = useState(4);
  const [showResults, setShowResults] = useState(true);
  const [validated, setValidated] = useState<Preset>(presets[0]);
  const [committedMaxSpan, setCommittedMaxSpan] = useState(2);
  const [committedBudget, setCommittedBudget] = useState(4);
  const outcomes = useMemo(() => {
    try {
      const item = constructCase(validated, committedMaxSpan);
      return { item, top1: solveFormal(item, 1), top2: solveFormal(item, 2), exact: solveFormal(item), limited: solveFormalBudgeted(item, committedBudget), error: "" };
    } catch (err) {
      return { item: null, top1: null, top2: null, exact: null, limited: null, error: err instanceof Error ? err.message : "Unexpected error." };
    }
  }, [validated, committedMaxSpan, committedBudget]);
  const update = (name: keyof Preset, value: string) => { setValues(v => ({ ...v, [name]: value })); setShowResults(false); };
  const choosePreset = (idx: number) => { setSelectedPreset(idx); setValues({ ...presets[idx] }); setValidated({ ...presets[idx] }); setMaxSpan(2); setCommittedMaxSpan(2); setBudget(4); setCommittedBudget(4); setShowResults(true); };
  const run = () => { setValidated({ ...values }); setCommittedMaxSpan(maxSpan); setCommittedBudget(budget); setShowResults(true); };
  return <main className="formal-page">
    <header className="formal-header"><Link className="formal-brand" href="/"><b>MAQAM</b> AI <span>/ ALIGNMENT LAB</span></Link><nav aria-label="Research navigation"><Link href="/">Workbench</Link><Link href="/research">Research ledger</Link></nav></header>
    <div className="formal-wrap">
      <section className="formal-hero">
        <p className="formal-eyebrow">RESEARCH MODULE 19 / INTERACTIVE FORMAL DEMONSTRATOR</p>
        <h1>When an alignment <em>looks impossible.</em></h1>
        <p>Explore how committing to a single syllable sequence can discard formally feasible options. Compare a Top-1 choice with exact search and a deliberately budget-limited search.</p>
        <div className="formal-warning"><b>FORMAL DEMO — NOT LANGUAGE VALIDATION</b><br/>The syllables are constructed tokens, not attested Hindi/Punjabi pronunciations. Cycles are abstract ticks, not validated Taal performances. No claim of artistic suitability or novel algorithms.</div>
      </section>
      <div className="formal-layout">
        <section className="formal-editor" aria-label="Constructed case editor">
          <div className="formal-panel-heading"><span>01 / Configure a formal task</span><h2>Input specification</h2></div>
          <label>Predefined examples</label>
          <div className="formal-presets" role="group" aria-label="Formal example presets">{presets.map((preset, i) => <button key={preset.label} type="button" className={selectedPreset === i ? "active" : ""} onClick={() => choosePreset(i)}>{preset.label}</button>)}</div>
          <p className="formal-help">{presets[selectedPreset].explanation}</p>
          <label htmlFor="formalCandidates">Candidate syllable paths · one per line, space-separated tokens</label>
          <textarea id="formalCandidates" spellCheck={false} rows={4} value={values.candidates} onChange={e => update("candidates", e.target.value)} />
          <div className="formal-field-grid">
            <div><label htmlFor="formalEvents">Event durations (ticks)</label><input id="formalEvents" value={values.events} onChange={e => update("events", e.target.value)} placeholder="1,1,1,1"/></div>
            <div><label htmlFor="formalCycle">Formal cycle length</label><input id="formalCycle" value={values.cycle} onChange={e => update("cycle", e.target.value)} inputMode="numeric" /></div>
            <div><label htmlFor="formalBoundaries">Phrase boundaries (ticks)</label><input id="formalBoundaries" value={values.boundary} onChange={e => update("boundary", e.target.value)} placeholder="none" /></div>
            <div><label htmlFor="formalSpan">Max events / syllable</label><select id="formalSpan" value={maxSpan} onChange={e => {setMaxSpan(Number(e.target.value)); setShowResults(false);}}>{[1,2,3,4,5].map(n => <option key={n} value={n}>{n}</option>)}</select></div>
            <div><label htmlFor="formalLockEvent">Lock event index (0-based)</label><input id="formalLockEvent" value={values.lockIndex} onChange={e => update("lockIndex", e.target.value)} placeholder="none"/></div>
            <div><label htmlFor="formalLockToken">Required locked token</label><input id="formalLockToken" value={values.lockSyllable} onChange={e => update("lockSyllable", e.target.value)} placeholder="none"/></div>
            <div><label htmlFor="formalBudget">Graph search state budget</label><select id="formalBudget" value={budget} onChange={e => {setBudget(Number(e.target.value)); setShowResults(false);}}>{[1,2,4,8,16,32,64,128,512].map(n => <option value={n} key={n}>{n} states</option>)}</select></div>
          </div>
          <button type="button" className="formal-run" onClick={run}>Run verifiable comparison →</button>
          <p className="formal-help">Candidate priority follows input order. The exact method searches all supplied candidates; it never invents new pronunciations. Limits: 32 formal events / 16 candidates.</p>
        </section>
        <section className="formal-output" aria-label="Formal search outputs" aria-live="polite">
          <div className="formal-panel-heading"><span>02 / Compare decisions</span><h2>Search evidence</h2></div>
          {!showResults ? <div className="formal-standby">Input changed. Run the comparison to update the evidence.</div> : outcomes.error ? <div className="formal-error" role="alert">{outcomes.error}</div> : outcomes.item && outcomes.top1 && outcomes.top2 && outcomes.exact && outcomes.limited ? <>
            <Answer label="Top-1 commitment" result={outcomes.top1} basis={outcomes.item}/>
            <Answer label="Top-2 commitment" result={outcomes.top2} basis={outcomes.item}/>
            <Answer label="Exact composed search" result={outcomes.exact} basis={outcomes.item}/>
            <Answer label={`Budgeted graph search (${committedBudget} states)`} result={outcomes.limited} basis={outcomes.item}/>
            <div className="formal-takeaway"><strong>Interpretation</strong><p>{outcomes.exact.status === "FEASIBLE" && outcomes.top1.status === "INFEASIBLE" ? "This constructed case proves that Top-1 commitment can discard a feasible path under the declared formal constraints." : outcomes.exact.status === "INFEASIBLE" ? "No supplied formal candidate satisfies all hard constraints; exact search is exhaustive for this finite task." : "The current Top-1 and exact searches agree on feasibility. This alone is not evidence that the first candidate is linguistically valid."} {outcomes.limited.status === "INCOMPLETE" ? "The budgeted search is INCOMPLETE, not INFEASIBLE." : ""}</p></div>
          </> : null}
        </section>
      </div>
      <section className="formal-method">
        <div><span>03 / RESEARCH LIMITS</span><h2>What the demonstration can actually prove</h2></div>
        <p>The Python source reference and this browser engine are checked against shared constructed cases. Exact feasibility concerns only the explicitly supplied finite candidate set, tick durations, boundary rules and locks. No evidence here establishes genuine alternative pronunciations, correct sung syllable boundaries, Hindustani musical authenticity, or scientific novelty.</p>
      </section>
    </div>
  </main>;
}
