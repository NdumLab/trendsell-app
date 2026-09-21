import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowDownRight, ArrowRight, ArrowUpRight, Check, ChevronDown, Download, FileCheck2, History, Info, Save, ShieldCheck, SlidersHorizontal } from 'lucide-react';
import { toast } from 'sonner';
import { useQuery } from '@tanstack/react-query';
import { useWorkspace } from '@/shared/Workspace';
import { api } from '@/lib/api';
import { DecisionBadge, Empty, Loading, Modal, Notice, PageTitle, TruthBadge } from '@/shared/UI';
import { calculate, sensitivity, targets, THRESHOLD_VERSION, type EvidenceGate } from '@/lib/economics';
import { dateTime, download, formatCompact, formatMoney } from '@/lib/utils';
import type { Assessment, Inputs, Product, Quote, Scenario } from '@/types';

type NumericKey = Exclude<keyof Inputs,'compliance'|'channel'|'shipping'>;
const fieldGroups: {title:string;fields:{key:NumericKey;label:string;unit:string;min:number;max:number;step?:number;help?:string}[]}[]=[
 {title:'Order & supplier',fields:[{key:'quantity',label:'Order quantity',unit:'units',min:1,max:1000000,step:1},{key:'unit_cost_usd',label:'Supplier unit quote',unit:'USD',min:0,max:1000000},{key:'fx_ngn',label:'Your exchange rate',unit:'NGN / USD',min:.0001,max:1000000}]},
 {title:'Freight & import assumptions',fields:[{key:'freight_ngn',label:'Total freight quote',unit:'NGN',min:0,max:1e12},{key:'duty_pct',label:'Duty assumption',unit:'%',min:0,max:100,help:'Applied to supplier value + freight. Confirm the actual assessment basis.'},{key:'import_tax_pct',label:'Import tax assumption',unit:'%',min:0,max:100,help:'Applied to supplier value + freight + duty. Classification remains unreviewed.'}]},
 {title:'Sales & operating costs',fields:[{key:'selling_price_ngn',label:'Target selling price',unit:'NGN / unit',min:.0001,max:1e12},{key:'channel_fee_pct',label:'Channel & payment fees',unit:'%',min:0,max:100},{key:'returns_pct',label:'Returns allowance',unit:'%',min:0,max:100},{key:'marketing_ngn',label:'Total marketing budget',unit:'NGN',min:0,max:1e12},{key:'fixed_cost_ngn',label:'Fixed costs & reserves',unit:'NGN',min:0,max:1e12,help:'Include overhead and any additional tax or launch reserve.'}]},
];
const fields=fieldGroups.flatMap(g=>g.fields);
const initial=()=>Object.fromEntries(fields.map(f=>[f.key,''])) as Record<NumericKey,string>;
export default function DecisionRoom(){
 const w=useWorkspace();const [params,setParams]=useSearchParams();const requested=params.get('product');
 // Which product is open. The list is the *menu*; it is never the reading (see below).
 const listed=w.products.find(p=>p.id===requested)||w.products[0];
 const selectedId=requested||listed?.id;
 /** The authoritative reading for the open product.
  *
  *  Review finding R01: the list endpoint returns stored product payloads, which carry no
  *  computed `evidence_quality` and no current evidence records. This screen preferred the
  *  list object and only fetched the detail when the product was *absent* from the loaded
  *  pages — so an ordinary, recently created product, which is always on the first page,
  *  never received the evidence reading the calculator needs. The draft showed confidence
  *  0 and INSUFFICIENT EVIDENCE while the server saved the same inputs as WATCH at 60.
  *
  *  The detail is now read for whichever product is open, page or no page. Recording
  *  evidence or deciding a review invalidates these queries, so the reading refreshes. */
 const detail=useQuery({queryKey:['product',selectedId],queryFn:()=>api<Product>(`/products/${selectedId}`),enabled:!!selectedId&&!w.demo,retry:false});
 const product=w.demo?listed:(detail.data??listed);
 const options=product&&!w.products.some(p=>p.id===product.id)?[product,...w.products]:w.products;
 const [values,setValues]=useState(initial);const [stress,setStress]=useState(10);const [channel,setChannel]=useState('Direct sales');const [shipping,setShipping]=useState<'Air'|'Sea'>('Air');const [compliance,setCompliance]=useState<'unresolved'|'prohibited'>('unresolved');const [busy,setBusy]=useState(false);const [saved,setSaved]=useState<Assessment|null>(null);const [history,setHistory]=useState(false);const [scenario,setScenario]=useState(1);
 const [quoteId,setQuoteId]=useState('');const [quoteFx,setQuoteFx]=useState('');
 const productQuotes=w.quotes.filter(quote=>quote.product_id===selectedId);
 const selectedQuote=productQuotes.find(quote=>quote.id===quoteId);
 const quoteAmount=(quote:Quote)=>quote.unit_price??quote.unit_price_usd??0;
 // One key per logical submission. A failed save keeps it so the retry is idempotent;
 // a successful save or any input change starts a new one (action plan T06).
 const submissionKey=useRef(crypto.randomUUID());
 const restartSubmission=()=>{setSaved(null);submissionKey.current=crypto.randomUUID();};
 // Demo mode prefills the fixture's own inputs and computes its evidence gate with the
 // production method; a real workspace reads the gate from the server (U02, D03).
 const [demoGate,setDemoGate]=useState<EvidenceGate|null>(null);
 useEffect(()=>{let active=true;setValues(initial());restartSubmission();setCompliance('unresolved');setDemoGate(null);setQuoteId('');setQuoteFx('');
  if(w.demo&&product)void import('@/demo').then(({demoInputsByProduct,demoInputs,demoQuality})=>{if(!active)return;
   const data=demoInputsByProduct[product.id]??demoInputs;
   setValues(Object.fromEntries(fields.map(f=>[f.key,String(data[f.key])])) as Record<NumericKey,string>);
   setStress(data.stress_pct);
   const reading=demoQuality(product.id);
   setDemoGate({confidence:reading.confidence,coverage:reading.coverage,compliance_resolved:reading.compliance_resolved,overall:reading.overall,observation_ids:reading.observation_ids});
  });
  return()=>{active=false;};},[w.demo,product?.id]);
 const valid=fields.every(f=>values[f.key]!==''&&Number.isFinite(+values[f.key])&&+values[f.key]>=f.min&&+values[f.key]<=f.max&&(f.key!=='quantity'||Number.isInteger(+values[f.key])));
 const inputs={...Object.fromEntries(fields.map(f=>[f.key,+values[f.key]])),stress_pct:stress,compliance,channel,shipping} as Inputs;
 // A real workspace's gate comes from the server on save; the browser shows the same
 // reading it was given rather than inventing one (D03).
 // Only ever the server's own reading. `compliance_status` carries the reviewed state, so
 // a reviewer's rejection decides the draft exactly as it decides the saved record (R04).
 const liveGate=useMemo<EvidenceGate|undefined>(()=>detail.data?.evidence_quality?{confidence:detail.data.evidence_quality.confidence,coverage:detail.data.evidence_quality.coverage,compliance_resolved:detail.data.evidence_quality.compliance_resolved,overall:detail.data.evidence_quality.overall,observation_ids:detail.data.evidence_quality.observation_ids,compliance_status:detail.data.compliance?.status}:undefined,[detail.data]);
 const gate=w.demo?(demoGate??undefined):liveGate;
 // A missing server reading is unavailable, not evidence of zero. Wait for the
 // authoritative detail and refuse draft calculation/export when that read fails.
 const evidenceReady=w.demo?!!demoGate:detail.isSuccess&&!!liveGate;
 const result=useMemo(()=>valid&&evidenceReady?calculate(inputs,gate):null,[JSON.stringify(inputs),valid,evidenceReady,gate]);
 const active=result?.scenarios[scenario],base=result?.scenarios[1];
 const swings=useMemo(()=>valid?sensitivity(inputs):[],[JSON.stringify(inputs),valid]);
 const goal=useMemo(()=>valid?targets(inputs):null,[JSON.stringify(inputs),valid]);
 const labelOf=(key:NumericKey)=>fields.find(f=>f.key===key)?.label||key;
 /** Export a *saved* assessment. Review finding 2: this used to attach
  *  `product.observations` from the open editor and overwrite the stored threshold
  *  version with a current constant, so downloading product A while viewing product B
  *  produced A's assessment carrying B's evidence. A saved assessment is immutable and
  *  self-contained, so nothing here may read the current screen (T03). */
 const exportSaved=(a:Assessment)=>download(`trendsell-assessment-${a.id}.json`,JSON.stringify({
   schema:'trendsell-assessment-export/1', source:'saved assessment', exported_at:new Date().toISOString(),
   demo:a.truth_state==='Demo',
   product:{id:a.product_id,name:a.product_name,asin:a.product_asin},
   formula_version:a.formula_version, threshold_version:a.threshold_version, evidence_version:a.evidence_version,
   evidence:a.evidence??[], supplier_quote:a.supplier_quote??null, quote_conversion:a.quote_conversion??null, assessment:a},null,2));
 /** Export the draft on screen. It is explicitly not a saved record: it has no id, it is
  *  labelled a draft, and its evidence is whatever the open product currently shows. */
 const exportDraft=(a:Assessment)=>download('trendsell-decision-draft.json',JSON.stringify({
   schema:'trendsell-assessment-export/1', source:'unsaved draft', exported_at:new Date().toISOString(),
   demo:w.demo, saved:false,
   product:product?{id:product.id,name:product.name,asin:product.asin}:null,
   // The draft's provenance is the reading it was calculated from, not a constant: it
   // used to claim `no-observations/1` while showing a score derived from real records
   // (R01). With no reading yet, it says so rather than naming a method it did not use.
   formula_version:a.formula_version, threshold_version:THRESHOLD_VERSION,
   evidence_version:w.demo?'demo-fixture/1':(detail.data?.evidence_quality?.method_version??'no-observations/1'),
   evidence:w.demo?(product?.observations||[]):(detail.data?.observations||[]), assessment:a},null,2));
 if(w.loading)return <Loading/>;
 return <><PageTitle eyebrow="BEFORE YOU COMMIT" title="Make the decision yours." description="Real quotes. Editable assumptions. A clear view of what could go wrong." actions={<button className="button secondary" onClick={()=>setHistory(true)}><History size={16}/>Saved decisions<span className="count-badge">{w.decisionTotal}</span></button>}/>
 {!product?<div className="panel"><Empty title="Start with a product worth investigating." action={<Link to="/xray" className="button primary">Analyze a product<ArrowRight size={16}/></Link>}>Decision Room connects a product’s evidence to your commercial assumptions. Capture a product first, or explore the explicitly labeled demo.</Empty></div>:<>
 <div className="decision-toolbar"><label>INVESTIGATING<select aria-label="Choose product" value={product.id} onChange={e=>setParams({product:e.target.value})}>{options.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select></label><div className="decision-market"><span className="nigeria-flag"/><span>Nigeria</span><span className="muted-text">NGN scenarios</span></div><TruthBadge truth={w.demo?'Demo':'User input'}/></div>
 <Notice kind={w.demo?'amber':'muted'}>{w.demo?'All prefilled figures are illustrative demo assumptions, including FX and import rates. They are not market quotes or regulatory guidance.':'Enter your own quotes, fees, FX, and import assumptions. No rates are supplied automatically. A reviewed classification is required before GO.'}</Notice>
 {!w.demo&&detail.isPending&&<Notice kind="muted">Loading this product’s current evidence and import-readiness record…</Notice>}
 {!w.demo&&detail.isError&&<Notice kind="amber">The current evidence record could not be loaded. Draft calculation, saving and export are paused so missing data cannot be mistaken for zero evidence. <button className="text-button" onClick={()=>void detail.refetch()}>Retry evidence</button></Notice>}
 <div className="decision-room-layout"><section className="panel assumptions"><div className="section-heading"><div><h2>Your commercial inputs</h2><p>All amounts below come from you.</p></div><SlidersHorizontal size={18}/></div><form onSubmit={async e=>{e.preventDefault();if(!result)return;if(!w.requireUser())return;setBusy(true);try{const a=await w.saveDecision(result,product,submissionKey.current,selectedQuote?.id,(selectedQuote?.currency??'USD')!=='USD'&&selectedQuote?Number(quoteFx):undefined);setSaved(a);submissionKey.current=crypto.randomUUID();toast.success('Decision saved with its exact inputs and formula version');}catch(e){toast.error((e as Error).message);}finally{setBusy(false);}}}>
 {!w.demo&&<fieldset><legend>Supplier quote provenance</legend>{productQuotes.length?<div className="stack"><label>Use a saved quote<select aria-label="Use a saved quote" value={quoteId} onChange={event=>{const id=event.target.value;const quote=productQuotes.find(item=>item.id===id);setQuoteId(id);setQuoteFx('');if(quote){const amount=quoteAmount(quote);setValues(current=>({...current,quantity:String(quote.moq),unit_cost_usd:(quote.currency??'USD')==='USD'?String(amount):''}));}restartSubmission();}}><option value="">No quote linked — values below are standalone inputs</option>{productQuotes.map(quote=><option value={quote.id} key={quote.id}>{quote.supplier} · {quoteAmount(quote)} {quote.currency||'USD'} · {quote.incoterm} · {quote.quote_date}</option>)}</select></label>{selectedQuote&&<Notice kind={Math.floor((Date.now()-new Date(`${selectedQuote.quote_date}T00:00:00Z`).getTime())/86400000)>90?'amber':'muted'}><a href={selectedQuote.source_url} target="_blank" rel="noreferrer">{selectedQuote.supplier}</a> quoted {formatMoney(quoteAmount(selectedQuote),selectedQuote.currency||'USD')} at MOQ {selectedQuote.moq.toLocaleString()} · {selectedQuote.incoterm} · {selectedQuote.quote_date}. This remains unverified user input.{Math.floor((Date.now()-new Date(`${selectedQuote.quote_date}T00:00:00Z`).getTime())/86400000)>90?' The quote is more than 90 days old; obtain a fresh quote before relying on it.':''}</Notice>}{selectedQuote&&(selectedQuote.currency??'USD')!=='USD'&&<label>{selectedQuote.currency} to USD conversion used<input aria-label={`${selectedQuote.currency} to USD conversion used`} type="number" min="0.000001" max="1000000" step="any" required value={quoteFx} onChange={event=>{const rate=event.target.value;setQuoteFx(rate);setValues(current=>({...current,unit_cost_usd:rate?String(quoteAmount(selectedQuote)*Number(rate)):''}));restartSubmission();}}/><small>This is your dated conversion assumption. The quote’s original amount and currency remain unchanged in the saved assessment.</small></label>}</div>:<Notice kind="muted">No supplier quote is recorded for this product. <Link to="/suppliers">Record a dated quote</Link>, then return here to use it without re-entering its price, MOQ, terms, or source.</Notice>}</fieldset>}
 {fieldGroups.map(g=><fieldset key={g.title}><legend>{g.title}</legend><div className="input-grid">{g.fields.map(f=><label className={f.help?'wide-input':''} key={f.key}>{f.label}<div className="unit-input"><input aria-label={f.label} type="number" required min={f.min} max={f.max} step={f.step||'any'} value={values[f.key]} placeholder="Enter value" onChange={e=>{setValues({...values,[f.key]:e.target.value});restartSubmission();}}/><span>{f.unit}</span></div>{f.help&&<small>{f.help}</small>}</label>)}</div></fieldset>)}
 <fieldset><legend>Route & readiness</legend><div className="input-grid"><label>Sales channel<select value={channel} onChange={e=>{setChannel(e.target.value);restartSubmission();}}>{['Direct sales','Jumia','Konga','Retail / wholesale','Other'].map(c=><option key={c}>{c}</option>)}</select></label><label>Freight mode<select value={shipping} onChange={e=>{setShipping(e.target.value as 'Air'|'Sea');restartSubmission();}}><option>Air</option><option>Sea</option></select></label><label className="wide-input">Import status<select value={compliance} onChange={e=>{setCompliance(e.target.value as 'unresolved'|'prohibited');restartSubmission();}}><option value="unresolved">Classification / requirements unresolved</option><option value="prohibited">Marked prohibited — block launch</option></select><small>A self-entered assumption cannot clear the compliance gate, and you do not need to restate a reviewer here — an import-readiness decision applies to this assessment on its own.</small></label></div></fieldset>
 <div className="stress-control"><div><label htmlFor="stress">Scenario stress range</label><strong>±{stress}%</strong></div><input id="stress" aria-label="Scenario stress range" type="range" min="0" max="50" value={stress} onChange={e=>{setStress(+e.target.value);restartSubmission();}}/><p>Downside: selling price falls {stress}%, supplier and freight costs rise {stress}%. Upside reverses those changes. These are scenarios, not forecasts.</p></div>
 <button className="button primary full" type="submit" disabled={!valid||busy||!product.confirmed||!evidenceReady}><Save size={16}/>{busy?'Saving…':'Save this decision'}</button>{!product.confirmed&&<p className="form-error">Confirm product identity in X-Ray before saving.</p>}
 </form></section><div className="scenario-output">{result&&base&&active?<>
 <section className="panel decision-verdict"><div className="section-heading"><span className="eyebrow">YOUR CURRENT DECISION</span><TruthBadge truth={w.demo?'Demo':'Calculated'}/></div><DecisionBadge decision={result.decision}/><p>{result.decision==='WATCH'?'The economics are a start. Close the evidence gaps before committing.':result.decision==='NO-GO'?'The current assumptions do not pass the decision gates.':'Your scenario is calculated. Demand and import readiness still need evidence.'}</p><div className="verdict-metrics"><div><small>Base net margin after allocated launch costs</small><strong className={base.margin_pct>=25?'text-lime':'text-amber'}>{base.margin_pct.toFixed(1)}<span>%</span></strong></div><div><small>Evidence coverage</small><strong>{result.confidence}<span>/ 100</span></strong><small className="muted-text">{gate?.coverage?'Demand and destination evidence recorded':'Coverage incomplete'} · {gate?.compliance_resolved?'import readiness approved':'import readiness unresolved'}</small></div></div></section>
 <section className="panel scenarios-panel"><div className="section-heading"><h2>Three scenarios. One clearer picture.</h2></div><div className="scenario-cards">{result.scenarios.map((s,i)=><button key={s.name} onClick={()=>setScenario(i)} className={`scenario-card ${i===scenario?'selected':''}`}><span>{s.name}{i===1&&<small>YOUR INPUTS</small>}</span><strong>{formatMoney(s.contribution)}</strong><small>Net return / unit after allocations</small><b className={s.margin_pct<15?'text-rose':s.margin_pct<25?'text-amber':'text-lime'}>{s.margin_pct.toFixed(1)}% net margin</b></button>)}</div></section>
 <section className="panel cost-waterfall"><div className="section-heading"><div><h2>Where each naira goes</h2><p>{active.name} scenario · per unit · NGN</p></div><TruthBadge truth="Calculated"/></div><Waterfall scenario={active}/><div className="economics-kpis"><div><small>Cash required for the order</small><strong>{formatCompact(active.cash_required)}</strong></div><div><small>Break-even acquisition cost / unit</small><strong>{formatMoney(active.break_even_cac)}</strong></div><div><small>Units to cover marketing & fixed costs</small><strong>{active.break_even_units===null?'Not achievable':active.break_even_units.toLocaleString()}</strong></div></div><p className="formula-caption">Net return and net margin deduct per-unit allocations of both marketing and fixed costs. Cash = landed cost × quantity + marketing + fixed costs. CAC headroom includes the fixed-cost allocation. Break-even units assume the entered selling price and all variable costs.</p></section>
 <section className="panel sensitivity-panel"><div className="section-heading"><div><h2>What moves this decision most</h2><p>Base net-margin swing after allocated launch costs when one input changes by ±10% and everything else holds.</p></div><TruthBadge truth="Calculated"/></div>{swings.length?<div className="sensitivity-rows">{swings.map(s=><div className="sensitivity-row" key={s.key}><span>{labelOf(s.key)}</span><div className="sensitivity-track"><i style={{width:`${Math.min(100,s.swing/swings[0].swing*100)}%`}}/></div><strong>{s.swing.toFixed(1)}<small>pts</small></strong><small>−10% → {s.low.toFixed(1)}% · +10% → {s.high.toFixed(1)}%</small></div>)}</div>:<p className="muted-text">No input changes the margin at these values.</p>}<p className="formula-caption">Each row re-runs the same formula with one input changed. These are scenarios for prioritising your next question, not forecasts.</p></section><section className="panel blockers-panel"><div className="section-heading"><h2>What must become true?</h2><ShieldCheck size={19}/></div>{result.blockers.map((b,i)=><div className="blocker-item" key={b}><span>{i+1}</span><p>{b}</p></div>)}{goal&&base.margin_pct<goal.target_margin&&<div className="target-note"><h4>To reach a {goal.target_margin}% base net margin after allocated launch costs</h4><p>At {inputs.quantity.toLocaleString()} units, either raise the selling price to {goal.price===null?"a price these fees and returns cannot support":formatMoney(goal.price)}{goal.max_landed!==null?<> or bring the landed cost below {formatMoney(goal.max_landed)} per unit{goal.max_unit_cost_usd!==null?<> — about {formatMoney(goal.max_unit_cost_usd,"USD")} per unit from the supplier at your exchange rate</>:null}</>:null}. Your current landed cost is {formatMoney(goal.landed)} per unit.</p></div>}<Link to="/data-health" className="text-button">Review the missing evidence<ArrowUpRight size={15}/></Link></section>
 <div className="formula-note"><FileCheck2 size={17}/><span>Reproducible by design.<small>{result.formula_version} · NGN · exact inputs saved with each assessment</small></span><span className="export-actions"><button className="text-button" onClick={()=>exportDraft(result)}><Download size={15}/>Export this draft</button>{saved&&<button className="text-button" onClick={()=>exportSaved(saved)}><Download size={15}/>Export saved assessment</button>}</span></div>{saved?<Notice>Saved {dateTime(saved.created_at)}. That assessment is immutable for its economics inputs, result, and versions. Provider evidence may later be replaced by an explicit retention tombstone when it expires. The draft above is what is on screen now; changing any input starts a new draft.</Notice>:<Notice kind="muted">Nothing on screen is saved yet. “Export this draft” downloads the unsaved scenario, labelled as a draft.</Notice>}
 </>:<section className="panel"><Empty title="Your inputs unlock the economics.">Fill in each commercial input, including zero for any cost that does not apply. We won’t fill missing costs with guesses.</Empty><div className="input-progress"><span>{fields.filter(f=>values[f.key]!=='').length} of {fields.length} inputs added</span><div><i style={{width:`${fields.filter(f=>values[f.key]!=='').length/fields.length*100}%`}}/></div></div></section>}</div></div></>}
 <Modal open={history} onOpenChange={setHistory} title="Saved decisions" description="Immutable assumptions and calculated results; provider evidence remains subject to retention expiry." drawer>{w.decisions.length?<>{w.decisions.map(d=><div className="saved-decision" key={d.id}><div><h3>{d.product_name}</h3><p>{dateTime(d.created_at)}</p></div><DecisionBadge decision={d.decision}/><dl><div><dt>Formula</dt><dd>{d.formula_version}</dd></div><div><dt>Base margin</dt><dd>{d.scenarios[1].margin_pct}%</dd></div></dl><TruthBadge truth={d.truth_state}/><button className="button secondary full" onClick={()=>exportSaved(d)}><Download size={15}/>Download assessment</button></div>)}{w.moreDecisions&&<button className="button secondary full" onClick={w.loadMoreDecisions}>Load older decisions</button>}</>:<Empty title="No saved decisions yet">Complete a scenario and save it to preserve the exact inputs, evidence references, and calculation version.</Empty>}</Modal></>;
}
function Waterfall({scenario:s}:{scenario:Scenario}){
 const rows:[string,number,string][]=[['Target selling price',s.price,'price'],['Supplier quote',s.supplier,'cost'],['Freight allocation',s.freight,'cost'],['Duty assumption',s.duty,'cost'],['Import tax assumption',s.import_tax,'cost'],['Channel & payment fees',s.fees,'cost'],['Returns allowance',s.returns,'cost'],['Marketing allocation',s.marketing,'cost'],['Fixed-cost allocation',s.overhead,'cost'],['Net return after allocations',s.contribution,'total']];
 return <div className="waterfall-rows">{rows.map(([name,value,type])=><div key={name} className={`waterfall-row ${type}`}><span>{name}</span><div className="waterfall-track"><i style={{width:`${Math.min(Math.abs(value)/s.price*100,100)}%`}}/></div><strong>{formatMoney(value)}</strong></div>)}</div>;
}
