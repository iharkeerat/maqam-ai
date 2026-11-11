/**
 * Browser-compatible demonstrator of the formal tick-alignment problem in
 * research/pronunciation_rhythm/core.py (v12.4.0).
 *
 * Inputs are USER-SUPPLIED FORMAL SYLLABLE TOKENS. This module neither predicts
 * Hindi/Punjabi pronunciations nor authenticates singing or Taal conventions.
 * Algorithms are established dynamic programming / uniform-cost graph search.
 */
export type FormalCandidate = {
  key: string;
  syllables: string[];
  prior: number;
  idealTicks?: number[];
};
export type FormalSpec = {
  events: number[];
  cycleTicks: number;
  minSyllableTicks: number;
  maxSyllableTicks: number;
  maxEventsPerSyllable: number;
  boundaries: number[];
  lockedEvents: { event: number; syllable: string }[];
};
export type FormalCase = {
  key: string;
  candidates: FormalCandidate[];
  rhythm: FormalSpec;
  provenance: "constructed_formal_only";
};
export type FormalSolution = {
  candidateKey: string;
  ends: number[];
  cost: number;
};
export type FormalResult = {
  status: "FEASIBLE" | "INFEASIBLE" | "INCOMPLETE";
  solution: FormalSolution | null;
  expansions: number;
  note?: string;
};

function integer(value: unknown, min: number, max: number): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= min && value <= max;
}

export function validateFormalCase(input: FormalCase): string[] {
  const errors: string[] = [];
  if (!input || input.provenance !== "constructed_formal_only") return ["Only explicitly constructed formal cases are supported."];
  if (!input.key || typeof input.key !== "string") errors.push("Case identifier required.");
  const spec = input.rhythm;
  if (!spec || !Array.isArray(spec.events) || spec.events.length === 0 || spec.events.length > 32 ||
      spec.events.some(v => !integer(v, 1, 64))) return ["Events must be 1–32 positive integer durations (max 64 ticks each)."];
  const total = spec.events.reduce((a, b) => a + b, 0);
  if (!integer(spec.cycleTicks, 1, 2048) || total % spec.cycleTicks !== 0) errors.push("Event duration must span whole formal cycles.");
  if (!integer(spec.minSyllableTicks, 1, 2048) || !integer(spec.maxSyllableTicks, 1, 2048) ||
      spec.maxSyllableTicks < spec.minSyllableTicks) errors.push("Invalid minimum/maximum syllable ticks.");
  if (!integer(spec.maxEventsPerSyllable, 1, 32)) errors.push("Invalid max events per syllable.");
  const prefix = [0];
  for (const v of spec.events) prefix.push(prefix[prefix.length - 1] + v);
  if (!Array.isArray(spec.boundaries) || new Set(spec.boundaries).size !== spec.boundaries.length ||
      spec.boundaries.some(b => !integer(b, 1, total - 1) || !prefix.includes(b))) errors.push("Boundaries must be unique internal event tick boundaries.");
  if (!Array.isArray(spec.lockedEvents) || new Set(spec.lockedEvents.map(l => l.event)).size !== spec.lockedEvents.length ||
      spec.lockedEvents.some(l => !integer(l.event, 0, spec.events.length - 1) || typeof l.syllable !== "string" || !l.syllable.trim()))
    errors.push("Invalid or duplicate locked events.");
  if (!Array.isArray(input.candidates) || input.candidates.length === 0 || input.candidates.length > 16)
    errors.push("Provide 1–16 formal candidates.");
  else {
    if (new Set(input.candidates.map(c => c.key)).size !== input.candidates.length) errors.push("Candidate keys must be unique.");
    for (const c of input.candidates) {
      if (!c.key || typeof c.key !== "string" || !Array.isArray(c.syllables) || c.syllables.length === 0 || c.syllables.length > 32 ||
          c.syllables.some(s => typeof s !== "string" || !s.trim())) errors.push(`Invalid syllables for ${String(c.key)}.`);
      if (!integer(c.prior, 0, 1000000)) errors.push(`Invalid non-negative candidate prior for ${String(c.key)}.`);
      if (c.idealTicks && (c.idealTicks.length !== c.syllables.length || c.idealTicks.some(t => !integer(t, 1, 2048))))
        errors.push(`Invalid target duration sequence for ${String(c.key)}.`);
    }
  }
  return errors;
}

function compareEnds(a: number[], b: number[]): number {
  for (let i = 0; i < Math.min(a.length, b.length); i++) if (a[i] !== b[i]) return a[i] - b[i];
  return a.length - b.length;
}
function compareSolutions(a: FormalSolution, b: FormalSolution): number {
  return a.cost - b.cost || a.candidateKey.localeCompare(b.candidateKey, "en") || compareEnds(a.ends, b.ends);
}

/** Independent witness check; does not call solve routines or spanEligible. */
export function verifyFormalWitness(input: FormalCase, sol: FormalSolution): boolean {
  if (validateFormalCase(input).length) return false;
  const c = input.candidates.find(v => v.key === sol.candidateKey);
  if (!c || !Array.isArray(sol.ends) || sol.ends.length !== c.syllables.length ||
      sol.ends[sol.ends.length - 1] !== input.rhythm.events.length || !integer(sol.cost, 0, 100000000)) return false;
  const s = input.rhythm;
  let start = 0;
  let cost = c.prior;
  for (let i = 0; i < sol.ends.length; i++) {
    const end = sol.ends[i];
    if (!integer(end, start + 1, s.events.length) || end - start > s.maxEventsPerSyllable) return false;
    const ticks = s.events.slice(start, end).reduce((x, y) => x + y, 0);
    if (ticks < s.minSyllableTicks || ticks > s.maxSyllableTicks) return false;
    const beginTick = s.events.slice(0, start).reduce((x, y) => x + y, 0);
    if (s.boundaries.some(b => beginTick < b && b < beginTick + ticks)) return false;
    if (s.lockedEvents.some(l => l.event >= start && l.event < end && l.syllable !== c.syllables[i])) return false;
    cost += end - start - 1;
    if (c.idealTicks?.length) cost += Math.abs(ticks - c.idealTicks[i]);
    start = end;
  }
  return start === s.events.length && cost === sol.cost;
}

function spanEligible(s: FormalSpec, c: FormalCandidate, syllable: number, start: number, end: number, prefix: number[]): number | null {
  const ticks = prefix[end] - prefix[start];
  if (end - start > s.maxEventsPerSyllable || ticks < s.minSyllableTicks || ticks > s.maxSyllableTicks) return null;
  if (s.boundaries.some(b => prefix[start] < b && b < prefix[end])) return null;
  if (s.lockedEvents.some(l => l.event >= start && l.event < end && l.syllable !== c.syllables[syllable])) return null;
  return end - start - 1 + (c.idealTicks?.length ? Math.abs(ticks - c.idealTicks[syllable]) : 0);
}

/** Exact optimal DP. Top-k filters pronunciation candidates BEFORE searching. */
export function solveFormal(input: FormalCase, topK?: number): FormalResult {
  const errors = validateFormalCase(input);
  if (errors.length) throw new Error(errors.join(" "));
  if (topK !== undefined && (!integer(topK, 1, 16))) throw new Error("topK must be a positive integer up to 16.");
  const s = input.rhythm;
  const n = s.events.length;
  const prefix = [0];
  for (const e of s.events) prefix.push(prefix[prefix.length - 1] + e);
  const candidates = [...input.candidates].sort((a, b) => a.prior - b.prior || a.key.localeCompare(b.key, "en"));
  let expansions = 0;
  const solutions: FormalSolution[] = [];
  for (const c of candidates.slice(0, topK ?? candidates.length)) {
    const memo = new Map<string, { cost: number; ends: number[] } | null>();
    const visit = (i: number, start: number): { cost: number; ends: number[] } | null => {
      if (i === c.syllables.length) return start === n ? { cost: 0, ends: [] } : null;
      const cacheKey = `${i}|${start}`;
      if (memo.has(cacheKey)) return memo.get(cacheKey) ?? null;
      let winner: { cost: number; ends: number[] } | null = null;
      for (let end = start + 1; end <= Math.min(n, start + s.maxEventsPerSyllable); end++) {
        expansions++;
        const weight = spanEligible(s, c, i, start, end, prefix);
        if (weight === null) continue;
        const tail = visit(i + 1, end);
        if (!tail) continue;
        const option = { cost: weight + tail.cost, ends: [end, ...tail.ends] };
        if (!winner || option.cost < winner.cost || (option.cost === winner.cost && compareEnds(option.ends, winner.ends) < 0)) winner = option;
      }
      memo.set(cacheKey, winner);
      return winner;
    };
    const found = visit(0, 0);
    if (found) solutions.push({ candidateKey: c.key, cost: c.prior + found.cost, ends: found.ends });
  }
  solutions.sort(compareSolutions);
  const best = solutions[0] ?? null;
  if (best && !verifyFormalWitness(input, best)) throw new Error("Independent witness verification failed.");
  return { status: best ? "FEASIBLE" : "INFEASIBLE", solution: best, expansions };
}

/** Budgeted uniform-cost graph search. INCOMPLETE is never mistaken for INFEASIBLE. */
export function solveFormalBudgeted(input: FormalCase, maxPops: number): FormalResult {
  const errors = validateFormalCase(input);
  if (errors.length) throw new Error(errors.join(" "));
  if (!integer(maxPops, 1, 100000)) throw new Error("Budget must be a positive integer up to 100000.");
  const s = input.rhythm;
  const prefix = [0];
  for (const e of s.events) prefix.push(prefix[prefix.length - 1] + e);
  type Node = { key: string; cost: number; ci: number; i: number; pos: number; ends: number[] };
  const frontier: Node[] = input.candidates.map((c, ci) => ({ key: c.key, cost: c.prior, ci, i: 0, pos: 0, ends: [] }));
  const best = new Map<string, Node>();
  const stateKey = (node: Node) => `${node.ci}|${node.i}|${node.pos}`;
  for (const n of frontier) best.set(stateKey(n), n);
  const cmp = (a: Node, b: Node) => a.cost - b.cost || a.key.localeCompare(b.key, "en") || compareEnds(a.ends, b.ends);
  let popped = 0;
  while (frontier.length > 0) {
    frontier.sort(cmp);
    const node = frontier.shift()!;
    if (best.get(stateKey(node)) !== node) continue;
    if (popped >= maxPops) return { status: "INCOMPLETE", solution: null, expansions: popped, note: "Search budget exhausted; infeasibility not established." };
    popped++;
    const c = input.candidates[node.ci];
    if (node.i === c.syllables.length && node.pos === s.events.length) {
      const sol = { candidateKey: c.key, cost: node.cost, ends: node.ends };
      if (!verifyFormalWitness(input, sol)) throw new Error("Budgeted search witness invalid.");
      return { status: "FEASIBLE", solution: sol, expansions: popped };
    }
    if (node.i === c.syllables.length) continue;
    for (let end = node.pos + 1; end <= Math.min(s.events.length, node.pos + s.maxEventsPerSyllable); end++) {
      const weight = spanEligible(s, c, node.i, node.pos, end, prefix);
      if (weight === null) continue;
      const successor = { key: node.key, ci: node.ci, i: node.i + 1, pos: end, cost: node.cost + weight, ends: [...node.ends, end] };
      const old = best.get(stateKey(successor));
      if (!old || cmp(successor, old) < 0) {
        best.set(stateKey(successor), successor);
        frontier.push(successor);
      }
    }
  }
  return { status: "INFEASIBLE", solution: null, expansions: popped, note: "Finite formal state graph exhausted." };
}

export function eventSyllables(input: FormalCase, sol: FormalSolution): string[] {
  if (!verifyFormalWitness(input, sol)) throw new Error("Invalid formal witness.");
  const candidate = input.candidates.find(c => c.key === sol.candidateKey)!;
  let start = 0;
  const map: string[] = [];
  sol.ends.forEach((end, i) => {
    while (start < end) { map.push(candidate.syllables[i]); start++; }
  });
  return map;
}
