import Link from "next/link";
import type { CSSProperties } from "react";
import metricsData from "../data/research_metrics.json";

type MetricResult = {
  model: string;
  items: number;
  top1Agreement: number;
  top3Agreement: number;
  primaryTop1Accuracy: number;
  primaryTop3Recall: number;
  meanReciprocalRank: number;
  macroF1PrimaryLabel: number;
  expectedCalibrationError: number;
  multiclassBrier: number;
  perLanguage: Record<string, { items: number; top1Agreement: number; top3Agreement: number; mrr: number }>;
};

type ResearchSummary = {
  release: string;
  benchmark: {
    name: string;
    type: string;
    expertValidated: boolean;
    rows: number;
    train: number;
    dev: number;
    test: number;
    classes: number;
    languages: string[];
    leakageControl: string;
    calibration: { method: string; temperature: number; fitSplit: string };
  };
  claimBoundary: string;
  models: MetricResult[];
  selectedModel: string;
  selectedMetrics: MetricResult;
  taalModel: MetricResult;
  target: { metric: string; range: string; status: string; requires: string };
};

const summary = metricsData as unknown as ResearchSummary;
const selected = summary.models.find((model) => model.model === summary.selectedModel) ?? summary.models[0];
const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

export default function ResearchPage() {
  return (
    <main className="research-page">
      <header className="research-nav">
        <Link href="/" className="research-brand"><b>MAQAM</b> AI <span>Research ledger / v10</span></Link>
        <nav><Link href="/">Workbench</Link><Link href="/review">Expert review</Link><Link href="/alignment-lab">Formal alignment lab</Link><a href="#models">Models</a><a href="#limits">Claim boundary</a></nav>
      </header>

      <section className="research-hero">
        <div>
          <p className="section-overline">Reproducible evaluation / not a marketing score</p>
          <h1>Evidence before<br /><em>accuracy claims.</em></h1>
          <p>MAQAM v10 ships an executable benchmark pipeline, multiple baselines, an ablation ledger, calibration analysis and a human-review interface. The included numbers are internal seed results—not musician consensus.</p>
        </div>
        <aside className="research-warning">
          <strong>INTERNAL SYNTHETIC BENCHMARK</strong>
          <span>{summary.benchmark.rows} generated multilingual items · {summary.benchmark.classes} Raags</span>
          <p>{summary.claimBoundary}</p>
        </aside>
      </section>

      <section className="research-metrics" aria-label="Selected baseline metrics">
        <article><small>Primary Raag Top-1</small><strong>{percent(selected.primaryTop1Accuracy)}</strong><span>exact generated primary label</span></article>
        <article><small>Primary Raag Top-3</small><strong>{percent(selected.primaryTop3Recall)}</strong><span>internal seed retrieval</span></article>
        <article><small>Macro F1</small><strong>{percent(selected.macroF1PrimaryLabel)}</strong><span>28-class balance check</span></article>
        <article><small>Taal Top-1</small><strong>{percent(summary.taalModel.primaryTop1Accuracy)}</strong><span>independent classifier</span></article>
        <article><small>Calibration error</small><strong>{selected.expectedCalibrationError.toFixed(3)}</strong><span>lower is better</span></article>
      </section>

      <section className="research-block" id="models">
        <div className="research-block-heading">
          <p className="section-overline">Baseline comparison</p>
          <h2>Simpler models are allowed to win.</h2>
          <p>The selected seed baseline is chosen by primary-label retrieval, macro F1 and calibration—not by which architecture sounds most impressive.</p>
        </div>
        <div className="research-table-wrap">
          <table className="research-table">
            <thead><tr><th>Model</th><th>Primary Top-1</th><th>Primary Top-3</th><th>Macro F1</th><th>MRR</th><th>ECE</th></tr></thead>
            <tbody>{summary.models.map((model) => (
              <tr key={model.model} className={model.model === summary.selectedModel ? "is-selected" : ""}>
                <td>{model.model}{model.model === summary.selectedModel && <small> selected seed baseline</small>}</td>
                <td>{percent(model.primaryTop1Accuracy)}</td><td>{percent(model.primaryTop3Recall)}</td><td>{percent(model.macroF1PrimaryLabel)}</td><td>{model.meanReciprocalRank.toFixed(3)}</td><td>{model.expectedCalibrationError.toFixed(3)}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </section>

      <section className="research-grid">
        <article className="research-panel">
          <p className="section-overline">Per-language audit / selected baseline</p>
          <h2>No language hidden inside an average.</h2>
          <div className="language-ledger">{Object.entries(selected.perLanguage).map(([language, values]) => (
            <div key={language}><span>{language}<small>{values.items} test items</small></span><b>{percent(values.top1Agreement)}</b><i style={{ "--meter": `${values.top1Agreement * 100}%` } as CSSProperties} /></div>
          ))}</div>
        </article>
        <article className="research-panel">
          <p className="section-overline">Data split and calibration</p>
          <h2>Reproduction details.</h2>
          <dl className="research-definition">
            <div><dt>Train / dev / test</dt><dd>{summary.benchmark.train} / {summary.benchmark.dev} / {summary.benchmark.test}</dd></div>
            <div><dt>Languages</dt><dd>{summary.benchmark.languages.join(" · ")}</dd></div>
            <div><dt>Leakage control</dt><dd>{summary.benchmark.leakageControl}</dd></div>
            <div><dt>Calibration</dt><dd>{summary.benchmark.calibration.method} on {summary.benchmark.calibration.fitSplit}; T={summary.benchmark.calibration.temperature}</dd></div>
          </dl>
        </article>
      </section>

      <section className="research-target" id="limits">
        <div><p className="section-overline">The real research target</p><h2>{summary.target.range} <em>Top-3 expert-set agreement</em></h2></div>
        <div><strong>Status: {summary.target.status}</strong><p>{summary.target.requires}. Internal seed metrics cannot satisfy this requirement.</p><Link href="/review">Open the expert-review interface →</Link></div>
      </section>

      <footer className="research-footer"><span>MAQAM AI Research &amp; Evaluation Edition</span><strong>Designed &amp; built by Harkeerat Singh</strong><small>Portfolio research project · 2026</small></footer>
    </main>
  );
}
