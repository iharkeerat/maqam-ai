"use client";

import { useEffect, useMemo, useRef, useState, type ChangeEvent, type CSSProperties } from "react";
import {
  BUILT_IN_RAAGS,
  HISTORICAL_TAALS,
  PRACTICAL_TAALS,
  RAAG_CATALOGUE,
  SOURCE_REGISTER,
  THAATS,
  findRaag,
  findTaal,
  importMasterKnowledge,
  mergeRaagLibraries,
  mergeTaalLibraries,
} from "../data/knowledge";
import type { RaagRecord, TaalRecord } from "../data/types";
import {
  grammarScore,
  makeSeedNotation,
  validatePhrase,
  type NotationEvent,
  type Ornament,
  type Saptak,
} from "../lib/grammar-engine";
import {
  runMusicologyAnalysis,
  type MusicologyAnalysis,
  type WorkbenchMode,
} from "../lib/musicology-engine";
import { Icon } from "./Icons";

type LanguageMode = "Punjabi" | "Hindi" | "Urdu" | "Roman";
type LockKey = "raag" | "taal" | "notation";

interface LockState {
  raag: boolean;
  taal: boolean;
  notation: boolean;
}

const SWAR_RATIOS: Record<string, number> = {
  S: 1,
  r: 16 / 15,
  R: 9 / 8,
  g: 6 / 5,
  G: 5 / 4,
  m: 4 / 3,
  M: 45 / 32,
  P: 3 / 2,
  d: 8 / 5,
  D: 5 / 3,
  n: 9 / 5,
  N: 15 / 8,
};

const SWAR_LABELS: Array<{ key: string; label: string; type: string }> = [
  { key: "S", label: "Sa", type: "achala" },
  { key: "r", label: "re", type: "komal" },
  { key: "R", label: "Re", type: "shuddha" },
  { key: "g", label: "ga", type: "komal" },
  { key: "G", label: "Ga", type: "shuddha" },
  { key: "m", label: "Ma", type: "shuddha" },
  { key: "M", label: "Ma", type: "tivra" },
  { key: "P", label: "Pa", type: "achala" },
  { key: "d", label: "dha", type: "komal" },
  { key: "D", label: "Dha", type: "shuddha" },
  { key: "n", label: "ni", type: "komal" },
  { key: "N", label: "Ni", type: "shuddha" },
];

const LANGUAGE_OPTIONS: LanguageMode[] = ["Punjabi", "Hindi", "Urdu", "Roman"];
const DEMO_POETRY = "Ranjha Ranjha kardi ni, main aape Ranjha hoi — the name of the beloved dissolves the distance between seeker and truth.";
const DEFAULT_RAAG_ID = "bhairavi";
const DEFAULT_TAAL_ID = "dadra";

function loadStoredRecords<T>(key: string): T[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as T[]) : [];
  } catch {
    return [];
  }
}

function safeRaag(library: RaagRecord[], id: string): RaagRecord {
  return findRaag(library, id) ?? library.find((record) => record.generationReady) ?? BUILT_IN_RAAGS[0];
}

function safeTaal(library: TaalRecord[], id: string): TaalRecord {
  return findTaal(library, id) ?? library.find((record) => record.generationReady) ?? PRACTICAL_TAALS[0];
}

function resizeNotation(notation: NotationEvent[], beats: number): NotationEvent[] {
  return Array.from({ length: beats }, (_, index) => notation[index] ?? {
    swar: "",
    bol: "",
    saptak: "madhya",
    ornament: "none",
    kan: "",
    locked: false,
  });
}

export default function MaqamStudio() {
  const [mode, setMode] = useState<WorkbenchMode>("guided");
  const [locks, setLocks] = useState<LockState>({ raag: false, taal: false, notation: false });
  const [importedRaags, setImportedRaags] = useState<RaagRecord[]>([]);
  const [importedTaals, setImportedTaals] = useState<TaalRecord[]>([]);
  const raagLibrary = useMemo(() => mergeRaagLibraries(BUILT_IN_RAAGS, importedRaags), [importedRaags]);
  const taalLibrary = useMemo(() => mergeTaalLibraries(PRACTICAL_TAALS, importedTaals), [importedTaals]);
  const generationRaags = useMemo(() => raagLibrary.filter((record) => record.generationReady), [raagLibrary]);
  const generationTaals = useMemo(() => taalLibrary.filter((record) => record.generationReady), [taalLibrary]);

  const [activeRaagId, setActiveRaagId] = useState(DEFAULT_RAAG_ID);
  const [activeTaalId, setActiveTaalId] = useState(DEFAULT_TAAL_ID);
  const activeRaag = safeRaag(raagLibrary, activeRaagId);
  const activeTaal = safeTaal(taalLibrary, activeTaalId);

  const [notation, setNotation] = useState<NotationEvent[]>(() => makeSeedNotation(safeRaag(BUILT_IN_RAAGS, DEFAULT_RAAG_ID), safeTaal(PRACTICAL_TAALS, DEFAULT_TAAL_ID)));
  const [selectedBeat, setSelectedBeat] = useState(0);
  const selectedNote = notation[selectedBeat] ?? notation[0] ?? { swar: "", bol: "", saptak: "madhya", ornament: "none", kan: "", locked: false };
  const [poetry, setPoetry] = useState(DEMO_POETRY);
  const [languageMode, setLanguageMode] = useState<LanguageMode>("Roman");
  const [preferredForm, setPreferredForm] = useState("");
  const [desiredLaya, setDesiredLaya] = useState("");
  const [analysis, setAnalysis] = useState<MusicologyAnalysis>(() => runMusicologyAnalysis(DEMO_POETRY, BUILT_IN_RAAGS));
  const [tempo, setTempo] = useState(76);
  const [isAnalysing, setIsAnalysing] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentBeat, setCurrentBeat] = useState<number | null>(null);
  const [saved, setSaved] = useState(false);
  const [notice, setNotice] = useState("v10 research engine ready");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [libraryQuery, setLibraryQuery] = useState("");
  const [libraryFilter, setLibraryFilter] = useState<"all" | "generation" | "catalogue">("all");
  const [historicalQuery, setHistoricalQuery] = useState("");
  const [historicalFilter, setHistoricalFilter] = useState<"all" | "named" | "unresolved">("all");
  const [importWarnings, setImportWarnings] = useState<string[]>([]);
  const [importMetadata, setImportMetadata] = useState<Record<string, unknown>>({});
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const playbackTimersRef = useRef<number[]>([]);

  useEffect(() => {
    let cancelled = false;
    document.documentElement.dataset.theme = "dark";
    queueMicrotask(() => {
      if (cancelled) return;
      setImportedRaags(loadStoredRecords<RaagRecord>("maqam-imported-raags-v10"));
      setImportedTaals(loadStoredRecords<TaalRecord>("maqam-imported-taals-v10"));
    });

    const root = document.querySelector<HTMLElement>(".maqam-site");
    if (!root) return;

    const revealTargets = Array.from(root.querySelectorAll<HTMLElement>(
      "main > section:not(.hero-section), .workbench-shell, .knowledge-grid, .accuracy-board, .stack-ledger"
    ));
    revealTargets.forEach((target) => target.classList.add("reveal"));

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const observer = reducedMotion || !("IntersectionObserver" in window)
      ? null
      : new IntersectionObserver((entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-visible");
              observer?.unobserve(entry.target);
            }
          });
        }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });

    revealTargets.forEach((target) => {
      if (observer) observer.observe(target);
      else target.classList.add("is-visible");
    });

    let frame = 0;
    const updateMotion = (event: PointerEvent) => {
      if (reducedMotion || window.innerWidth < 900) return;
      cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        const x = event.clientX / window.innerWidth - 0.5;
        const y = event.clientY / window.innerHeight - 0.5;
        root.style.setProperty("--parallax-copy-x", `${x * -10}px`);
        root.style.setProperty("--parallax-copy-y", `${y * -8}px`);
        root.style.setProperty("--parallax-stage-x", `${x * 16}px`);
        root.style.setProperty("--parallax-stage-y", `${y * 12}px`);
        root.style.setProperty("--parallax-ui-x", `${x * -7}px`);
        root.style.setProperty("--parallax-ui-y", `${y * -5}px`);
      });
    };

    const updateScroll = () => {
      root.style.setProperty("--scroll-shift", `${-Math.min(window.scrollY * 0.035, 34)}px`);
    };

    window.addEventListener("pointermove", updateMotion, { passive: true });
    window.addEventListener("scroll", updateScroll, { passive: true });
    updateScroll();

    return () => {
      cancelled = true;
      observer?.disconnect();
      cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", updateMotion);
      window.removeEventListener("scroll", updateScroll);
    };
  }, []);

  const diagnostics = useMemo(() => validatePhrase(notation, activeRaag, activeTaal), [notation, activeRaag, activeTaal]);
  const validationScore = useMemo(() => grammarScore(diagnostics), [diagnostics]);
  const affectedBeats = useMemo(() => new Set(diagnostics.filter((item) => item.severity === "fail" || item.severity === "warn").flatMap((item) => item.affectedBeats)), [diagnostics]);
  const divisionStarts = useMemo(() => activeTaal.divisions.map((_, index) => 1 + activeTaal.divisions.slice(0, index).reduce((sum, value) => sum + value, 0)), [activeTaal]);
  const divisionEnds = useMemo(() => activeTaal.divisions.map((_, index) => activeTaal.divisions.slice(0, index + 1).reduce((sum, value) => sum + value, 0)), [activeTaal]);
  const selectedRaagCandidate = analysis.raagCandidates.find((candidate) => candidate.id === activeRaag.id) ?? analysis.raagCandidates[0];
  const filteredCatalogue = useMemo(() => {
    const query = libraryQuery.trim().toLowerCase();
    return RAAG_CATALOGUE.filter((record) => {
      if (libraryFilter === "generation" && !record.generationReady) return false;
      if (libraryFilter === "catalogue" && record.generationReady) return false;
      return !query || record.name.toLowerCase().includes(query) || (record.thaat ?? "").toLowerCase().includes(query);
    });
  }, [libraryFilter, libraryQuery]);
  const historicalNamedCount = useMemo(() => HISTORICAL_TAALS.filter((record) => record.attestationLevel === "secondary-attested-name").length, []);
  const filteredHistoricalTaals = useMemo(() => {
    const query = historicalQuery.trim().toLowerCase();
    return HISTORICAL_TAALS.filter((record) => {
      if (historicalFilter === "named" && !record.canonicalName) return false;
      if (historicalFilter === "unresolved" && record.canonicalName) return false;
      const haystack = `${record.canonicalName ?? ""} ${record.iast ?? ""} ${record.devanagari ?? ""} ${record.id}`.toLowerCase();
      return !query || haystack.includes(query);
    });
  }, [historicalFilter, historicalQuery]);

  const toggleLock = (key: LockKey) => {
    setLocks((current) => {
      const nextLocked = !current[key];
      setNotice(`${key[0].toUpperCase()}${key.slice(1)} ${nextLocked ? "locked" : "unlocked"}`);
      return { ...current, [key]: nextLocked };
    });
  };

  const applyRaag = (id: string, regenerate = true) => {
    const nextRaag = safeRaag(raagLibrary, id);
    setActiveRaagId(nextRaag.id);
    if (regenerate && !locks.notation) {
      setNotation((current) => {
        const seed = makeSeedNotation(nextRaag, activeTaal);
        return seed.map((event, index) => current[index]?.locked ? current[index] : event);
      });
    }
    setSelectedBeat(0);
    setSaved(false);
    setNotice(`${nextRaag.displayName} loaded · Taal unchanged`);
  };

  const applyTaal = (id: string, regenerate = false) => {
    const nextTaal = safeTaal(taalLibrary, id);
    setActiveTaalId(nextTaal.id);
    setNotation((current) => {
      if (regenerate && !locks.notation) {
        const seed = makeSeedNotation(activeRaag, nextTaal);
        return seed.map((event, index) => current[index]?.locked ? current[index] : event);
      }
      return resizeNotation(current, nextTaal.beats);
    });
    setSelectedBeat((current) => Math.min(current, nextTaal.beats - 1));
    setSaved(false);
    setNotice(`${nextTaal.name} applied independently`);
  };

  const applyRecommendation = (result: MusicologyAnalysis) => {
    const proposedRaag = safeRaag(raagLibrary, result.recommendation.raagId);
    const proposedTaal = safeTaal(taalLibrary, result.recommendation.taalId);
    const nextRaag = locks.raag || mode === "scholar" ? activeRaag : proposedRaag;
    const nextTaal = locks.taal || mode === "scholar" ? activeTaal : proposedTaal;

    if (!locks.raag && mode !== "scholar") setActiveRaagId(nextRaag.id);
    if (!locks.taal && mode !== "scholar") setActiveTaalId(nextTaal.id);

    if (mode === "autopilot" && !locks.notation) {
      setNotation((current) => makeSeedNotation(nextRaag, nextTaal).map((event, index) => current[index]?.locked ? current[index] : event));
    } else if (!locks.taal && mode !== "scholar") {
      setNotation((current) => resizeNotation(current, nextTaal.beats));
    }
    setSelectedBeat(0);
  };

  const analysePoetry = async () => {
    if (!poetry.trim()) {
      setNotice("Add a verse before analysis");
      return;
    }
    setIsAnalysing(true);
    setNotice("Separating language, affect, Raag and Taal reasoning…");
    try {
      const response = await fetch("/api/analyse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          poetry,
          importedRaags,
          importedTaals,
          constraints: {
            mode,
            lockedRaagId: locks.raag ? activeRaag.id : null,
            lockedTaalId: locks.taal ? activeTaal.id : null,
            preferredForm,
            desiredLaya,
          },
        }),
      });
      const result = (await response.json()) as MusicologyAnalysis & { error?: string };
      if (!response.ok || result.error) throw new Error(result.error ?? "Analysis service unavailable");
      setAnalysis(result);
      applyRecommendation(result);
      setNotice(mode === "scholar" ? "Analysis complete · manual selections preserved" : `Analysis complete · ${result.recommendation.raagName} / ${result.recommendation.taalName} proposed`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Analysis could not complete");
    } finally {
      setIsAnalysing(false);
    }
  };

  const updateNote = <K extends keyof NotationEvent>(index: number, field: K, value: NotationEvent[K]) => {
    setNotation((current) => current.map((event, eventIndex) => eventIndex === index ? { ...event, [field]: value } : event));
    setSaved(false);
  };

  const setSelectedSwar = (swar: string) => {
    updateNote(selectedBeat, "swar", swar);
    setNotice(swar ? `${swar} placed at matra ${selectedBeat + 1}` : `Matra ${selectedBeat + 1} cleared`);
  };

  const toggleSelectedEventLock = () => {
    updateNote(selectedBeat, "locked", !selectedNote.locked);
    setNotice(`Matra ${selectedBeat + 1} ${selectedNote.locked ? "unlocked" : "locked"}`);
  };

  const syncLyrics = () => {
    const words = poetry.replace(/[.,/#!$%^&*;:{}=\-_`~()“”"']/g, "").split(/\s+/).filter(Boolean);
    setNotation((current) => current.map((event, index) => event.locked ? event : { ...event, bol: words[index] ?? "" }));
    setSaved(false);
    setNotice("Words distributed across unlocked matras");
  };

  const autoCompose = () => {
    if (locks.notation) {
      setNotice("Notation is locked");
      return;
    }
    setNotation((current) => makeSeedNotation(activeRaag, activeTaal).map((event, index) => current[index]?.locked ? current[index] : event));
    setSelectedBeat(0);
    setSaved(false);
    setNotice(`${activeRaag.displayName} seed phrase generated with locked events preserved`);
  };

  const stopPlayback = async () => {
    playbackTimersRef.current.forEach((timer) => window.clearTimeout(timer));
    playbackTimersRef.current = [];
    if (audioContextRef.current) {
      await audioContextRef.current.close();
      audioContextRef.current = null;
    }
    setCurrentBeat(null);
    setIsPlaying(false);
    setNotice("Playback stopped");
  };

  const playComposition = async () => {
    if (isPlaying) {
      await stopPlayback();
      return;
    }
    if (!notation.some((event) => SWAR_RATIOS[event.swar])) {
      setNotice("Enter at least one valid Swar");
      return;
    }
    const context = new AudioContext();
    audioContextRef.current = context;
    const master = context.createGain();
    master.gain.value = 0.17;
    master.connect(context.destination);
    const beatDuration = 60 / tempo;
    const tonic = 261.63;

    notation.forEach((event, index) => {
      playbackTimersRef.current.push(window.setTimeout(() => {
        setCurrentBeat(index);
        setSelectedBeat(index);
      }, index * beatDuration * 1000));
      if (!SWAR_RATIOS[event.swar]) return;
      const start = context.currentTime + 0.08 + index * beatDuration;
      const duration = beatDuration * 0.86;
      const octave = event.saptak === "mandra" ? 0.5 : event.saptak === "taar" ? 2 : 1;
      const frequency = tonic * SWAR_RATIOS[event.swar] * octave;
      const oscillator = context.createOscillator();
      const reed = context.createOscillator();
      const gain = context.createGain();
      oscillator.type = "sawtooth";
      reed.type = "triangle";
      oscillator.frequency.setValueAtTime(frequency, start);
      reed.frequency.setValueAtTime(frequency * 2.002, start);
      const next = notation.slice(index + 1).find((candidate) => SWAR_RATIOS[candidate.swar]);
      if (event.ornament === "meend" && next) {
        const nextOctave = next.saptak === "mandra" ? 0.5 : next.saptak === "taar" ? 2 : 1;
        oscillator.frequency.exponentialRampToValueAtTime(tonic * SWAR_RATIOS[next.swar] * nextOctave, start + duration);
      }
      if (event.ornament === "murki" || event.ornament === "gamak") {
        oscillator.detune.setValueAtTime(0, start);
        oscillator.detune.linearRampToValueAtTime(event.ornament === "gamak" ? 140 : 90, start + duration * 0.25);
        oscillator.detune.linearRampToValueAtTime(event.ornament === "gamak" ? -120 : -70, start + duration * 0.5);
        oscillator.detune.linearRampToValueAtTime(0, start + duration * 0.8);
      }
      if (event.ornament === "khatka") {
        oscillator.detune.setValueAtTime(120, start);
        oscillator.detune.exponentialRampToValueAtTime(1, start + duration * 0.18);
      }
      if (event.ornament === "andolan") {
        const encoded = activeRaag.andolan[event.swar];
        const lfo = context.createOscillator();
        const depth = context.createGain();
        lfo.frequency.value = encoded?.speedHz || 4;
        depth.gain.value = encoded?.widthCents || 18;
        lfo.connect(depth);
        depth.connect(oscillator.detune);
        lfo.start(start);
        lfo.stop(start + duration);
      }
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.48, start + 0.035);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
      oscillator.connect(gain);
      reed.connect(gain);
      gain.connect(master);
      oscillator.start(start);
      reed.start(start);
      oscillator.stop(start + duration + 0.02);
      reed.stop(start + duration + 0.02);
    });

    setIsPlaying(true);
    setNotice("Playing browser synthesis");
    playbackTimersRef.current.push(window.setTimeout(() => {
      setIsPlaying(false);
      setCurrentBeat(null);
      audioContextRef.current?.close().catch(() => undefined);
      audioContextRef.current = null;
      playbackTimersRef.current = [];
      setNotice("Playback complete");
    }, (notation.length * beatDuration + 0.25) * 1000));
  };

  const saveComposition = () => {
    window.localStorage.setItem("maqam-composition-v10", JSON.stringify({ poetry, activeRaagId, activeTaalId, notation, tempo, analysis, languageMode, mode, locks, preferredForm, desiredLaya }));
    setSaved(true);
    setNotice("Composition and reasoning trace saved locally");
  };

  const resetComposition = () => {
    setPoetry("");
    setNotation(makeSeedNotation(activeRaag, activeTaal).map((event) => ({ ...event, swar: "", bol: "" })));
    setSelectedBeat(0);
    setSaved(false);
    setNotice("Blank study opened");
  };

  const exportComposition = () => {
    const payload = JSON.stringify({
      format: "MAQAM-AI composition v10",
      title: "Untitled Kalam",
      poetry,
      raag: activeRaag,
      taal: activeTaal,
      tempo,
      notation,
      analysis,
      languageMode,
      mode,
      locks,
      validation: { score: validationScore, diagnostics },
    }, null, 2);
    const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `maqam-${activeRaag.id}-${activeTaal.id}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    setNotice("Composition, knowledge references and reasoning exported");
  };

  const handleMasterImport = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text()) as unknown;
      const imported = importMasterKnowledge(parsed);
      setImportedRaags(imported.raags);
      setImportedTaals(imported.taals);
      setImportWarnings(imported.warnings);
      setImportMetadata(imported.metadata);
      window.localStorage.setItem("maqam-imported-raags-v10", JSON.stringify(imported.raags));
      window.localStorage.setItem("maqam-imported-taals-v10", JSON.stringify(imported.taals));
      setNotice(`${imported.raags.length} Raags and ${imported.taals.length} Taals imported and normalised`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "The master JSON could not be imported");
    } finally {
      event.target.value = "";
    }
  };

  const clearImportedKnowledge = () => {
    setImportedRaags([]);
    setImportedTaals([]);
    setImportWarnings([]);
    setImportMetadata({});
    window.localStorage.removeItem("maqam-imported-raags-v10");
    window.localStorage.removeItem("maqam-imported-taals-v10");
    if (!BUILT_IN_RAAGS.some((record) => record.id === activeRaagId)) {
      applyRaag(DEFAULT_RAAG_ID);
    }
    setNotice("Imported master library removed; built-in seed restored");
  };

  const candidateRaag = safeRaag(raagLibrary, analysis.recommendation.raagId);
  const candidateTaal = safeTaal(taalLibrary, analysis.recommendation.taalId);

  return (
    <div className="maqam-site" data-theme="dark">
      <header className="site-header">
        <a className="brand-lockup" href="#home" aria-label="MAQAM AI v10 home">
          <span className="brand-word"><b>MAQAM</b> AI</span>
          <span className="brand-descriptor">Explainable knowledge engine<br />for Hindustani musicology</span>
        </a>
        <nav className={mobileOpen ? "site-nav is-open" : "site-nav"} aria-label="Main navigation">
          <a href="#workbench" onClick={() => setMobileOpen(false)}>Workbench</a>
          <a href="#method" onClick={() => setMobileOpen(false)}>Method</a>
          <a href="#library" onClick={() => setMobileOpen(false)}>Knowledge</a>
          <a href="/research" onClick={() => setMobileOpen(false)}>Research</a>
          <a href="/alignment-lab" onClick={() => setMobileOpen(false)}>Alignment Lab</a>
          <a href="/review" onClick={() => setMobileOpen(false)}>Expert review</a>
        </nav>
        <div className="header-actions">
          <a className="header-cta" href="#workbench">Open workbench <Icon name="arrow" size={15} /></a>
          <button className="menu-toggle" onClick={() => setMobileOpen((open) => !open)} aria-expanded={mobileOpen} aria-label="Toggle menu"><Icon name={mobileOpen ? "close" : "menu"} size={21} /></button>
        </div>
      </header>

      <main>
        <section className="hero-section" id="home">
          <aside className="hero-index" aria-hidden="true"><span>POETRY</span><i /><span>RAAG</span><i /><span>TAAL</span><i /><span>NOTATION</span><i /><span>EVIDENCE</span></aside>
          <div className="hero-copy">
            <p className="hero-overline">Language becomes evidence.<br /><em>Evidence becomes a musical proposal.</em></p>
            <h1><span>Where</span><span>poetry</span><span className="serif-line">becomes</span><span className="accent-line">Raag.</span></h1>
            <p className="hero-summary">An explainable computational-musicology workbench for Punjabi, Hindi and Urdu poetry: independent Raag and Taal ranking, editable Bhatkhande events, symbolic grammar diagnostics and an immediate audio study.</p>
            <div className="hero-proofline"><span>{RAAG_CATALOGUE.length} Raags indexed</span><span>{generationRaags.length} deep records active</span><span>{PRACTICAL_TAALS.length} practical Taal records</span><span>{HISTORICAL_TAALS.length} protected historical records</span></div>
            <a className="text-link" href="#workbench">Test the knowledge engine <Icon name="arrow" size={17} /></a>
          </div>
          <div className="heritage-window" aria-hidden="true"><HeritageStage /><div className="heritage-caption"><span>Archive / performance / computation</span><b>Tradition remains editable</b></div></div>
          <div className="hero-workbench" aria-label="Live MAQAM AI reasoning preview">
            <div className="preview-topbar"><span>MAQAM / NEURO-SYMBOLIC TRACE</span><b>{candidateRaag.displayName} · {candidateTaal.name}</b><em>{analysis.semanticEngine.replaceAll("-", " ")} · {Math.round(analysis.semanticConfidence * 100)}% semantic confidence</em></div>
            <div className="preview-layout">
              <section className="preview-poetry"><div className="panel-kicker"><b>1</b><span>Poetry evidence</span></div><div className="mini-tabs"><span>ਹਿੰਦੀ</span><span>اردو</span><span>ਪੰਜਾਬੀ</span></div><blockquote>{poetry}</blockquote><dl><div><dt>Detected</dt><dd>{analysis.features.language} · {analysis.features.scripts.join(" + ")}</dd></div><div><dt>Bhava trace</dt><dd>{analysis.features.primaryRasa} / {analysis.features.secondaryRasa}</dd></div></dl></section>
              <section className="preview-recommendation"><div className="panel-kicker"><b>2</b><span>Independent proposals</span></div><div className="recommendation-heading"><div><small>Raag / Taal</small><strong>{candidateRaag.displayName}</strong><p>{candidateTaal.name} · {candidateTaal.beats} matras</p></div><span>{analysis.recommendation.score}</span></div><p className="why-match">{analysis.raagCandidates[0]?.explanation}</p><div className="recommendation-meta"><span>Fit score, not probability</span><span>{candidateRaag.verification}</span></div></section>
              <section className="preview-notation"><div className="panel-kicker"><b>3</b><span>Bhatkhande event model</span></div><div className="preview-staff">{notation.slice(0, 12).map((event, index) => <div key={index} className={currentBeat === index ? "is-live" : ""}><small>{index + 1}</small><strong>{event.swar || "·"}</strong><i /><span>{event.bol || (event.locked ? "locked" : "edit")}</span></div>)}</div></section>
              <section className="preview-validation"><div className="panel-kicker"><b>4</b><span>Independent validator</span></div>{diagnostics.slice(0, 3).map((item) => <div key={item.id}><i>{item.severity === "pass" ? "✓" : item.severity === "fail" ? "×" : "!"}</i><span><strong>{item.label}</strong><small>{item.value}</small></span></div>)}</section>
              <section className="preview-audio"><button onClick={playComposition} aria-label={isPlaying ? "Stop audio preview" : "Play audio preview"}><Icon name={isPlaying ? "pause" : "play"} size={17} /></button><div><small>5 / Audio study</small><WaveformBars /><span>{isPlaying ? "playing phrase" : `${tempo} BPM · Web Audio`}</span></div></section>
            </div>
          </div>
        </section>

        <section className="workflow-band" aria-label="MAQAM AI workflow">
          {[
            ["01", "Read the verse", "Script, language and evidence", "book"],
            ["02", "Rank Raags", "Affective vectors + constraints", "spark"],
            ["03", "Rank Taals", "Cadence + form, independently", "cycle"],
            ["04", "Edit notation", "Locks preserve musician decisions", "grid"],
            ["05", "Audit & hear", "Grammar diagnostics + audio", "wave"],
          ].map(([number, title, body, icon]) => <article key={number}><span>{number}</span><Icon name={icon as "book" | "spark" | "cycle" | "grid" | "wave"} size={23} /><div><strong>{title}</strong><small>{body}</small></div></article>)}
        </section>

        <section className="heritage-story" id="method">
          <div className="story-copy"><p className="section-overline">Method / neuro-symbolic by design</p><h2>AI interprets.<br /><em>Rules refuse.</em><br />The musician decides.</h2><p>A server-side Gemini structured-output layer can interpret language, imagery, form and Rasa. It never chooses the music directly. Separate deterministic engines rank Raag and Taal, and an independent symbolic validator audits every generated or edited phrase.</p><div className="method-rule"><span>01</span><b>Structured semantics</b><small>Gemini when configured; deterministic fallback otherwise</small></div><div className="method-rule"><span>02</span><b>Knowledge retrieval</b><small>Structured Raag, Taal and source records</small></div><div className="method-rule"><span>03</span><b>Independent audit</b><small>Swar, Pakad, Nyas, contour, ornament and cycle checks</small></div></div>
          <div className="archive-composition"><div className="archive-page"><span>SOURCE LAYER</span><b>10 Thaats</b><p>{THAATS.join(" · ")}</p><i>Thaat indexes the pitch field. It never substitutes for Chalan, Pakad or treatment.</i></div><div className="archive-portrait"><MaqamKnowledgeDiagram /></div><div className="archive-caption"><span>Knowledge architecture</span><strong>28 built-in deep records + one-command 100-Raag master ingestion</strong><small>Catalogue breadth is never presented as equal to generation depth.</small></div></div>
          <div className="audience-board"><p className="section-overline">Three operating modes</p><h3>Automation without deleting authorship.</h3><div>{[
            ["Guided", "AI proposes and updates unlocked Raag/Taal decisions; notation remains yours."],
            ["Scholar", "Analysis runs, but manual Raag, Taal and notation selections are preserved."],
            ["Autopilot", "Experimental full proposal: unlocked selections and notation may regenerate."],
            ["Constraint locks", "Lock Raag, Taal, the full score, or individual matras before rerunning."],
          ].map(([title, body]) => <article key={title}><strong>{title}</strong><p>{body}</p></article>)}</div></div>
        </section>

        <section className="workbench-section" id="workbench">
          <div className="workbench-intro"><p className="section-overline">Core instrument / v10</p><h2>Compose with<br /><em>visible uncertainty.</em></h2><p>Manual settings stay because musical judgement is not an error condition. The system can automate repetitive work, but every recommendation remains inspectable, reversible and lockable.</p></div>
          <div className="workbench-shell">
            <div className="mode-console">
              <div className="mode-console-title"><MaqamGlyph /><span><b>MAQAM KNOWLEDGE ENGINE</b><small>{importedRaags.length ? `${importedRaags.length} imported master records active` : `${generationRaags.length} built-in generation records active`}</small></span></div>
              <div className="mode-switcher" role="group" aria-label="Workbench mode">{(["guided", "scholar", "autopilot"] as WorkbenchMode[]).map((value) => <button key={value} className={mode === value ? "is-active" : ""} onClick={() => setMode(value)}><span>{value === "guided" ? "AI Guided" : value === "scholar" ? "Scholar / Manual" : "Autopilot"}</span><small>{value === "guided" ? "propose" : value === "scholar" ? "preserve" : "regenerate"}</small></button>)}</div>
              <div className="constraint-locks">{(["raag", "taal", "notation"] as LockKey[]).map((key) => <button key={key} className={locks[key] ? "is-locked" : ""} onClick={() => toggleLock(key)}><Icon name={locks[key] ? "lock" : "unlock"} size={13} /><span>{key}</span></button>)}</div>
            </div>

            <div className="workbench-header">
              <div className="workbench-brand"><MaqamGlyph /><span><b>UNTITLED KALAM</b><small>{saved ? "saved locally" : "working study"}</small></span></div>
              <label><span>Raag</span><select value={activeRaag.id} disabled={locks.raag} onChange={(event) => applyRaag(event.target.value)}>{generationRaags.map((record) => <option key={record.id} value={record.id}>{record.displayName} · {record.thaat ?? "unclassified"}</option>)}</select></label>
              <label><span>Taal</span><select value={activeTaal.id} disabled={locks.taal} onChange={(event) => applyTaal(event.target.value)}>{generationTaals.map((record) => <option key={record.id} value={record.id}>{record.name} · {record.beats}</option>)}</select></label>
              <label><span>Tempo</span><input type="number" min={40} max={220} value={tempo} onChange={(event) => setTempo(Number(event.target.value))} /></label>
              <div className="project-actions"><button onClick={resetComposition}><Icon name="plus" size={14} /> New</button><button onClick={saveComposition}><Icon name="save" size={14} /> Save</button><button onClick={exportComposition}><Icon name="download" size={14} /> Export</button></div>
            </div>

            <div className="workbench-body">
              <aside className="poetry-column">
                <div className="workspace-title"><span>01</span><b>Verse &amp; constraints</b><small>{analysis.features.language}</small></div>
                <div className="language-tabs">{LANGUAGE_OPTIONS.map((option) => <button key={option} className={languageMode === option ? "is-active" : ""} onClick={() => setLanguageMode(option)}>{option}</button>)}</div>
                <textarea value={poetry} onChange={(event) => { setPoetry(event.target.value); setSaved(false); }} placeholder="Paste Punjabi, Hindi, Urdu or Roman-script poetry…" />
                <div className="constraint-fields"><label><span>Musical form</span><select value={preferredForm} onChange={(event) => setPreferredForm(event.target.value)}><option value="">No form lock</option><option>Khayal</option><option>Thumri</option><option>Ghazal</option><option>Qawwali</option><option>Bhajan</option><option>Folk</option><option>Instrumental</option></select></label><label><span>Laya</span><select value={desiredLaya} onChange={(event) => setDesiredLaya(event.target.value)}><option value="">No Laya lock</option><option>Vilambit</option><option>Madhya</option><option>Drut</option></select></label></div>
                <div className="poetry-buttons"><button onClick={analysePoetry} disabled={isAnalysing}><span>{isAnalysing ? "Analysing…" : "Analyse & rank"}</span><Icon name="spark" size={15} /></button><button onClick={syncLyrics}><span>Align words</span><Icon name="grid" size={15} /></button></div>
                <div className="feature-evidence"><div className="analysis-heading"><span>Detected evidence</span><small>{analysis.features.wordCount} words</small></div><dl><div><dt>Primary / secondary</dt><dd>{analysis.features.primaryRasa} · {analysis.features.secondaryRasa}</dd></div><div><dt>Cadence</dt><dd>{analysis.features.averageWordsPerLine} words/line · σ {analysis.features.cadenceVariation}</dd></div><div><dt>Scripts</dt><dd>{analysis.features.scripts.join(" + ") || "Undetermined"}</dd></div></dl><div className="evidence-chips">{analysis.features.evidence.length ? analysis.features.evidence.map((item) => <span key={`${item.token}-${item.rasa}`}>{item.token}<b>{item.rasa}</b></span>) : <span>Low explicit evidence<b>uncertain</b></span>}</div></div>
                <div className="profile-ledger"><div className="analysis-heading"><span>{activeRaag.displayName} profile</span><small>{activeRaag.dataCompleteness}% complete</small></div><dl><div><dt>Thaat</dt><dd>{activeRaag.thaat ?? "Unresolved"}</dd></div><div><dt>Vadi / Samvadi</dt><dd>{activeRaag.vadi ?? "—"} / {activeRaag.samvadi ?? "—"}</dd></div><div><dt>Aaroh</dt><dd>{activeRaag.aaroh ?? "Not encoded"}</dd></div><div><dt>Avroh</dt><dd>{activeRaag.avroh ?? "Not encoded"}</dd></div><div><dt>Pakad</dt><dd>{activeRaag.pakad ?? "Not encoded"}</dd></div></dl></div>
              </aside>

              <section className="notation-column">
                <div className="workspace-title"><span>02</span><b>Editable Bhatkhande event field</b><small>{notation.filter((event) => event.locked).length} locked matras</small></div>
                <div className="swar-palette">{SWAR_LABELS.map((item) => <button key={item.key} onClick={() => setSelectedSwar(item.key)} className={`${activeRaag.allowedSwars.includes(item.key) ? "" : "is-outside"} ${selectedNote.swar === item.key ? "is-selected" : ""}`}><strong>{item.label}</strong><span>{item.key}</span><small>{item.type}</small></button>)}<button className="rest-key" onClick={() => setSelectedSwar("")}><strong>·</strong><span>rest</span></button></div>
                <div className="notation-viewport"><div className="notation-grid" style={{ "--beats": activeTaal.beats } as CSSProperties}>
                  <div className="notation-row count-row"><span className="row-label">Matra</span>{notation.map((_, index) => <span key={index} className={divisionStarts.includes(index + 1) ? "is-vibhag" : ""}>{index + 1}</span>)}</div>
                  <div className="notation-row swar-row"><span className="row-label">Swar</span>{notation.map((event, index) => <button key={index} onClick={() => setSelectedBeat(index)} className={`${selectedBeat === index ? "is-selected" : ""} ${currentBeat === index ? "is-current" : ""} ${divisionStarts.includes(index + 1) ? "is-vibhag" : ""} ${affectedBeats.has(index) ? "has-error" : ""}`}><strong>{event.swar || "·"}</strong>{event.swar && <i />}<small>{event.locked ? "LOCK" : event.saptak}</small></button>)}</div>
                  <div className="notation-row bol-row"><span className="row-label">Bol</span>{notation.map((event, index) => <label key={index} className={`${selectedBeat === index ? "is-selected" : ""} ${currentBeat === index ? "is-current" : ""} ${divisionStarts.includes(index + 1) ? "is-vibhag" : ""}`}><input value={event.bol} disabled={event.locked && mode === "autopilot"} onFocus={() => setSelectedBeat(index)} onChange={(changeEvent) => updateNote(index, "bol", changeEvent.target.value)} placeholder="—" /></label>)}</div>
                  <div className="notation-row ornament-row"><span className="row-label">Alankar</span>{notation.map((event, index) => <button key={index} onClick={() => setSelectedBeat(index)} className={`${selectedBeat === index ? "is-selected" : ""} ${divisionStarts.includes(index + 1) ? "is-vibhag" : ""}`}>{event.ornament === "none" ? "—" : event.ornament}</button>)}</div>
                  <div className="notation-row taal-row"><span className="row-label">Taal</span>{notation.map((_, index) => <span key={index} className={divisionStarts.includes(index + 1) ? "is-vibhag" : ""}>{divisionStarts.includes(index + 1) ? activeTaal.marks[divisionStarts.indexOf(index + 1)] : divisionEnds.includes(index + 1) ? "|" : ""}</span>)}</div>
                </div></div>
                <div className="editor-toolbar"><button onClick={autoCompose}><Icon name="reset" size={15} /> Generate unlocked phrase</button><span>{activeTaal.theka ?? "No verified default Theka stored"}</span><small>{locks.notation ? "Global score locked" : "Select a matra to edit or lock it."}</small></div>
              </section>

              <aside className="analysis-column" id="grammar">
                <div className="workspace-title"><span>03</span><b>Reasoning &amp; validation</b><small>{analysis.semanticEngine.replaceAll("-", " ")} · {validationScore}/100 grammar</small></div>
                <div className="selected-event-card"><span>{selectedNote.swar || "·"}</span><div><small>Selected matra {selectedBeat + 1}</small><strong>{selectedNote.locked ? "Locked event" : selectedNote.swar ? SWAR_LABELS.find((item) => item.key === selectedNote.swar)?.label : "Rest"}</strong></div><button onClick={toggleSelectedEventLock} aria-label="Toggle selected event lock"><Icon name={selectedNote.locked ? "lock" : "unlock"} size={14} /></button></div>
                <div className="event-editor"><label><span>Saptak</span><select value={selectedNote.saptak} onChange={(event) => updateNote(selectedBeat, "saptak", event.target.value as Saptak)}><option value="mandra">Mandra</option><option value="madhya">Madhya</option><option value="taar">Taar</option></select></label><label><span>Ornament</span><select value={selectedNote.ornament} onChange={(event) => updateNote(selectedBeat, "ornament", event.target.value as Ornament)}><option value="none">Plain</option><option value="meend">Meend</option><option value="murki">Murki</option><option value="khatka">Khatka</option><option value="andolan">Andolan</option><option value="gamak">Gamak</option></select></label><label><span>Kan</span><input value={selectedNote.kan} maxLength={1} onChange={(event) => updateNote(selectedBeat, "kan", event.target.value)} placeholder="—" /></label></div>

                <div className="ranking-panel"><div className="analysis-heading"><span>Raag candidates</span><small>fit ≠ probability</small></div>{analysis.raagCandidates.slice(0, 5).map((candidate, index) => <button key={candidate.id} onClick={() => applyRaag(candidate.id, false)} className={candidate.id === activeRaag.id ? "is-active" : ""}><b>{index + 1}</b><span><strong>{candidate.name}</strong><i style={{ "--score": `${candidate.fitScore}%` } as CSSProperties} /></span><em>{candidate.fitScore}/100</em></button>)}</div>
                <div className="ranking-panel taal-ranking"><div className="analysis-heading"><span>Taal candidates</span><small>independent ranker</small></div>{analysis.taalCandidates.slice(0, 4).map((candidate, index) => <button key={candidate.id} onClick={() => applyTaal(candidate.id)} className={candidate.id === activeTaal.id ? "is-active" : ""}><b>{index + 1}</b><span><strong>{candidate.name} · {candidate.beats}</strong><i style={{ "--score": `${candidate.fitScore}%` } as CSSProperties} /></span><em>{candidate.fitScore}/100</em></button>)}</div>
                <div className="score-breakdown"><div className="analysis-heading"><span>Why {selectedRaagCandidate?.name}</span><small>decomposed score</small></div>{selectedRaagCandidate?.components.slice(0, 6).map((component) => <div key={component.key}><span><b>{component.label}</b><small>{component.reason}</small></span><em>{component.score}/{component.max}</em></div>)}</div>
                <div className="grammar-panel"><div className="analysis-heading"><span>Grammar diagnostics</span><small>{diagnostics.some((item) => item.severity === "fail") ? "repair required" : "review trace"}</small></div>{diagnostics.map((item) => <div key={item.id} className={item.severity}><i>{item.severity === "pass" ? "✓" : item.severity === "fail" ? "×" : item.severity === "warn" ? "!" : "i"}</i><span><strong>{item.label}</strong><small>{item.detail}</small></span><em>{item.value}</em></div>)}</div>
              </aside>
            </div>

            <div className="audio-transport"><div className="transport-label"><span>Audio study</span><small>{activeRaag.displayName} · {activeTaal.name}</small></div><button onClick={playComposition} className="transport-play"><Icon name={isPlaying ? "pause" : "play"} size={23} /></button><div className="transport-time">{isPlaying ? "Playing" : "Ready"}<small>{tempo} BPM</small></div><div className="transport-wave"><WaveformBars large /><div className="beat-progress" style={{ "--beats": activeTaal.beats } as CSSProperties}>{notation.map((_, index) => <i key={index} className={currentBeat === index ? "is-current" : currentBeat !== null && index < currentBeat ? "is-past" : ""} />)}</div></div><div className="transport-status"><span>{notice}</span><b>{saved ? "Saved locally" : `${mode} mode · ${Object.values(locks).filter(Boolean).length} locks`}</b></div></div>
          </div>
        </section>

        <section className="knowledge-section" id="library">
          <div className="knowledge-heading"><p className="section-overline">Knowledge library / coverage is labelled</p><h2>Broad enough to explore.<br /><em>Strict enough not to bluff.</em></h2><p>The release separates depth from breadth: 28 deep built-in Raags, a 100-name catalogue, a 32-record practical Taal register, and a protected 120-record Saṅgītaratnākara registry. Your existing 100-Raag master JSON can be normalised at runtime or bundled through the included build script.</p></div>
          <div className="knowledge-stats"><article><strong>{RAAG_CATALOGUE.length}</strong><span>Raag names indexed</span><small>Catalogue does not equal generation certification.</small></article><article><strong>{generationRaags.length}</strong><span>Generation-ready now</span><small>{importedRaags.length ? "Includes runtime master import." : "Built-in deep seed only."}</small></article><article><strong>{taalLibrary.length}</strong><span>Practical Taal records</span><small>{generationTaals.length} enabled for automatic cycle generation{importedTaals.length ? ", including imported records" : ""}.</small></article><article><strong>{HISTORICAL_TAALS.length}</strong><span>Historical registry records</span><small>{historicalNamedCount} secondary-attested names · {HISTORICAL_TAALS.length - historicalNamedCount} unresolved source slots.</small></article></div>
          <div className="knowledge-grid">
            <div className="master-import-card"><div className="analysis-heading"><span>Import MAQAM master JSON</span><small>Raag + Taal schema adapter</small></div><h3>Use the full file you already built.</h3><p>The importer recognises the master structure with symbolic, acoustic and affective layers; normalises names and Swar tokens; calculates schema completeness; and stores the transformed records locally.</p><input ref={fileInputRef} type="file" accept="application/json,.json" onChange={handleMasterImport} hidden /><div className="import-actions"><button onClick={() => fileInputRef.current?.click()}><Icon name="upload" size={15} /> Select master JSON</button>{importedRaags.length > 0 && <button onClick={clearImportedKnowledge}><Icon name="close" size={15} /> Remove import</button>}</div><dl><div><dt>Imported</dt><dd>{importedRaags.length || "—"}</dd></div><div><dt>Raags ready</dt><dd>{importedRaags.filter((record) => record.generationReady).length || "—"}</dd></div><div><dt>Taals imported</dt><dd>{importedTaals.length || "—"}</dd></div><div><dt>Metadata</dt><dd>{Object.keys(importMetadata).length ? JSON.stringify(importMetadata).slice(0, 110) : "Waiting for file"}</dd></div></dl>{importWarnings.map((warning) => <p key={warning} className="import-warning">{warning}</p>)}</div>
            <div className="catalogue-browser"><div className="analysis-heading"><span>100-Raag catalogue</span><small>{filteredCatalogue.length} visible</small></div><div className="catalogue-controls"><input value={libraryQuery} onChange={(event) => setLibraryQuery(event.target.value)} placeholder="Search Raag or Thaat" /><select value={libraryFilter} onChange={(event) => setLibraryFilter(event.target.value as "all" | "generation" | "catalogue")}><option value="all">All records</option><option value="generation">Generation-ready</option><option value="catalogue">Catalogue-only</option></select></div><div className="catalogue-list">{filteredCatalogue.map((record) => <div key={record.id}><span>{String(record.ordinal).padStart(3, "0")}</span><strong>{record.name}</strong><small>{record.thaat ?? "classification pending"}</small><em className={record.generationReady ? "ready" : "catalogue"}>{record.generationReady ? "compose" : "archive"}</em></div>)}</div></div>
            <div className="historical-observatory"><div className="analysis-heading"><span>Saṅgītaratnākara observatory</span><small>Tālādhyāya / protected 120-record registry</small></div><h3>Integrated without fabricating history.</h3><p>All 120 registry positions exist in the product and documentation. {historicalNamedCount} names are carried as secondary-attested candidates; the remaining {HISTORICAL_TAALS.length - historicalNamedCount} are explicitly unresolved. No source order, Aṅga sequence, Matra count, Kriyā pattern or modern Theka is invented.</p><div className="catalogue-controls"><input value={historicalQuery} onChange={(event) => setHistoricalQuery(event.target.value)} placeholder="Search historical candidate" /><select value={historicalFilter} onChange={(event) => setHistoricalFilter(event.target.value as "all" | "named" | "unresolved")}><option value="all">All 120 records</option><option value="named">Secondary-attested names</option><option value="unresolved">Unresolved source slots</option></select></div><div className="historical-sample">{filteredHistoricalTaals.slice(0, 16).map((record) => <div key={record.id}><span>{String(record.registrySlot).padStart(3, "0")}</span><strong>{record.canonicalName ?? "Source transcription pending"}</strong><small>{record.iast ? `${record.iast} · ` : ""}{record.attestationLevel.replaceAll("-", " ")}</small></div>)}</div><p className="import-warning">Historical playback remains disabled until primary-edition Aṅgas and Kriyās are transcribed and validated. The included CSV and scripts support that workflow.</p><div className="source-register"><strong>Source register</strong>{SOURCE_REGISTER.map((source) => <span key={source.id}>{source.title}<small>{source.note}</small></span>)}</div></div>
          </div>
        </section>

        <section className="accuracy-section" id="accuracy">
          <div className="accuracy-intro"><p className="section-overline">Accuracy laboratory</p><h2>90–93% is a target<br /><em>that must be earned.</em></h2><p>MAQAM now separates internal rule coverage from future expert-agreement metrics. It does not call a recommendation score “accuracy,” and it does not claim expert consensus without an expert-labelled test set.</p></div>
          <div className="accuracy-board"><article className="accuracy-primary"><span>Current displayed number</span><strong>{analysis.recommendation.score}</strong><h3>Heuristic fit score</h3><p>A reproducible combination of semantic Bhava features, context, time, form, Taal cadence and data completeness. It ranks options; it is not a probability or expert-agreement result.</p></article><article><span>Symbolic grammar</span><strong>{validationScore}</strong><h3>Internal diagnostic score</h3><p>Summarises this phrase’s encoded checks. It cannot certify stylistic authenticity or Gharana validity.</p></article><article><span>Target evaluation</span><strong>90–93%</strong><h3>Top-3 expert agreement</h3><p>The defensible future target: at least one of the top three proposals falls within an expert-accepted set.</p></article><article><span>Required evidence</span><strong>3×</strong><h3>Independent annotators</h3><p>Each verse should permit multiple acceptable Raags and Taals, with disagreement preserved rather than erased.</p></article></div>
          <div className="evaluation-roadmap">{[
            ["01", "Build benchmark", "1,500–3,000 multilingual verses, split by poet and collection."],
            ["02", "Collect expert sets", "Three or more annotators; multiple acceptable answers allowed."],
            ["03", "Calibrate weights", "Fit ranking weights on training folds, not on the final test set."],
            ["04", "Report honestly", "Top-1, Top-3, MRR, NDCG, calibration and grammar precision/recall."],
          ].map(([number, title, body]) => <article key={number}><span>{number}</span><h3>{title}</h3><p>{body}</p></article>)}</div>
          <div className="uncertainty-register"><strong>Current uncertainty register</strong>{analysis.uncertainty.map((item) => <p key={item}>{item}</p>)}</div><div className="accuracy-actions"><a href="/research">Open reproducible research ledger →</a><a href="/review">Open expert-review console →</a></div>
        </section>

        <section className="technology-section" id="stack"><div className="technology-heading"><p className="section-overline">Technologies &amp; frameworks</p><h2>Built across interface, knowledge, rules and sound.</h2><p>The v10 portfolio story is no longer “an LLM chose a Raag.” It is data ingestion, multilingual feature extraction, independent rankers, constraint-aware symbolic editing, validation and synthesis.</p></div><div className="stack-ledger">{[
          ["01", "Next.js 16", "Application shell, server analysis endpoint and portfolio delivery.", "globe"],
          ["02", "React 19", "Constraint locks, live notation state and interactive reasoning views.", "layers"],
          ["03", "TypeScript", "Typed Raag/Taal schemas, import adapters and deterministic engines.", "code"],
          ["04", "Scikit-learn", "Multilingual TF-IDF baselines, logistic ranking, temperature calibration and model artefacts.", "database"],
          ["05", "Rule engine", "Independent phrase diagnostics for Swar, Pakad, Nyas, contour and Sam.", "shield"],
          ["06", "Web Audio API", "Immediate synthesis with Meend, Murki, Khatka, Gamak and Andolan.", "wave"],
          ["07", "FastAPI + NumPy", "Validated WAV synthesis plus local reproducible model-inference endpoints.", "spark"],
          ["08", "Evaluation stack", "Synthetic seed benchmark, ablations, error analysis, model card, dataset card and expert-review export.", "grid"],
        ].map(([number, title, body, icon]) => <article key={number}><span>{number}</span><Icon name={icon as "globe" | "layers" | "code" | "database" | "shield" | "wave" | "spark" | "grid"} size={28} /><h3>{title}</h3><p>{body}</p><i>↗</i></article>)}</div><div className="architecture-line"><span>VERSE</span><i /><span>SEMANTIC JSON</span><i /><span>RAAG RANKER</span><i /><span>TAAL RANKER</span><i /><span>RULE AUDIT</span><i /><span>AUDIO</span></div></section>

        <section className="project-statement"><div><p className="section-overline">Portfolio research project / 2026</p><h2>Not an oracle.<br /><em>An accountable instrument.</em></h2></div><p>MAQAM automates data handling, scoring, notation proposals and diagnostics while preserving musician control. The strongest claim is not perfection; it is that every decision has a visible origin, a reversible state and an explicit uncertainty.</p><a className="project-link" href="#workbench">Return to the instrument <Icon name="arrow" size={17} /></a></section>
      </main>

      <footer className="site-footer" id="about"><div className="footer-brand"><MaqamGlyph /><span><b>MAQAM AI</b><small>Explainable computational musicology</small></span></div><p>Punjabi · Hindi · Urdu poetry → Raag · Taal · Bhatkhande events · grammar trace · sound</p><div className="footer-credit"><span>Designed &amp; built by</span><strong>Harkeerat Singh</strong><small>Research & Evaluation Edition · 2026</small></div></footer>
    </div>
  );
}

function MaqamGlyph() {
  return <svg className="maqam-glyph" viewBox="0 0 48 48" aria-hidden="true"><path d="M6 8h11v11H6zM31 8h11v11H31zM6 29h11v11H6z" /><path d="M31 29h11v11H31z" className="fill"/><path d="M11.5 10v7M8 13.5h7M36.5 10v7M33 13.5h7M8 34.5h7"/><circle cx="11.5" cy="34.5" r="2.5" className="fill"/></svg>;
}

function MaqamKnowledgeDiagram() {
  return <svg className="knowledge-diagram" viewBox="0 0 520 520" role="img" aria-label="MAQAM knowledge architecture diagram"><circle cx="260" cy="260" r="205"/><circle cx="260" cy="260" r="144"/><circle cx="260" cy="260" r="72"/><path d="M260 55v410M55 260h410M115 115l290 290M405 115 115 405"/><g><text x="240" y="250">POETRY</text><text x="225" y="276">EVIDENCE</text><text x="228" y="105">RAAG</text><text x="400" y="267">TAAL</text><text x="217" y="438">GRAMMAR</text><text x="65" y="267">AUDIO</text></g><g className="nodes">{[[260,55],[405,115],[465,260],[405,405],[260,465],[115,405],[55,260],[115,115]].map(([cx,cy],index)=><circle key={index} cx={cx} cy={cy} r="8"/>)}</g></svg>;
}

function HeritageStage() {
  return <svg className="heritage-stage-svg" viewBox="0 0 500 760" role="img" aria-label="Abstract architectural arch and tanpura illustration"><defs><linearGradient id="stageGlow" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#9b5c38" stopOpacity=".76"/><stop offset=".55" stopColor="#463223" stopOpacity=".4"/><stop offset="1" stopColor="#0d0e0d" stopOpacity="0"/></linearGradient><filter id="soft"><feGaussianBlur stdDeviation="18"/></filter></defs><rect width="500" height="760" fill="#121311"/><circle cx="265" cy="310" r="190" fill="url(#stageGlow)" filter="url(#soft)"/><path d="M54 720V260C54 98 160 32 250 32s196 66 196 228v460" fill="none" stroke="#5f4431" strokeWidth="44" opacity=".76"/><path d="M88 720V275C88 135 173 72 250 72s162 63 162 203v445" fill="none" stroke="#a4764e" strokeWidth="2" opacity=".72"/><path d="M94 594h312M84 638h332M72 684h356" stroke="#7c593d" strokeWidth="2" opacity=".45"/><g opacity=".22" fill="#d5c0a6" fontFamily="serif" fontSize="19"><text x="124" y="166">स्वर लय शब्द अर्थ</text><text x="94" y="202">राग संगीत विचार</text><text x="282" y="246">S R G M P D N</text><text x="108" y="292">ਨਾਦ · सुर · صدا</text></g><g transform="translate(219 250)"><path d="M31 56C7 90 5 160 25 206c18 42 13 119-3 174-11 38-10 84 8 108 18 24 54 24 72 0 18-24 19-70 8-108-16-55-21-132-3-174 20-46 18-116-6-150Z" fill="#21140e" stroke="#b4855d" strokeWidth="3"/><ellipse cx="66" cy="480" rx="58" ry="70" fill="#24150f" stroke="#b4855d" strokeWidth="3"/><ellipse cx="66" cy="480" rx="30" ry="40" fill="none" stroke="#725038" strokeWidth="2"/><path d="M45 58 57-173h18L87 58" fill="#2d1c13" stroke="#b4855d" strokeWidth="3"/><path d="M62-166v650M68-166v650" stroke="#d7b289" strokeWidth="1" opacity=".72"/><path d="M51-176c14-18 39-18 48-3-6 13-14 23-28 24-14-1-21-8-20-21Z" fill="#2d1c13" stroke="#b4855d" strokeWidth="3"/></g><path d="M98 360c58-38 102-54 128-46M274 554c44-22 91-27 132-13" fill="none" stroke="#dd5d36" strokeWidth="2" opacity=".64"/><text x="32" y="734" fill="#9c785b" fontFamily="monospace" fontSize="9" letterSpacing="3">SOURCE / PERFORMANCE / COMPUTATION</text></svg>;
}

function WaveformBars({ large = false }: { large?: boolean }) {
  const bars = [6,12,9,18,24,11,30,17,8,23,34,15,27,10,20,38,18,8,29,22,12,33,16,9,25,36,13,21,31,11,17,26,8,19,28,14,35,20,10,24,16,30,12,22,7,18,26,11];
  return <span className={large ? "waveform-bars is-large" : "waveform-bars"} aria-hidden="true">{bars.map((height, index) => <i key={index} style={{ height: `${height}px`, "--bar-index": index } as CSSProperties} />)}</span>;
}
