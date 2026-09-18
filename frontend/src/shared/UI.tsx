import React, { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight, Check, ChevronRight, ExternalLink, FileSearch, Info, LoaderCircle, Search, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { dateTime, relativeTime } from '@/lib/utils';
import { useWorkspace } from './Workspace';
import type { Decision, LatestAssessment, Observation, Product, Truth } from '@/types';

export function TruthBadge({truth}:{truth:Truth}) {return <span className={`truth truth-${truth.toLowerCase().replaceAll(' ','-')}`}><span/>{truth}</span>;}
export function DecisionBadge({decision}:{decision:Decision}) {return <span className={`decision decision-${decision.toLowerCase().replaceAll(' ','-')}`}><span/>{decision==='INSUFFICIENT EVIDENCE'?'Needs evidence':decision}</span>;}
/** The user's latest saved commercial assessment, shown beside — never instead of — the
 *  product's evidence status (action plan T07). Its date and scenario are part of the fact:
 *  a NO-GO saved in July under a different channel is not today's verdict. */
export function AssessmentSummary({assessment,compact=false}:{assessment?:LatestAssessment|null;compact?:boolean}){
 if(!assessment) return <span className="assessment-summary none"><span className="muted-text">No saved assessment</span></span>;
 const {economics}=assessment;
 return <span className={`assessment-summary ${compact?'compact':''}`}>
  <DecisionBadge decision={assessment.decision}/>
  <small title={dateTime(assessment.saved_at)}>Saved {relativeTime(assessment.saved_at)} · {assessment.channel} · {assessment.shipping}</small>
  {!compact&&<small className={economics.viable?'text-lime':'text-amber'}>{economics.viable?'Economics pass at these assumptions':`Economics fail: ${economics.failures[0]}`}</small>}
  {assessment.compliance==='prohibited'&&<small className="text-rose">Marked prohibited by the person who saved it</small>}
 </span>;
}
export function PageTitle({eyebrow,title,description,actions}:{eyebrow?:string;title:string;description:string;actions?:React.ReactNode}) {return <div className="page-title"><div>{eyebrow&&<div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1><p>{description}</p></div>{actions&&<div className="page-actions">{actions}</div>}</div>;}
export function Empty({title,children,action}:{title:string;children:React.ReactNode;action?:React.ReactNode}) {return <div className="empty-state"><div className="empty-icon"><FileSearch size={27}/></div><h3>{title}</h3><p>{children}</p>{action}</div>;}
export function Loading(){return <div className="loading" role="status"><LoaderCircle className="spin" size={22}/> Loading your workspace…</div>;}
export function Notice({children,kind='muted'}:{children:React.ReactNode;kind?:string}){return <div className={`notice ${kind}`}><Info size={17}/><div>{children}</div></div>;}
export function Modal({open,onOpenChange,title,description,children,drawer=false}:{open:boolean;onOpenChange:(open:boolean)=>void;title:string;description:string;children:React.ReactNode;drawer?:boolean}){
 return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal><Dialog.Overlay className="modal-overlay"/><Dialog.Content className={drawer?'modal drawer':'modal'}><div className="modal-head"><div><Dialog.Title>{title}</Dialog.Title><Dialog.Description>{description}</Dialog.Description></div><Dialog.Close className="icon-button" aria-label="Close dialog"><X size={20}/></Dialog.Close></div><div className="modal-body">{children}</div></Dialog.Content></Dialog.Portal></Dialog.Root>;
}
const METRIC_NOTES: Record<string,{what:string;limits:string}> = {
 'Search interest':{what:'A normalized index describes relative search interest inside one window and market. 100 is the highest point in that window, not a number of searches.',limits:'It does not represent units sold, revenue, or a proven cause of demand. Comparing two windows requires the same market, window length, and normalization.'},
 'Review velocity':{what:'The count of new reviews created in a period. It is a public trace of buyer activity on one listing.',limits:'Reviews are a small and delayed sample of purchases. Promotions, review gating, and removals all move this value without demand moving.'},
 'Marketplace rank':{what:'A listing position published by the marketplace for one category and market.',limits:'Rank is relative to other listings, so it can improve while demand falls. It is not a sales figure.'},
 'Ad persistence':{what:'How long a public ad has remained active, measured from its first and last seen dates.',limits:'A long-running ad persisted; it was not proven profitable. Spend, reach, and return are not published.'},
};
const DEFAULT_NOTE={what:'This value was recorded against one metric, market, and moment in time.',limits:'Read it with its source, window, and unit. A single observation is not a trend, and a trend is not a cause.'};
const PRODUCED: Record<string,string> = {
 Observed:'Returned directly by the named source and stored with a hashed, normalized source snapshot.',
 Calculated:'Derived from observations by a versioned formula. Its inputs are listed in the lineage.',
 Estimated:'Inferred from partial evidence. Treat the range, not the midpoint, as the answer.',
 'User input':'Entered by someone in this workspace. TrendSell stores it separately from observed facts.',
 Unavailable:'No trustworthy observation exists for this source, window, and market.',
 Demo:'A synthetic fixture. It was never collected from a source.',
};
export function EvidenceDrawer({observation,onClose}:{observation:Observation|null;onClose:()=>void}){
 const note=observation?METRIC_NOTES[observation.metric]||DEFAULT_NOTE:DEFAULT_NOTE;
 const series=observation?.series;
 const collected=series?.filter(p=>p.value!==null).length??0;
 return <Modal open={!!observation} onOpenChange={open=>!open&&onClose()} title="Follow the evidence" description="The source, context, and lineage behind this value." drawer>{observation&&<>
  <div className="evidence-number"><TruthBadge truth={observation.truth_state}/><h2>{observation.value===null?'Unavailable':observation.value.toLocaleString()} <small>{observation.value===null?'':observation.unit}</small></h2><p>{observation.metric}</p></div>
  {observation.truth_state==='Demo'&&<Notice kind="amber">This is a synthetic example, not a collected source observation. It cannot support a real investment decision.</Notice>}
  {observation.value===null&&<Notice kind="amber">No observation was collected for this point. A gap is not a zero, and it is not falling demand.</Notice>}
  <div className="evidence-quality"><div><small>Confidence</small><strong>{observation.confidence}<span>/ 100</span></strong></div><div><small>Window coverage</small><strong>{series?`${collected}`:'—'}<span>{series?`of ${series.length} points`:'single observation'}</span></strong></div><div><small>Observed</small><strong>{relativeTime(observation.observed_at)}<span>{observation.market} · {observation.unit}</span></strong></div></div>
  {series&&collected<series.length&&<p className="evidence-gap">{series.length-collected} point{series.length-collected===1?'':'s'} in this window {series.length-collected===1?'has':'have'} no observation. Missing points are left as gaps and are never interpolated.</p>}
  <div className="explanation"><h4>How this value was produced</h4><p>{PRODUCED[observation.truth_state]}</p></div>
  <dl className="metadata">{[['Source',observation.source_name??observation.source],['Market',observation.market],['Unit',observation.unit],['Observed at',dateTime(observation.observed_at)],['Fetched at',dateTime(observation.fetched_at)],['Expires at',dateTime(observation.expires_at)],['Observation ID',observation.id],['Snapshot',observation.snapshot_id],['Collector version',observation.collector_version],['Parser version',observation.parser_version],['Usage basis',observation.usage_rights]].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
  {observation.source_url&&<a href={observation.source_url} target="_blank" rel="noreferrer" className="button secondary full">{observation.truth_state==='Demo'?'Open source homepage':'Open original source'}<ExternalLink size={15}/></a>}
  <div className="explanation"><h4>What this tells you</h4><p>{note.what}</p></div>
  <div className="explanation"><h4>What it cannot tell you</h4><p>{note.limits}</p></div>
 </>}</Modal>;
}
export function ProductArt({kind='steamer',small=false}:{kind?:Product['illustration'];small?:boolean}){
 return <div className={`product-art ${kind} ${small?'small':''}`} role="img" aria-label={`${kind} product illustration`}>
  <svg viewBox="0 0 240 170" aria-hidden="true"><defs><linearGradient id={`body-${kind}`} x1="0" y1="0" x2="1" y2="1"><stop stopColor={kind==='blender'?'#b8cbd0':kind==='lamp'?'#868a8f':'#e4e4d9'}/><stop offset="1" stopColor={kind==='blender'?'#63868c':kind==='lamp'?'#353a42':'#a3a699'}/></linearGradient></defs>
   <ellipse cx="124" cy="148" rx="56" ry="8" fill="#000" opacity=".17"/>
   {kind==='steamer'?<g transform="rotate(-15 120 85)"><rect x="89" y="38" width="53" height="100" rx="18" fill={`url(#body-${kind})`}/><path d="M139 57h13q23 0 23 25v21q0 20-25 20h-12v-13h12q11 0 11-11V82q0-12-11-12h-11z" fill="#aaad9f"/><rect x="93" y="28" width="45" height="29" rx="12" fill="#caccc1"/><rect x="101" y="24" width="29" height="10" rx="5" fill="#777f70"/><rect x="108" y="75" width="15" height="25" rx="7" fill="#9a9f8e"/><circle cx="115" cy="82" r="3" fill="#dceec7"/><path d="M103 15q-9-10 0-20m13 20q-9-10 0-20m13 20q-9-10 0-20" fill="none" stroke="#dcead8" opacity=".25" strokeWidth="3"/></g>:
    kind==='lamp'?<g><ellipse cx="150" cy="65" rx="62" ry="59" fill="#f5a65c" opacity=".08"/><ellipse cx="151" cy="65" rx="45" ry="43" fill="#f5a65c" opacity=".08"/><rect x="115" y="61" width="8" height="77" rx="4" fill="#575d65"/><ellipse cx="119" cy="139" rx="34" ry="7" fill="#555b62"/><g transform="rotate(-22 123 61)"><rect x="94" y="40" width="49" height="45" rx="18" fill={`url(#body-${kind})`}/><ellipse cx="139" cy="62" rx="12" ry="21" fill="#272d34"/><ellipse cx="141" cy="62" rx="8" ry="16" fill="#efb770"/></g></g>:
    <g transform="rotate(12 120 85)"><rect x="94" y="24" width="53" height="95" rx="15" fill="#d1e4e3" opacity=".5"/><path d="M100 78q21-11 41 0v25q-20 11-41 0z" fill="#f0b68c" opacity=".65"/><rect x="91" y="19" width="59" height="18" rx="8" fill="#a7c1c5"/><rect x="92" y="107" width="57" height="35" rx="12" fill={`url(#body-${kind})`}/><circle cx="120" cy="124" r="7" fill="#759497"/><circle cx="120" cy="124" r="3" fill="#c3dcdd"/><path d="M110 18v-7q16-10 23 6" fill="none" stroke="#819d9e" strokeWidth="5"/></g>}
  </svg><span>Illustration</span></div>;
}
export function ProductCard({product,onEvidence}:{product:Product;onEvidence:(observation:Observation)=>void}){
 const workspace=useWorkspace();const [busy,setBusy]=useState(false);const watched=workspace.watches.some(w=>w.product_id===product.id);
 return <article className="product-card"><div className="product-card-top"><span className="category-label">{product.category}</span><TruthBadge truth={product.truth_state}/></div><Link to={`/products/${product.id}`} tabIndex={-1} aria-hidden="true"><ProductArt kind={product.illustration}/></Link><div className="product-card-body"><div className="stage"><span/>{product.stage}</div><Link className="product-name" to={`/products/${product.id}`}>{product.name}<ArrowUpRight size={17}/></Link><div className="card-decision"><span className="evidence-status"><small>Evidence</small><DecisionBadge decision={product.decision}/></span><button className="confidence" onClick={()=>product.observations[0]?onEvidence(product.observations[0]):toast.info('No observations collected. Confidence is suppressed.')}>{product.confidence}<span>/100 confidence</span></button></div><div className="card-assessment"><small>Your latest assessment</small><AssessmentSummary assessment={product.latest_assessment} compact/></div><div className="signal-list">{(product.signals||['Product identifier captured','Source verification is pending']).map(s=><div key={s}><Check size={13}/>{s}</div>)}</div><div className="risk"><Info size={14}/><span>{product.blocker}</span></div><div className="card-footer"><span title={dateTime(product.created_at)}>{product.truth_state==='Demo'?'Example · ':''}{relativeTime(product.created_at)}</span><button className="text-button" disabled={busy||watched} onClick={async()=>{setBusy(true);try{await workspace.watch(product.id);toast.success('Added to watchlist');}catch(e){toast.error((e as Error).message);}finally{setBusy(false);}}}>{watched?'Watching':'Watch'}<ChevronRight size={14}/></button></div></div></article>;
}

/** A product chooser that asks the server, not the pages a screen happens to have loaded.
 *
 *  Review finding R10: supplier quotes and RFQs picked from `workspace.products`, which
 *  starts at one page of 50 and is additionally narrowed by whatever was typed on
 *  Discover. A user with 300 products could not quote against the 51st, and a stale
 *  Discover search silently removed options from an unrelated screen. This runs its own
 *  search so every authorised product is reachable, and owns its own term so no other
 *  screen can filter it.
 *
 *  `confirmedOnly` serves the RFQ draft, which may only name a product the user confirmed.
 */
export function ProductPicker({name,confirmedOnly=false}:{name:string;confirmedOnly?:boolean}){
  const w=useWorkspace();
  const [term,setTerm]=useState('');
  const search=term.trim();
  const query=useQuery({
    queryKey:['product-picker',w.user?.workspace_id,search,confirmedOnly],
    queryFn:()=>api<{products:Product[];total:number}>(`/products?limit=50${search?`&search=${encodeURIComponent(search)}`:''}`),
    enabled:!w.demo&&!!w.user,retry:false});
  const matched=w.demo
    ? w.products.filter(p=>!search||`${p.name} ${p.asin}`.toLowerCase().includes(search.toLowerCase()))
    : query.data?.products ?? [];
  const options=confirmedOnly?matched.filter(p=>p.confirmed):matched;
  const total=w.demo?options.length:query.data?.total ?? 0;
  return <>
    <label>Find a product<span className="search-input"><Search size={16}/>
      <input aria-label="Search your products" placeholder="Search by name or identifier…"
             value={term} onChange={e=>setTerm(e.target.value)}/></span></label>
    <label>Product<select name={name} required disabled={!options.length}>
      {options.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
    </select></label>
    {options.length
      ? <p className="form-caption">{query.isFetching?'Searching…':`Choosing from ${options.length} of ${total} products.`}{total>options.length&&' Search to narrow to one that is not listed.'}</p>
      : query.isError
        // A failed lookup is not an answer about the workspace. Saying "no product
        // matches" here would report a fact this picker could not check (finding F03).
        ? <p className="form-caption">Your products could not be loaded, so this list is
            incomplete — this is not a statement that you have none.{' '}
            <button type="button" className="text-button" onClick={()=>void query.refetch()}>Retry</button></p>
        : <p className="form-caption">{query.isFetching?'Searching…':search?'No product matches that search.':'No products yet.'}</p>}
  </>;
}
