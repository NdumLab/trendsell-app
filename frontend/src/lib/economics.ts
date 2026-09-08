import type { Assessment, Inputs } from '@/types';
import { ceilUnits, div, money, mul, parse } from '@/lib/money';

/** Two formula versions exist on purpose (action plan T04).
 *
 *  `unit-economics/1.0.0` is the float implementation the pilot shipped. It disagreed
 *  with the server on some accepted inputs, so nothing new is calculated with it — but
 *  assessments already saved under it must still replay to the values they were saved
 *  with, so `calculateV1_0_0` stays.
 *
 *  `unit-economics/1.1.0` is the current version: identical formulas, evaluated with the
 *  shared scaled-integer arithmetic in `money.ts` so the browser and the API agree exactly. */
export const FORMULA_VERSION = 'unit-economics/1.1.0';
export const THRESHOLD_VERSION = 'decision-gates/1.0.0';

export interface EvidenceGate { confidence: number; coverage: boolean; compliance_resolved: boolean; overall: number | null; observation_ids: string[] }
export const NO_EVIDENCE: EvidenceGate = { confidence: 0, coverage: false, compliance_resolved: false, overall: null, observation_ids: [] };

type ScenarioRow = Assessment['scenarios'][number];

/** Legacy (1.0.0) rounding. Kept only so stored assessments replay unchanged. */
const legacyMoney = (value: number) => Math.sign(value) * Math.round((Math.abs(value) + Number.EPSILON) * 100) / 100;

function scenariosV1_0_0(i: Inputs): ScenarioRow[] {
  const factors: [string, number, number][] = [['Downside', 1-i.stress_pct/100, 1+i.stress_pct/100], ['Base', 1, 1], ['Upside', 1+i.stress_pct/100, 1-i.stress_pct/100]];
  return factors.map(([name, priceFactor, costFactor]) => {
    const supplier = i.unit_cost_usd*i.fx_ngn*costFactor, freight = i.freight_ngn/i.quantity*costFactor;
    const duty = (supplier+freight)*i.duty_pct/100, importTax = (supplier+freight+duty)*i.import_tax_pct/100;
    const landed = supplier+freight+duty+importTax, price = i.selling_price_ngn*priceFactor;
    const fees = price*i.channel_fee_pct/100, returns = price*i.returns_pct/100, marketing = i.marketing_ngn/i.quantity, overhead = i.fixed_cost_ngn/i.quantity;
    const contribution = price-landed-fees-returns-marketing-overhead, beforeFixed = price-landed-fees-returns;
    return { name, supplier: legacyMoney(supplier), freight: legacyMoney(freight), duty: legacyMoney(duty), import_tax: legacyMoney(importTax), landed_cost: legacyMoney(landed), price: legacyMoney(price), fees: legacyMoney(fees), returns: legacyMoney(returns), marketing: legacyMoney(marketing), overhead: legacyMoney(overhead), contribution: legacyMoney(contribution), margin_pct: legacyMoney(contribution/price*100), cash_required: legacyMoney(landed*i.quantity+i.marketing_ngn+i.fixed_cost_ngn), break_even_cac: legacyMoney(Math.max(0,beforeFixed-overhead)), break_even_units: beforeFixed>0 ? Math.ceil((i.marketing_ngn+i.fixed_cost_ngn)/beforeFixed) : null };
  });
}

/** The same formulas on scaled integers, so the server can match exactly. */
function scenariosV1_1_0(i: Inputs): ScenarioRow[] {
  const one = parse(1), hundred = parse(100);
  const quantity = parse(i.quantity);
  const unitCost = parse(i.unit_cost_usd), fx = parse(i.fx_ngn);
  const freightTotal = parse(i.freight_ngn);
  const dutyRate = div(parse(i.duty_pct), hundred), taxRate = div(parse(i.import_tax_pct), hundred);
  const sellingPrice = parse(i.selling_price_ngn);
  const feeRate = div(parse(i.channel_fee_pct), hundred), returnsRate = div(parse(i.returns_pct), hundred);
  const marketingTotal = parse(i.marketing_ngn), fixedTotal = parse(i.fixed_cost_ngn);
  const stress = div(parse(i.stress_pct), hundred);
  const factors: [string, bigint, bigint][] = [['Downside', one-stress, one+stress], ['Base', one, one], ['Upside', one+stress, one-stress]];
  return factors.map(([name, priceFactor, costFactor]) => {
    const supplier = mul(mul(unitCost, fx), costFactor);
    const freight = mul(div(freightTotal, quantity), costFactor);
    const duty = mul(supplier+freight, dutyRate);
    const importTax = mul(supplier+freight+duty, taxRate);
    const landed = supplier+freight+duty+importTax;
    const price = mul(sellingPrice, priceFactor);
    const fees = mul(price, feeRate), returns = mul(price, returnsRate);
    const marketing = div(marketingTotal, quantity), overhead = div(fixedTotal, quantity);
    const contribution = price-landed-fees-returns-marketing-overhead;
    const beforeFixed = price-landed-fees-returns;
    return { name, supplier: money(supplier), freight: money(freight), duty: money(duty), import_tax: money(importTax), landed_cost: money(landed), price: money(price), fees: money(fees), returns: money(returns), marketing: money(marketing), overhead: money(overhead), contribution: money(contribution), margin_pct: money(mul(div(contribution, price), hundred)), cash_required: money(mul(landed, quantity)+marketingTotal+fixedTotal), break_even_cac: money(beforeFixed-overhead > 0n ? beforeFixed-overhead : 0n), break_even_units: beforeFixed > 0n ? ceilUnits(div(marketingTotal+fixedTotal, beforeFixed)) : null };
  });
}

const SCENARIO_FORMULAS: Record<string, (i: Inputs) => ScenarioRow[]> = {
  'unit-economics/1.0.0': scenariosV1_0_0,
  'unit-economics/1.1.0': scenariosV1_1_0,
};

/** The decision gates. Unchanged by T04 and versioned separately as THRESHOLD_VERSION. */
export function gates(scenarios: ScenarioRow[], i: Inputs, evidence: EvidenceGate): { decision: Assessment['decision']; blockers: string[] } {
  const base = scenarios[1], downside = scenarios[0], blockers: string[] = [];
  if (!evidence.coverage) blockers.push('Collect independent demand signals and destination-market evidence.');
  if (!evidence.compliance_resolved) blockers.push('Obtain a reviewed product classification and current import requirements.');
  if (evidence.confidence<70) blockers.push('Raise evidence confidence to at least 70 before committing inventory.');
  if (base.margin_pct<25) blockers.push('Raise base contribution margin to at least 25%.');
  if (downside.margin_pct<10) blockers.push('Keep downside contribution margin at or above 10%.');
  let decision: Assessment['decision'];
  if(i.compliance==='prohibited') { decision='NO-GO'; blockers.unshift('The product is marked prohibited. Do not proceed.'); }
  else if(evidence.confidence<40 || !evidence.coverage) decision='INSUFFICIENT EVIDENCE';
  else if(base.margin_pct<15 || (evidence.overall!==null && evidence.overall<55)) decision='NO-GO';
  else if(!blockers.length && (evidence.overall||0)>=75) decision='GO';
  else decision='WATCH';
  return { decision, blockers };
}

/** Scenarios and gates for `i`.
 *  `formulaVersion` exists so a stored assessment replays under the version it was saved
 *  with. Callers producing a *new* assessment must leave it at the default. */
export function calculate(i: Inputs, evidence: EvidenceGate = NO_EVIDENCE, formulaVersion: string = FORMULA_VERSION): Assessment {
  const build = SCENARIO_FORMULAS[formulaVersion];
  if (!build) throw new Error(`unknown formula version: ${formulaVersion}`);
  const scenarios = build(i);
  const { decision, blockers } = gates(scenarios, i, evidence);
  return {formula_version:formulaVersion,truth_state:'Calculated',currency:'NGN',market:'NG',decision,confidence:evidence.confidence,observation_ids:evidence.observation_ids,blockers,scenarios,inputs:i,input_truth_state:'User input'};
}

export interface EconomicsSummary { base_margin_pct: number; downside_margin_pct: number; contribution: number; break_even_units: number | null; viable: boolean; failures: string[]; threshold_version: string }
/** Whether the scenario pays for itself, judged without reference to evidence.
 *  Kept out of `calculate()` on purpose: that output is pinned by `formula_version` and a
 *  replayed historical assessment must reproduce byte for byte. This is a separate reading
 *  of the same scenarios so a screen can say "the economics fail under these assumptions"
 *  *and* "demand is unverified" instead of collapsing both into one verdict (T07).
 *  Mirrors economics_summary() in backend/app/economics.py. */
export function economicsSummary(scenarios: ScenarioRow[]): EconomicsSummary {
  const base = scenarios[1], downside = scenarios[0], failures: string[] = [];
  if (base.contribution <= 0) failures.push('The unit does not cover its own costs under these assumptions.');
  if (base.margin_pct < 15) failures.push('Base contribution margin is below the 15% floor.');
  else if (base.margin_pct < 25) failures.push('Base contribution margin is below the 25% target.');
  if (downside.margin_pct < 10) failures.push('Downside contribution margin is below 10%.');
  return { base_margin_pct: base.margin_pct, downside_margin_pct: downside.margin_pct, contribution: base.contribution,
    break_even_units: base.break_even_units, viable: !failures.length, failures, threshold_version: THRESHOLD_VERSION };
}

export type NumericKey = Exclude<keyof Inputs,'compliance'|'channel'|'shipping'>;
const SENSITIVITY_KEYS: NumericKey[] = ['unit_cost_usd','fx_ngn','freight_ngn','duty_pct','import_tax_pct','selling_price_ngn','channel_fee_pct','returns_pct','marketing_ngn','fixed_cost_ngn','quantity'];
export interface Swing { key: NumericKey; low: number; high: number; swing: number }
/** Ranks inputs by how far a ±variation% change moves the base contribution margin. Scenarios, not forecasts. */
export function sensitivity(i: Inputs, variation = 10): Swing[] {
  const shift=(key:NumericKey,factor:number)=>{const value=i[key]*factor;return {...i,[key]:key==='quantity'?Math.max(1,Math.round(value)):value};};
  return SENSITIVITY_KEYS.map(key=>{
    const low=calculate(shift(key,1-variation/100)).scenarios[1].margin_pct, high=calculate(shift(key,1+variation/100)).scenarios[1].margin_pct;
    return {key,low,high,swing:Math.abs(high-low)};
  }).filter(s=>s.swing>0.05).sort((a,b)=>b.swing-a.swing).slice(0,3);
}
export interface Targets { target_margin: number; landed: number; price: number | null; max_landed: number | null; max_unit_cost_usd: number | null }
/** The price and landed cost that would satisfy a target base margin under the current inputs. */
export function targets(i: Inputs, target = 25): Targets {
  const variable=(i.channel_fee_pct+i.returns_pct)/100, perUnitFixed=(i.marketing_ngn+i.fixed_cost_ngn)/i.quantity;
  const importFactor=(1+i.duty_pct/100)*(1+i.import_tax_pct/100);
  const landed=(i.unit_cost_usd*i.fx_ngn+i.freight_ngn/i.quantity)*importFactor;
  const headroom=1-variable-target/100;
  const maxLanded=i.selling_price_ngn*headroom-perUnitFixed;
  const maxUnitCost=(maxLanded/importFactor-i.freight_ngn/i.quantity)/i.fx_ngn;
  return {target_margin:target, landed, price:headroom>0?(landed+perUnitFixed)/headroom:null, max_landed:maxLanded>0?maxLanded:null, max_unit_cost_usd:maxLanded>0&&maxUnitCost>0?maxUnitCost:null};
}
