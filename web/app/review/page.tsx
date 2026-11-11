"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ChangeEvent, type CSSProperties } from "react";
import casesData from "../data/review_cases.json";

type ReviewCase = {
  itemId: string;
  language: string;
  poem: string;
  systemCandidates: string[];
  referenceSeed: string[];
  systemTaalCandidates: string[];
  referenceTaalSeed: string[];
  warning: string;
};

type Decision = {
  itemId: string;
  reviewerId: string;
  decision: "accept" | "alternative" | "reject";
  acceptedRaags: string[];
  acceptedTaals: string[];
  phraseRating: number;
  note: string;
  reviewedAt: string;
};

const cases = casesData as ReviewCase[];
const STORAGE_KEY = "maqam-v10-expert-review";

function initialDecisions(): Decision[] {
  if (typeof window === "undefined") return [];
  try { return JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "[]") as Decision[]; } catch { return []; }
}

function csvEscape(value: unknown): string {
  const text = Array.isArray(value) ? value.join(";") : String(value ?? "");
  return `"${text.replaceAll('"', '""')}"`;
}

export default function ReviewPage() {
  const [reviewerId, setReviewerId] = useState("reviewer-anonymous");
  const [index, setIndex] = useState(0);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const current = cases[index];
  const existing = decisions.find((decision) => decision.itemId === current.itemId);
  const [decision, setDecision] = useState<Decision["decision"]>(existing?.decision ?? "accept");
  const [acceptedRaags, setAcceptedRaags] = useState<string[]>(existing?.acceptedRaags ?? []);
  const [acceptedTaals, setAcceptedTaals] = useState<string[]>(existing?.acceptedTaals ?? []);
  const [phraseRating, setPhraseRating] = useState(existing?.phraseRating ?? 3);
  const [note, setNote] = useState(existing?.note ?? "");
  const completed = useMemo(() => new Set(decisions.map((item) => item.itemId)).size, [decisions]);

  useEffect(() => {
    // localStorage is browser-only; restore it after hydration without changing
    // the server/client first render.
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      const stored = initialDecisions();
      setDecisions(stored);
      const found = stored.find((item) => item.itemId === cases[0]?.itemId);
      if (found) {
        setDecision(found.decision);
        setAcceptedRaags(found.acceptedRaags);
        setAcceptedTaals(found.acceptedTaals);
        setPhraseRating(found.phraseRating);
        setNote(found.note);
      }
    });
    return () => { cancelled = true; };
  }, []);

  const toggle = (value: string, selected: string[], setter: (items: string[]) => void) => setter(selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value]);

  const move = (next: number) => {
    const bounded = Math.max(0, Math.min(cases.length - 1, next));
    const found = decisions.find((item) => item.itemId === cases[bounded].itemId);
    setIndex(bounded); setDecision(found?.decision ?? "accept"); setAcceptedRaags(found?.acceptedRaags ?? []); setAcceptedTaals(found?.acceptedTaals ?? []); setPhraseRating(found?.phraseRating ?? 3); setNote(found?.note ?? "");
  };

  const save = () => {
    const record: Decision = { itemId: current.itemId, reviewerId: reviewerId.trim() || "reviewer-anonymous", decision, acceptedRaags, acceptedTaals, phraseRating, note: note.trim(), reviewedAt: new Date().toISOString() };
    const updated = [...decisions.filter((item) => item.itemId !== current.itemId), record];
    setDecisions(updated); window.localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    if (index < cases.length - 1) move(index + 1);
  };

  const exportCsv = () => {
    const headers = ["item_id", "reviewer_id", "decision", "accepted_raags", "accepted_taals", "phrase_rating", "note", "reviewed_at"];
    const lines = [headers.join(","), ...decisions.map((item) => [item.itemId, item.reviewerId, item.decision, item.acceptedRaags, item.acceptedTaals, item.phraseRating, item.note, item.reviewedAt].map(csvEscape).join(","))];
    const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "maqam-expert-review.csv"; anchor.click(); URL.revokeObjectURL(url);
  };

  return (
    <main className="review-page">
      <header className="research-nav"><Link href="/" className="research-brand"><b>MAQAM</b> AI <span>Expert review console</span></Link><nav><Link href="/">Workbench</Link><Link href="/research">Research ledger</Link></nav></header>
      <section className="review-heading"><div><p className="section-overline">Human evaluation / local-first</p><h1>Musical judgement<br /><em>cannot be simulated.</em></h1></div><div className="review-progress"><strong>{completed} / {cases.length}</strong><span>cases reviewed locally</span><i style={{ "--meter": `${(completed / cases.length) * 100}%` } as CSSProperties} /></div></section>
      <section className="review-shell">
        <aside className="review-context"><label>Reviewer identifier<input value={reviewerId} onChange={(event: ChangeEvent<HTMLInputElement>) => setReviewerId(event.target.value)} /></label><small>Use an anonymous code when collecting research data.</small><p>{current.warning}</p><dl><div><dt>Item</dt><dd>{current.itemId}</dd></div><div><dt>Language</dt><dd>{current.language}</dd></div><div><dt>Position</dt><dd>{index + 1} / {cases.length}</dd></div></dl></aside>
        <article className="review-case">
          <blockquote>{current.poem}</blockquote>
          <div className="review-candidates"><section><h2>System Raag candidates</h2>{current.systemCandidates.map((candidate, rank) => <label key={candidate} className={acceptedRaags.includes(candidate) ? "is-checked" : ""}><input type="checkbox" checked={acceptedRaags.includes(candidate)} onChange={() => toggle(candidate, acceptedRaags, setAcceptedRaags)} /><b>{rank + 1}</b><span>{candidate}</span></label>)}</section><section><h2>System Taal candidates</h2>{current.systemTaalCandidates.map((candidate, rank) => <label key={candidate} className={acceptedTaals.includes(candidate) ? "is-checked" : ""}><input type="checkbox" checked={acceptedTaals.includes(candidate)} onChange={() => toggle(candidate, acceptedTaals, setAcceptedTaals)} /><b>{rank + 1}</b><span>{candidate}</span></label>)}</section></div>
          <div className="review-decision"><h2>Reviewer judgement</h2><div className="decision-options">{(["accept", "alternative", "reject"] as const).map((value) => <button key={value} className={decision === value ? "is-active" : ""} onClick={() => setDecision(value)}>{value}</button>)}</div><label>Generated phrase acceptance: {phraseRating}/5<input type="range" min="1" max="5" value={phraseRating} onChange={(event: ChangeEvent<HTMLInputElement>) => setPhraseRating(Number(event.target.value))} /></label><label>Correction or reason<textarea value={note} onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setNote(event.target.value)} placeholder="Optional musical reasoning, alternative Raag/Taal, phrase issue or source note…" /></label></div>
          <div className="review-actions"><button onClick={() => move(index - 1)} disabled={index === 0}>← Previous</button><button className="review-save" onClick={save}>Save judgement &amp; continue</button><button onClick={() => move(index + 1)} disabled={index === cases.length - 1}>Skip →</button></div>
        </article>
      </section>
      <section className="review-export"><div><strong>Local data only</strong><p>Responses remain in this browser until exported. The repository includes an import and evaluation workflow for the resulting CSV.</p></div><button onClick={exportCsv} disabled={!decisions.length}>Export {decisions.length} reviews as CSV</button></section>
      <footer className="research-footer"><span>MAQAM AI expert-review workflow</span><strong>Designed &amp; built by Harkeerat Singh</strong><small>Research infrastructure · 2026</small></footer>
    </main>
  );
}
