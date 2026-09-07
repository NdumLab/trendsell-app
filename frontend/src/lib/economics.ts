import type { Assessment, Inputs } from '@/types';
export const FORMULA_VERSION = 'unit-economics/1.0.0';
const money = (value: number) => Math.sign(value) * Math.round((Math.abs(value) + Number.EPSILON) * 100) / 100;
export interface EvidenceGate { confidence: number; coverage: boolean; compliance_resolved: boolean; overall: number | null; observation_ids: string[] }
export function calculate(i: Inputs, evidence: EvidenceGate = { confidence: 0, coverage: false, compliance_resolved: false, overall: null, observation_ids: [] }): Assessment {
  const factors: [string, number, number][] = [['Downside', 1-i.stress_pct/100, 1+i.stress_pct/100], ['Base', 1, 1], ['Upside', 1+i.stress_pct/100, 1-i.stress_pct/100]];
  const scenarios = factors.map(([name, priceFactor, costFactor]) => {
    const supplier = i.unit_cost_usd*i.fx_ngn*costFactor, freight = i.freight_ngn/i.quantity*costFactor;
    const duty = (supplier+freight)*i.duty_pct/100, importTax = (supplier+freight+duty)*i.import_tax_pct/100;
    const landed = supplier+freight+duty+importTax, price = i.selling_price_ngn*priceFactor;
    const fees = price*i.channel_fee_pct/100, returns = price*i.returns_pct/100, marketing = i.marketing_ngn/i.quantity, overhead = i.fixed_cost_ngn/i.quantity;
    const contribution = price-landed-fees-returns-marketing-overhead, beforeFixed = price-landed-fees-returns;
    return { name, supplier: money(supplier), freight: money(freight), duty: money(duty), import_tax: money(importTax), landed_cost: money(landed), price: money(price), fees: money(fees), returns: money(returns), marketing: money(marketing), overhead: money(overhead), contribution: money(contribution), margin_pct: money(contribution/price*100), cash_required: money(landed*i.quantity+i.marketing_ngn+i.fixed_cost_ngn), break_even_cac: money(Math.max(0,beforeFixed-overhead)), break_even_units: beforeFixed>0 ? Math.ceil((i.marketing_ngn+i.fixed_cost_ngn)/beforeFixed) : null };
  });
  const base=scenarios[1], downside=scenarios[0], blockers: string[]=[];
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
  return {formula_version:FORMULA_VERSION,truth_state:'Calculated',currency:'NGN',market:'NG',decision,confidence:evidence.confidence,observation_ids:evidence.observation_ids,blockers,scenarios,inputs:i,input_truth_state:'User input'};
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
