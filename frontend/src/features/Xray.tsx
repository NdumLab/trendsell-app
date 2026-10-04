import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Check, CircleDashed, Globe2, Image, Info, Link2, LoaderCircle, ScanLine, Search, ShieldCheck, TextSearch, Video } from 'lucide-react';
import { toast } from 'sonner';
import { useWorkspace } from '@/shared/Workspace';
import { Notice, PageTitle, TruthBadge } from '@/shared/UI';
import { api, post } from '@/lib/api';
import { dateTime } from '@/lib/utils';
import { parseAmazon } from '@/lib/identifier';
import type { DiscoveryCandidate, DiscoveryRun, Job } from '@/types';

type Mode = 'identifier' | 'keyword';

export default function Xray(){
 const w=useWorkspace();
 const [params]=useSearchParams();
 const [mode,setMode]=useState<Mode>('identifier');
 const [input,setInput]=useState(params.get('input')||'');
 const [keyword,setKeyword]=useState('');
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const [jobId,setJobId]=useState('');
 const [discoveryId,setDiscoveryId]=useState('');
 const [demoJob,setDemoJob]=useState<Job|null>(null);
 const [name,setName]=useState('');
 const [confirmed,setConfirmed]=useState(false);
 const [refreshedJob,setRefreshedJob]=useState('');
 const jobQuery=useQuery({queryKey:['job',jobId],queryFn:()=>api<Job>(`/research-jobs/${jobId}`),enabled:!!jobId&&!w.demo,refetchInterval:q=>['queued','running'].includes(q.state.data?.status||'queued')?1000:false});
 const discoveryQuery=useQuery({queryKey:['discovery',discoveryId],queryFn:()=>api<DiscoveryRun>(`/discovery/${discoveryId}`),enabled:!!discoveryId&&!w.demo,refetchInterval:q=>['queued','running'].includes(q.state.data?.status||'queued')?1000:false,retry:false});
 const job=w.demo?demoJob:jobQuery.data;
 const discovery=discoveryQuery.data;
 const product=w.products.find(p=>p.id===job?.product_id);

 useEffect(()=>{
  if(jobId&&job&&!['queued','running'].includes(job.status)&&refreshedJob!==jobId){
   setRefreshedJob(jobId);
   void w.refresh();
  }
 },[jobId,job?.status,refreshedJob]);

 const submitIdentifier=async(e:React.FormEvent)=>{
  e.preventDefault();setError('');setConfirmed(false);
  try{parseAmazon(input);}catch(problem){setError((problem as Error).message);return;}
  if(!w.requireUser())return;
  setBusy(true);
  try{
   if(w.demo){
    const {demoProducts}=await import('@/demo');const p={...demoProducts[0],confirmed:false};
    w.addDemoProduct(p);setName(p.name);
    setDemoJob({id:'demo-job',product_id:p.id,status:'partial',events:[
     {id:1,step:'Example investigation loaded',status:'succeeded',detail:'The garment steamer is a synthetic demonstration. Your input is not fetched or matched to a real product.',at:new Date().toISOString()},
     {id:2,step:'Demo evidence attached',status:'succeeded',detail:'Illustrative search and review values are labeled Demo.',at:new Date().toISOString()},
     {id:3,step:'Live source collection',status:'unavailable',detail:'No external collectors run in demo mode.',at:new Date().toISOString()},
    ]});
   }else{
    const result=await post<Job>('/xray',{input,market:'NG'},crypto.randomUUID());
    setJobId(result.id);setRefreshedJob('');await w.refresh();setName('');
   }
  }catch(problem){setError((problem as Error).message);}finally{setBusy(false);}
 };

 const submitKeyword=async(e:React.FormEvent)=>{
  e.preventDefault();setError('');setDiscoveryId('');setJobId('');setConfirmed(false);
  if(keyword.trim().length<2){setError('Enter at least two characters to search for current product candidates.');return;}
  if(!w.requireUser())return;
  if(w.demo){setError('Keyword collection is unavailable in demo mode. Exit demo and use an authorised workspace connection.');return;}
  setBusy(true);
  try{
   const result=await post<DiscoveryRun>('/discovery',{query:keyword.trim(),limit:10},crypto.randomUUID());
   setDiscoveryId(result.id);
  }catch(problem){setError((problem as Error).message);}finally{setBusy(false);}
 };

 const investigateCandidate=async(candidate:DiscoveryCandidate)=>{
  if(!discovery||!w.requireUser())return;
  setBusy(true);setError('');setConfirmed(false);
  try{
   const result=await post<Job>('/xray',{input:candidate.asin,market:'NG',discovery_id:discovery.id},crypto.randomUUID());
   setInput(candidate.asin);setJobId(result.id);setRefreshedJob('');await w.refresh();setName('');
  }catch(problem){setError((problem as Error).message);}finally{setBusy(false);}
 };

 return <>
  <PageTitle eyebrow="FROM IDEA TO INVESTIGATION" title="Put a product under the X-Ray." description="Discover current candidates or start with an identifier. Resolve the match, inspect the evidence, then test the economics."/>
  <div className="xray-layout"><div>
   <section className="panel xray-capture">
    <div className="tab-bar">
     <button type="button" className={`tab ${mode==='identifier'?'active':''}`} onClick={()=>{setMode('identifier');setError('');}}><Link2 size={15}/>URL or ASIN</button>
     <button type="button" className={`tab ${mode==='keyword'?'active':''}`} onClick={()=>{setMode('keyword');setError('');}}><TextSearch size={15}/>Keyword</button>
     {[{icon:Image,label:'Image'},{icon:Video,label:'Video'}].map(({icon:Icon,label})=><span className="tab unavailable" key={label} title="Not available in the pilot"><Icon size={15}/>{label}<small>Later</small></span>)}
    </div>
    {mode==='identifier'?<form onSubmit={submitIdentifier} className="xray-form">
     <label htmlFor="xray-input">What are you investigating?</label>
     <div className="xray-input"><ScanLine size={23}/><input id="xray-input" required value={input} onChange={e=>setInput(e.target.value)} placeholder="Paste an Amazon US product URL or ASIN" maxLength={2048}/></div>
     <RouteContext/>
     {error&&<div className="form-error" role="alert">{error}</div>}
     <button className="button primary full" disabled={busy}>{busy?<LoaderCircle className="spin" size={17}/>:<ScanLine size={17}/>} {busy?'Creating investigation…':'Start investigation'}<ArrowRight size={16}/></button>
     <p className="form-caption">Identifiers are captured without fetching arbitrary URLs. Source availability determines what can be verified.</p>
    </form>:<form onSubmit={submitKeyword} className="xray-form">
     <label htmlFor="keyword-input">Find current product candidates</label>
     <div className="xray-input"><Search size={23}/><input id="keyword-input" required minLength={2} maxLength={200} value={keyword} onChange={e=>setKeyword(e.target.value)} placeholder="For example, portable garment steamer"/></div>
     <RouteContext/>
     {error&&<div className="form-error" role="alert">{error}</div>}
     <button className="button primary full" disabled={busy}>{busy?<LoaderCircle className="spin" size={17}/>:<Search size={17}/>} {busy?'Searching current source…':'Find candidates'}<ArrowRight size={16}/></button>
     <p className="form-caption">Results are current organic candidates from the configured provider. Rank, price, ratings, and purchase indicators do not prove sales, suitability, or attribution.</p>
    </form>}
   </section>

   {discoveryQuery.error&&<Notice kind="amber">Discovery status is unavailable: {discoveryQuery.error.message} <button className="text-button" onClick={()=>void discoveryQuery.refetch()}>Retry status check</button></Notice>}
   {discovery&&<section className="panel discovery-panel" aria-live="polite">
    <div className="section-heading"><div><h2>Keyword candidates</h2><p>{discovery.query}</p></div><span className="status-label">{discovery.status}</span></div>
    {['queued','running'].includes(discovery.status)&&<Notice>Waiting for the configured current product source. Authentication alone is not counted as collection success.</Notice>}
    {discovery.status==='unavailable'&&<Notice kind="amber"><strong>No candidates were recorded.</strong> {discovery.detail}{discovery.error_code?` Error type: ${discovery.error_code}.`:''}</Notice>}
    {discovery.status==='succeeded'&&discovery.candidates.length===0&&<Notice kind="amber">The provider collection completed but returned no organic candidates. No product match is implied.</Notice>}
    {discovery.status==='succeeded'&&discovery.candidates.length>0&&<>
     <Notice>{discovery.detail} Select a candidate only to begin exact-ASIN resolution; the candidate itself is not a confirmed product match.</Notice>
     <div className="table-scroll"><table><thead><tr><th>Current candidate</th><th>Observed fields</th><th>Match state</th><th/></tr></thead><tbody>{discovery.candidates.map(candidate=><tr key={candidate.asin}>
      <td><strong>{candidate.title||'Title unavailable'}</strong><small>{candidate.asin} · organic position {candidate.absolute_position??candidate.position??'unavailable'}</small></td>
      <td>{candidate.price_from!=null?`${candidate.currency||'Currency unavailable'} ${candidate.price_from}`:'Price unavailable'}<small>Rating {candidate.rating??'unavailable'} · votes {candidate.rating_votes??'unavailable'}</small></td>
      <td><TruthBadge truth="Observed"/><small>Candidate only · exact match incomplete</small></td>
      <td><button className="button secondary" disabled={busy} onClick={()=>void investigateCandidate(candidate)}>Investigate<ArrowRight size={15}/></button></td>
     </tr>)}</tbody></table></div>
     <p className="form-caption">Observed {discovery.observed_at?dateTime(discovery.observed_at):'time unavailable'} · collected {discovery.collected_at?dateTime(discovery.collected_at):'time unavailable'} · expires {discovery.expires_at?dateTime(discovery.expires_at):'under configured policy'}.</p>
    </>}
   </section>}

   {jobQuery.error&&<Notice kind="amber">Investigation status is unavailable: {jobQuery.error.message}<button className="text-button" onClick={()=>void jobQuery.refetch()}>Retry</button></Notice>}
   {job&&<section className="panel job-panel" aria-live="polite"><div className="section-heading"><h2>Investigation activity</h2><span className="status-label">{job.status}</span></div><p className="muted-text">{w.demo?'Demo events describe the fixture that was loaded.':'These events come from your saved research job.'}</p><div className="job-events">{job.events.map(event=><div className="job-event" key={event.id}><span className={`event-icon ${event.status}`}>{event.status==='succeeded'?<Check size={16}/>:event.status==='unavailable'?<Info size={16}/>:<CircleDashed size={16}/>}</span><div><h4>{event.step}<span>{event.status}</span></h4><p>{event.detail}</p><time dateTime={event.at}>{dateTime(event.at)}</time></div></div>)}</div></section>}
   {job&&product&&<section className="panel confirmation"><div className="section-heading"><h2>{product.confirmed?'Product identity resolved':'Confirm the product'}</h2><TruthBadge truth={w.demo?'Demo':product.truth_state}/></div>{product.confirmed?<>
    <Notice>{product.truth_state==='Observed'?'The configured catalog source returned this exact ASIN. Current fields and collection provenance are saved; listing claims are not independently certified.':'This product was confirmed by a workspace user and remains user input.'}</Notice>
    {product.discovery_context&&<Notice>Selected from keyword “{product.discovery_context.query}”. {product.discovery_context.limitations}</Notice>}
    <div className="identity-row"><span>Captured identifier</span><code>{product.asin}</code><span>Identity source <strong>{product.truth_state==='Observed'?(product.identity_source||'External catalog source'):'Workspace user'}</strong></span></div>
    <div className="page-actions"><Link to={`/products/${product.id}`} className="button primary">View product evidence<ArrowRight size={16}/></Link><Link to={`/decisions?product=${product.id}`} className="button secondary">Test economics<ArrowRight size={16}/></Link></div>
   </>:<>
    <Notice>Product identity is unverified by an external source. Your confirmation records what you intend to investigate; it does not verify the listing’s claims.</Notice>
    <div className="identity-row"><span>Captured identifier</span><code>{product.asin}</code><span>Match confidence <strong>Unavailable</strong></span></div>
    <form className="stack" onSubmit={async e=>{e.preventDefault();setBusy(true);try{await w.confirm(product.id,name);setConfirmed(true);toast.success('Product identity confirmed');}catch(problem){toast.error((problem as Error).message);}finally{setBusy(false);}}}><label>Product name<input value={name} onChange={e=>setName(e.target.value)} required minLength={2} maxLength={160} placeholder="Enter the product name from the listing"/></label>{confirmed?<div className="page-actions"><Link to={`/products/${product.id}`} className="button primary">View product evidence<ArrowRight size={16}/></Link><Link to={`/decisions?product=${product.id}`} className="button secondary">Test economics<ArrowRight size={16}/></Link></div>:<button className="button primary" disabled={busy}>Confirm this product<Check size={16}/></button>}</form>
   </>}</section>}
  </div><aside className="xray-aside"><div className="panel"><div className="section-icon lime"><ShieldCheck size={23}/></div><h3>Clarity at every step.</h3><p>An investigation is useful even when the answer is “we need more evidence.”</p><div className="numbered-steps">{[['01','Discover or resolve','Collect current candidates, then resolve an exact product identity.'],['02','Inspect the evidence','See source references, timestamps, observations, and gaps.'],['03','Test your economics','Use explicit assumptions; missing evidence keeps the result at WATCH or insufficient.']].map(([number,title,text])=><div key={number}><span>{number}</span><div><h4>{title}</h4><p>{text}</p></div></div>)}</div></div><div className="try-demo"><ScanLine size={20}/><h4>Just looking around?</h4><p>Explore a garment steamer example. It is synthetic and never counts as live collection.</p><button className="text-button" onClick={async()=>{await w.enterDemo();setMode('identifier');setInput('DEMO000001');setJobId('');setDiscoveryId('');setDemoJob(null);}}>Load the demo input<ArrowRight size={14}/></button></div></aside></div>
 </>;
}

function RouteContext(){return <div className="xray-destination"><span><Globe2 size={16}/>Discovery<strong>Amazon US</strong></span><ArrowRight size={15}/><span><span className="nigeria-flag"/>Destination<strong>Nigeria</strong></span></div>;}
