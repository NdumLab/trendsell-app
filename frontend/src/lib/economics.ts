import type { Assessment, Inputs } from '@/types';
import { ceilUnits, div, money, mul, parse } from '@/lib/money';

/** Three formula versions exist on purpose (action plans T04 and D02).
 *
 *  `unit-economics/1.0.0` is the float implementation the pilot shipped. It disagreed
 *  with the server on some accepted inputs, so nothing new is calculated with it — but
 *  assessments already saved under it must still replay to the values they were saved
 *  with, so `calculateV1_0_0` stays.
 *
 *  `unit-economics/1.1.0` is the first exact-decimal version.
 *
 *  `unit-economics/1.2.0` is the current explicit landed-cost model. No rate or omitted
 *  cost is filled by this module; the Decision Room requires every input. */
export const FORMULA_VERSION = 'unit-economics/1.2.0';
export const THRESHOLD_VERSION = 'decision-gates/1.2.0';
export const COST_MODEL_VERSION = 'landed-cost/2.0.0';

export interface EvidenceGate { confidence: number; coverage: boolean; compliance_resolved: boolean; overall: number | null; observation_ids: string[]; compliance_status?: string }
export const NO_EVIDENCE: EvidenceGate = { confidence: 0, coverage: false, compliance_resolved: false, overall: null, observation_ids: [], compliance_status: 'none' };

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

/** Expanded D02 landed-cost lines, mirrored exactly by backend/app/economics.py. */
function scenariosV1_2_0(i: Inputs): ScenarioRow[] {
  const one=parse(1), hundred=parse(100), quantity=parse(i.quantity);
  const unitCost=parse(i.unit_cost_usd), fx=parse(i.fx_ngn);
  const total=(key:'freight_ngn'|'packaging_ngn'|'insurance_ngn'|'clearance_ngn'|'local_delivery_ngn'|'marketing_ngn'|'fixed_cost_ngn'|'reserve_ngn')=>parse(i[key]);
  const dutyRate=div(parse(i.duty_pct),hundred), taxRate=div(parse(i.import_tax_pct),hundred);
  const fxBufferRate=div(parse(i.fx_buffer_pct),hundred), sellingPrice=parse(i.selling_price_ngn);
  const channelRate=div(parse(i.channel_fee_pct),hundred), paymentRate=div(parse(i.payment_fee_pct),hundred);
  const returnsRate=div(parse(i.returns_pct),hundred), depositRate=div(parse(i.supplier_deposit_pct),hundred);
  const marketingTotal=total('marketing_ngn'), fixedTotal=total('fixed_cost_ngn'), reserveTotal=total('reserve_ngn');
  const launchTotals=marketingTotal+fixedTotal+reserveTotal, stress=div(parse(i.stress_pct),hundred);
  const factors:[string,bigint,bigint][]=[['Downside',one-stress,one+stress],['Base',one,one],['Upside',one+stress,one-stress]];
  return factors.map(([name,priceFactor,costFactor])=>{
    const supplier=mul(mul(unitCost,fx),costFactor), fxBuffer=mul(supplier,fxBufferRate);
    const packaging=mul(div(total('packaging_ngn'),quantity),costFactor);
    const freight=mul(div(total('freight_ngn'),quantity),costFactor);
    const insurance=mul(div(total('insurance_ngn'),quantity),costFactor);
    const clearance=mul(div(total('clearance_ngn'),quantity),costFactor);
    const localDelivery=mul(div(total('local_delivery_ngn'),quantity),costFactor);
    const customsBase=supplier+fxBuffer+freight+insurance;
    const duty=mul(customsBase,dutyRate), importTax=mul(customsBase+duty,taxRate);
    const landed=supplier+fxBuffer+packaging+freight+insurance+duty+importTax+clearance+localDelivery;
    const price=mul(sellingPrice,priceFactor), fees=mul(price,channelRate), paymentFees=mul(price,paymentRate);
    const returns=mul(price,returnsRate), marketing=div(marketingTotal,quantity);
    const overhead=div(fixedTotal,quantity), reserve=div(reserveTotal,quantity);
    const contribution=price-landed-fees-paymentFees-returns-marketing-overhead-reserve;
    const beforeFixed=price-landed-fees-paymentFees-returns;
    return {name,supplier:money(supplier),fx_buffer:money(fxBuffer),packaging:money(packaging),
      freight:money(freight),insurance:money(insurance),duty:money(duty),import_tax:money(importTax),
      clearance:money(clearance),local_delivery:money(localDelivery),landed_cost:money(landed),
      price:money(price),fees:money(fees),payment_fees:money(paymentFees),returns:money(returns),
      marketing:money(marketing),overhead:money(overhead),reserve:money(reserve),contribution:money(contribution),
      margin_pct:money(mul(div(contribution,price),hundred)),cash_required:money(mul(landed,quantity)+launchTotals),
      supplier_deposit_cash:money(mul(mul(supplier,quantity),depositRate)),cash_tied_up_days:i.cash_tied_up_days,
      break_even_cac:money(beforeFixed-overhead-reserve>0n?beforeFixed-overhead-reserve:0n),
      break_even_units:beforeFixed>0n?ceilUnits(div(launchTotals,beforeFixed)):null};
  });
}

const SCENARIO_FORMULAS: Record<string, (i: Inputs) => ScenarioRow[]> = {
  'unit-economics/1.0.0': scenariosV1_0_0,
  'unit-economics/1.1.0': scenariosV1_1_0,
  'unit-economics/1.2.0': scenariosV1_2_0,
};

/** What a reviewer's rejection says, in the assessment as well as on the screen. */
export const REJECTED_BLOCKER = 'A reviewer rejected this product for import. Do not proceed.';
export const PROHIBITED_BLOCKER = 'The product is marked prohibited. Do not proceed.';

/** The advisory blockers. Identical in both threshold versions. */
function blockersV1_1_0(scenarios: ScenarioRow[], evidence: EvidenceGate): string[] {
  const base = scenarios[1], downside = scenarios[0], blockers: string[] = [];
  if (!evidence.coverage) blockers.push('Collect independent demand signals and destination-market evidence.');
  if (!evidence.compliance_resolved) blockers.push('Obtain a reviewed product classification and current import requirements.');
  if (evidence.confidence<70) blockers.push('Raise evidence confidence to at least 70 before committing inventory.');
  if (base.margin_pct<25) blockers.push('Raise base contribution margin to at least 25%.');
  if (downside.margin_pct<10) blockers.push('Keep downside contribution margin at or above 10%.');
  return blockers;
}

/** The evidence/economics ladder, once nothing has forced NO-GO. */
function decide(scenarios: ScenarioRow[], evidence: EvidenceGate, blockers: string[]): Assessment['decision'] {
  const base = scenarios[1];
  if (evidence.confidence<40 || !evidence.coverage) return 'INSUFFICIENT EVIDENCE';
  if (base.margin_pct<15 || (evidence.overall!==null && evidence.overall<55)) return 'NO-GO';
  if (!blockers.length && (evidence.overall||0)>=75) return 'GO';
  return 'WATCH';
}

type GateRule = (scenarios: ScenarioRow[], i: Inputs, evidence: EvidenceGate) => { decision: Assessment['decision']; blockers: string[] };

/** The gates the pilot shipped: only the user's own dropdown can force NO-GO. Frozen, so
 *  an assessment saved under it replays to the values it was saved with. */
const gatesV1_0_0: GateRule = (scenarios, i, evidence) => {
  const blockers = blockersV1_1_0(scenarios, evidence);
  if (i.compliance==='prohibited') return { decision:'NO-GO', blockers:[PROHIBITED_BLOCKER, ...blockers] };
  return { decision: decide(scenarios, evidence, blockers), blockers };
};

/** The current gates: a reviewer's rejection is authoritative (review finding R04). A
 *  missing `compliance_status` means no reviewer has rejected this, which reproduces
 *  1.0.0 exactly. */
const gatesV1_1_0: GateRule = (scenarios, i, evidence) => {
  const blockers = blockersV1_1_0(scenarios, evidence);
  if (evidence.compliance_status==='rejected') return { decision:'NO-GO', blockers:[REJECTED_BLOCKER, ...blockers] };
  if (i.compliance==='prohibited') return { decision:'NO-GO', blockers:[PROHIBITED_BLOCKER, ...blockers] };
  return { decision: decide(scenarios, evidence, blockers), blockers };
};

const gatesV1_2_0: GateRule = (scenarios, i, evidence) => {
  const blockers = blockersV1_1_0(scenarios, evidence).map(blocker => blocker
    .replace('base contribution margin', 'base net margin after allocated launch costs')
    .replace('downside contribution margin', 'downside net margin after allocated launch costs'));
  if (evidence.compliance_status==='rejected') return { decision:'NO-GO', blockers:[REJECTED_BLOCKER, ...blockers] };
  if (i.compliance==='prohibited') return { decision:'NO-GO', blockers:[PROHIBITED_BLOCKER, ...blockers] };
  return { decision: decide(scenarios, evidence, blockers), blockers };
};

const GATE_RULES: Record<string, GateRule> = {
  'decision-gates/1.0.0': gatesV1_0_0,
  'decision-gates/1.1.0': gatesV1_1_0,
  'decision-gates/1.2.0': gatesV1_2_0,
};

/** The decision gates for `thresholdVersion`. */
export function gates(scenarios: ScenarioRow[], i: Inputs, evidence: EvidenceGate, thresholdVersion: string = THRESHOLD_VERSION): { decision: Assessment['decision']; blockers: string[] } {
  const rule = GATE_RULES[thresholdVersion];
  if (!rule) throw new Error(`unknown threshold version: ${thresholdVersion}`);
  return rule(scenarios, i, evidence);
}

/** Scenarios and gates for `i`.
 *  `formulaVersion` exists so a stored assessment replays under the version it was saved
 *  with. Callers producing a *new* assessment must leave it at the default. */
export function calculate(i: Inputs, evidence: EvidenceGate = NO_EVIDENCE, formulaVersion: string = FORMULA_VERSION, thresholdVersion: string = THRESHOLD_VERSION): Assessment {
  const build = SCENARIO_FORMULAS[formulaVersion];
  if (!build) throw new Error(`unknown formula version: ${formulaVersion}`);
  const scenarios = build(i);
  const { decision, blockers } = gates(scenarios, i, { ...NO_EVIDENCE, ...evidence }, thresholdVersion);
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
  if (base.margin_pct < 15) failures.push('Base net margin after allocated launch costs is below the 15% floor.');
  else if (base.margin_pct < 25) failures.push('Base net margin after allocated launch costs is below the 25% target.');
  if (downside.margin_pct < 10) failures.push('Downside net margin after allocated launch costs is below 10%.');
  return { base_margin_pct: base.margin_pct, downside_margin_pct: downside.margin_pct, contribution: base.contribution,
    break_even_units: base.break_even_units, viable: !failures.length, failures, threshold_version: THRESHOLD_VERSION };
}

export type NumericKey = Exclude<keyof Inputs,'compliance'|'channel'|'shipping'>;
const SENSITIVITY_KEYS: NumericKey[] = ['unit_cost_usd','fx_ngn','fx_buffer_pct','packaging_ngn','freight_ngn','insurance_ngn','duty_pct','import_tax_pct','clearance_ngn','local_delivery_ngn','selling_price_ngn','channel_fee_pct','payment_fee_pct','returns_pct','marketing_ngn','fixed_cost_ngn','reserve_ngn','quantity'];
export interface Swing { key: NumericKey; low: number; high: number; swing: number }
/** Ranks inputs by how far a ±variation% change moves net margin after allocations. Scenarios, not forecasts. */
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
  const variable=(i.channel_fee_pct+i.payment_fee_pct+i.returns_pct)/100, perUnitFixed=(i.marketing_ngn+i.fixed_cost_ngn+i.reserve_ngn)/i.quantity;
  const importFactor=(1+i.duty_pct/100)*(1+i.import_tax_pct/100);
  const supplierFactor=1+i.fx_buffer_pct/100;
  const importBase=i.unit_cost_usd*i.fx_ngn*supplierFactor+(i.freight_ngn+i.insurance_ngn)/i.quantity;
  const outsideImportBase=(i.packaging_ngn+i.clearance_ngn+i.local_delivery_ngn)/i.quantity;
  const landed=importBase*importFactor+outsideImportBase;
  const headroom=1-variable-target/100;
  const maxLanded=i.selling_price_ngn*headroom-perUnitFixed;
  const maxUnitCost=((maxLanded-outsideImportBase)/importFactor-(i.freight_ngn+i.insurance_ngn)/i.quantity)/(i.fx_ngn*supplierFactor);
  return {target_margin:target, landed, price:headroom>0?(landed+perUnitFixed)/headroom:null, max_landed:maxLanded>0?maxLanded:null, max_unit_cost_usd:maxLanded>0&&maxUnitCost>0?maxUnitCost:null};
}
