import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, Check, FilePlus2, Info, ShieldCheck, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Empty, Modal, Notice, TruthBadge } from '@/shared/UI';
import { api, post } from '@/lib/api';
import { dateTime } from '@/lib/utils';
import type { ComplianceGate, ComplianceReview, EvidenceQuality, Observation, Product } from '@/types';

/** Recording evidence and requesting or deciding an import-readiness review
 *  (action plan E06, N02, N03). Both are the answers to blockers the app used to state
 *  without offering any way to resolve them. */

const METRICS = ['Search interest', 'Review velocity', 'Marketplace rank', 'Social mentions',
  'Local listing price', 'Local listing count', 'Local seller count', 'Local demand signal', 'Other'];
const MARKETS = [['NG', 'Nigeria (destination)'], ['US', 'United States (discovery)'], ['CN', 'China (supply)'], ['GLOBAL', 'Global']] as const;

export interface EvidenceResponse {
  observations: Observation[]; truth_state: string; reason: string;
  quality: EvidenceQuality; compliance: ComplianceGate; metrics: string[];
}
export interface ComplianceResponse {
  gate: ComplianceGate; current: ComplianceReview | null; history: ComplianceReview[];
  can_review: boolean; review_version: string;
}

export function useEvidence(productId: string | undefined, enabled: boolean) {
  return useQuery({ queryKey: ['evidence', productId], enabled: !!productId && enabled, retry: false,
    queryFn: () => api<EvidenceResponse>(`/products/${productId}/evidence`) });
}
export function useCompliance(productId: string | undefined, enabled: boolean) {
  return useQuery({ queryKey: ['compliance', productId], enabled: !!productId && enabled, retry: false,
    queryFn: () => api<ComplianceResponse>(`/products/${productId}/compliance`) });
}

/** The quality reading, component by component, so the number can be argued with. */
export function EvidenceQualityPanel({ quality }: { quality: EvidenceQuality }) {
  return <section className="panel quality-panel">
    <div className="section-heading">
      <div><h2>Why the evidence score is {quality.confidence}</h2><p>{quality.score_meaning}</p></div>
      <span className="method-version">{quality.method_version}</span>
    </div>
    <div className="quality-rows">{quality.components.map(component =>
      <div className="quality-row" key={component.name}>
        <span>{component.name}<small>{component.detail}</small></span>
        <div className="quality-track"><i style={{ width: `${(component.points / component.max) * 100}%` }} /></div>
        <strong>{component.points}<small>/ {component.max}</small></strong>
      </div>)}
    </div>
    {quality.capped_at !== null && quality.raw_points > quality.capped_at &&
      <Notice kind="amber">The components add up to {quality.raw_points}, but every record here was entered
        by a person, so the score is held at {quality.capped_at}. Only a connected, authorised collector can
        raise it further — and none is connected.</Notice>}
    {quality.limitations.length > 0 && <div className="limitations">
      <h4>What this score does not tell you</h4>
      {quality.limitations.map(limitation => <p key={limitation}><Info size={13} />{limitation}</p>)}
    </div>}
  </section>;
}

/** Record one dated observation. The truth state is set by the server, not here. */
export function RecordEvidence({ product, open, onOpenChange }:
  { product: Product; open: boolean; onOpenChange: (open: boolean) => void }) {
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return <Modal open={open} onOpenChange={onOpenChange} title="Record evidence"
    description="A dated observation you made, with where it came from and how you read it.">
    <Notice>What you record here is stored as <strong>user input</strong>, never as an observed fact.
      It keeps your name, the date you observed it, and the method you used, so it can be judged later.</Notice>
    <form className="stack" onSubmit={async event => {
      event.preventDefault();
      setBusy(true); setError('');
      const data = new FormData(event.currentTarget);
      try {
        await post(`/products/${product.id}/evidence`, {
          metric: String(data.get('metric')), unit: String(data.get('unit')),
          value: data.get('value') === '' ? null : Number(data.get('value')),
          market: String(data.get('market')), observed_at: String(data.get('observed_at')),
          source_name: String(data.get('source_name')), source_url: String(data.get('source_url') || ''),
          method: String(data.get('method')), notes: String(data.get('notes') || ''),
        });
        await client.invalidateQueries();
        onOpenChange(false);
        toast.success('Evidence recorded as user input');
      } catch (problem) { setError((problem as Error).message); } finally { setBusy(false); }
    }}>
      <div className="input-grid">
        <label>What did you measure?<select name="metric" aria-label="What did you measure?" defaultValue="Search interest">{METRICS.map(metric => <option key={metric}>{metric}</option>)}</select></label>
        <label>Market<select name="market" aria-label="Market" defaultValue="NG">{MARKETS.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>
        <label>Value<input name="value" aria-label="Value" type="number" step="any" placeholder="Leave empty if not a number" /></label>
        <label>Unit<input name="unit" aria-label="Unit" required minLength={1} maxLength={40} placeholder="index / 100, NGN, listings" /></label>
        <label>Date observed<input name="observed_at" aria-label="Date observed" type="date" required max={new Date().toISOString().slice(0, 10)} /></label>
        <label>Source<input name="source_name" aria-label="Source" required minLength={2} maxLength={160} placeholder="Google Trends export, Lagos market survey" /></label>
      </div>
      <label>Source link (optional)<input name="source_url" aria-label="Source link" type="url" pattern="https://.*" maxLength={2000} placeholder="https://" /></label>
      <label>How did you read it?<textarea name="method" aria-label="How did you read it?" required minLength={4} maxLength={400}
        placeholder="Exported the 12-month series for Nigeria and read the latest weekly point." /></label>
      <label>Notes (optional)<textarea name="notes" aria-label="Notes" maxLength={2000} placeholder="Anything that limits how this should be read." /></label>
      {error && <div role="alert" className="form-error">{error}</div>}
      <button className="button primary" disabled={busy}>{busy ? 'Recording…' : 'Record evidence'}<Check size={16} /></button>
    </form>
  </Modal>;
}

/** The import-readiness gate: its state, how to ask for a review, and — for a reviewer —
 *  how to decide one. An analyst cannot decide their own request. */
export function CompliancePanel({ product }: { product: Product }) {
  const client = useQueryClient();
  const state = useCompliance(product.id, true);
  const [requesting, setRequesting] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const gate = state.data?.gate;
  const current = state.data?.current;

  return <section className="panel compliance-panel">
    <div className="section-heading">
      <div><h2>Import readiness</h2><p>Resolved by a reviewer, never by a dropdown.</p></div>
      <ShieldCheck size={19} />
    </div>
    {state.error ? <Notice kind="amber">{state.error.message}</Notice> : gate &&
      <Notice kind={gate.resolved ? 'muted' : 'amber'}>
        <strong>{{ none: 'Not reviewed', requested: 'Waiting for a reviewer', approved: 'Approved',
          rejected: 'Rejected', expired: 'Approval expired', support_expired: 'Supporting source expired',
          review_incomplete: 'New review required', superseded: 'Replaced by a new request',
          more_information: 'More information needed' }[gate.status]}</strong>
        {' — '}{gate.reason}
        {gate.re_review_pending && <> A new review has been requested and is waiting for a reviewer;
          the decision above stands until that one is decided.</>}
      </Notice>}
    {gate?.resolved && <dl className="metadata">
      <div><dt>Classification</dt><dd>{gate.hs_code || 'Not stated'}</dd></div>
      <div><dt>Valid until</dt><dd>{gate.expires_at ? dateTime(gate.expires_at) : '—'}</dd></div>
    </dl>}
    {!!gate?.requirements?.length && <div className="requirement-list">
      <h4>Requirements the reviewer recorded</h4>
      {gate.requirements.map(requirement => <p key={requirement}><Check size={13} />{requirement}</p>)}
    </div>}
    {current?.sources?.length ? <div className="requirement-list">
      <h4>Sources the decision rests on</h4>
      {current.sources.map(source => <p key={source.url}><Info size={13} />
        <a href={source.url} target="_blank" rel="noreferrer">{source.title}</a> — {source.publisher}, effective {source.effective_from}</p>)}
    </div> : null}
    <div className="page-actions">
      {gate && gate.status !== 'requested' &&
        <button className="button secondary" onClick={() => setRequesting(true)}><FilePlus2 size={15} />
          {gate.status === 'none' ? 'Request a review' : 'Request a fresh review'}</button>}
      {state.data?.can_review && current?.status === 'requested' &&
        <button className="button primary" onClick={() => setDeciding(true)}>Decide this review<ArrowRight size={15} /></button>}
    </div>
    {!state.data?.can_review && current?.status === 'requested' &&
      <p className="muted-text">Your workspace role cannot decide a review. It is waiting for someone who can.</p>}

    <Modal open={requesting} onOpenChange={setRequesting} title="Request an import-readiness review"
      description="Give the reviewer what they need to answer without chasing context.">
      <form className="stack" onSubmit={async event => {
        event.preventDefault(); setBusy(true); setError('');
        const data = new FormData(event.currentTarget);
        try {
          await post(`/products/${product.id}/compliance/requests`, {
            product_id: product.id, destination: 'NG',
            specifications: String(data.get('specifications')), intended_use: String(data.get('intended_use')),
            question: String(data.get('question')), hs_code_candidate: String(data.get('hs_code_candidate') || ''),
          });
          await client.invalidateQueries(); setRequesting(false); toast.success('Review requested');
        } catch (problem) { setError((problem as Error).message); } finally { setBusy(false); }
      }}>
        <label>Product specifications<textarea name="specifications" aria-label="Product specifications" required minLength={10} maxLength={4000}
          placeholder="Power, materials, dimensions, voltage, packaging — whatever bears on classification." /></label>
        <label>Intended use<input name="intended_use" aria-label="Intended use" required minLength={4} maxLength={1000} placeholder="Retail sale to consumers in Lagos" /></label>
        <label>Your question<textarea name="question" aria-label="Your question" required minLength={10} maxLength={2000}
          placeholder="Which classification applies, and what certification is required before import?" /></label>
        <label>Candidate HS code (optional)<input name="hs_code_candidate" aria-label="Candidate HS code" maxLength={20} placeholder="8451.30" />
          <small>A candidate stays a candidate until a reviewer confirms it.</small></label>
        {error && <div role="alert" className="form-error">{error}</div>}
        <button className="button primary" disabled={busy}>{busy ? 'Sending…' : 'Send to a reviewer'}<ArrowRight size={16} /></button>
      </form>
    </Modal>

    <Modal open={deciding} onOpenChange={setDeciding} title="Decide this review"
      description="An approval must cite the official sources it rests on." drawer>
      {current && <div className="review-context">
        <h4>{current.product_name}</h4>
        <p><strong>Specifications:</strong> {current.specifications}</p>
        <p><strong>Intended use:</strong> {current.intended_use}</p>
        <p><strong>Question:</strong> {current.question}</p>
        {current.hs_code_candidate && <p><strong>Candidate code:</strong> {current.hs_code_candidate}</p>}
      </div>}
      <form className="stack" onSubmit={async event => {
        event.preventDefault(); setBusy(true); setError('');
        const data = new FormData(event.currentTarget);
        const status = String(data.get('status'));
        const requirements = String(data.get('requirements') || '').split('\n').map(line => line.trim()).filter(Boolean);
        const sources = String(data.get('source_url') || '').trim() ? [{
          title: String(data.get('source_title')), url: String(data.get('source_url')),
          publisher: String(data.get('source_publisher')), effective_from: String(data.get('source_effective_from')),
        }] : [];
        try {
          await post(`/compliance/reviews/${current!.id}/decision`, {
            status, rationale: String(data.get('rationale')), hs_code: String(data.get('hs_code') || ''),
            requirements, sources, validity_days: Number(data.get('validity_days')),
          });
          await client.invalidateQueries(); setDeciding(false); toast.success('Review decided');
        } catch (problem) { setError((problem as Error).message); } finally { setBusy(false); }
      }}>
        <label>Decision<select name="status" aria-label="Decision" defaultValue="approved">
          <option value="approved">Approved for import, subject to the requirements below</option>
          <option value="rejected">Rejected — do not proceed</option>
          <option value="more_information">More information needed</option>
        </select></label>
        <label>Rationale<textarea name="rationale" aria-label="Rationale" required minLength={10} maxLength={4000}
          placeholder="What you concluded and why, referring to the sources below." /></label>
        <div className="input-grid">
          <label>Confirmed HS code<input name="hs_code" aria-label="Confirmed HS code" maxLength={20} placeholder="8451.30.00" /></label>
          <label>Valid for (days)<input name="validity_days" aria-label="Valid for (days)" type="number" min={1} max={365} defaultValue={180} /></label>
        </div>
        <label>Requirements, one per line<textarea name="requirements" aria-label="Requirements, one per line" maxLength={2000}
          placeholder={'SONCAP product certificate before shipment\nForm M registration prior to import'} /></label>
        <fieldset><legend>Official source</legend><div className="input-grid">
          <label>Title<input name="source_title" aria-label="Source title" maxLength={300} placeholder="Import guidelines, chapter 84" /></label>
          <label>Publisher<input name="source_publisher" aria-label="Source publisher" maxLength={200} placeholder="Regulator" /></label>
          <label>Link<input name="source_url" aria-label="Source link" type="url" pattern="https://.*" maxLength={2000} placeholder="https://" /></label>
          <label>Effective from<input name="source_effective_from" aria-label="Effective from" type="date" /></label>
        </div></fieldset>
        {error && <div role="alert" className="form-error">{error}</div>}
        <button className="button primary" disabled={busy}>{busy ? 'Saving…' : 'Record this decision'}<Check size={16} /></button>
      </form>
    </Modal>
  </section>;
}

/** The evidence ledger: every record, its provenance, and a way to withdraw a mistake. */
export function EvidenceLedger({ product, records, unavailable, onRetry, onInspect, onAdd }:
  { product: Product; records: Observation[]; unavailable?: boolean; onRetry?: () => void;
    onInspect: (observation: Observation) => void; onAdd: () => void }) {
  const client = useQueryClient();
  const [removing, setRemoving] = useState('');
  return <div className="panel evidence-ledger">
    <div className="section-heading">
      <div><h2>Evidence ledger</h2><p>Every record, who entered it, when it was observed and how.</p></div>
      <button className="button primary" onClick={onAdd}><FilePlus2 size={15} />Record evidence</button>
    </div>
    {records.length ? <div className="table-scroll"><table>
      <thead><tr><th>Metric</th><th>Value</th><th>Market</th><th>Observed</th><th>Source</th><th>Truth state</th><th /></tr></thead>
      <tbody>{records.map(observation => <tr key={observation.id}>
        <td>{observation.metric}</td>
        <td>{observation.value === null || observation.value === undefined ? 'Not a number' : `${observation.value} ${observation.unit}`}</td>
        <td>{observation.market}</td>
        <td>{observation.observed_at}</td>
        <td>{observation.source_url
          ? <a className="table-link" href={observation.source_url} target="_blank" rel="noreferrer">{observation.source_name ?? observation.source}</a>
          : (observation.source_name ?? observation.source)}</td>
        <td><TruthBadge truth={observation.truth_state} /></td>
        <td className="row-actions">
          <button className="text-button" onClick={() => onInspect(observation)}>Inspect</button>
          <button className="icon-button" aria-label={`Withdraw ${observation.metric}`} disabled={removing === observation.id}
            onClick={async () => {
              setRemoving(observation.id);
              try {
                await api(`/products/${product.id}/evidence/${observation.id}`, { method: 'DELETE' });
                await client.invalidateQueries();
                toast.success('Record withdrawn. Saved assessments keep their own snapshot.');
              } catch (problem) { toast.error((problem as Error).message); } finally { setRemoving(''); }
            }}><Trash2 size={15} /></button>
        </td>
      </tr>)}</tbody>
    </table></div> : unavailable
      // An unavailable read is not an empty ledger. Saying "nothing recorded" here would
      // state as fact something this screen could not check (review finding F03).
      ? <Notice kind="amber">This product’s evidence records could not be loaded, so the ledger
          below is not shown. This is not a statement that no evidence exists.
          {onRetry && <> <button className="text-button" onClick={onRetry}>Retry</button></>}
        </Notice>
      : <Empty title="No evidence recorded yet"
      action={<button className="button primary" onClick={onAdd}><FilePlus2 size={15} />Record your first observation</button>}>
      Nothing has been collected automatically, and nothing has been entered. Record what you have found,
      with its date and source, and it becomes part of this product’s ledger.
    </Empty>}
  </div>;
}
