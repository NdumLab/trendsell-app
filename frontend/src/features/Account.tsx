import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { KeyRound, LogOut, MailCheck, ShieldAlert, ShieldCheck, Trash2 } from 'lucide-react';
import { useWorkspace } from '@/shared/Workspace';
import { Modal, Notice } from '@/shared/UI';
import { api, del, post } from '@/lib/api';
import { dateTime } from '@/lib/utils';
import type { AccountSession } from '@/types';

/** Account security: the browser half of action plan P03.
 *
 *  The API has carried password change, session revocation, email verification and
 *  account deletion for some time; none of it had a screen, so a pilot user could not
 *  reach any of it without a client that speaks HTTP. Everything here is the person's
 *  own account, so nothing on this screen depends on a workspace role.
 *
 *  Mail delivery is still unconfigured in production, so the two token flows accept a
 *  pasted token as well as a mailed link. That is deliberate and labelled: it is the
 *  difference between a flow that exists and one that waits on a provider decision.
 */

function useSessions(enabled: boolean) {
  return useQuery({ queryKey: ['auth-sessions'], enabled, retry: false,
    queryFn: () => api<{ sessions: AccountSession[]; total: number }>('/auth/sessions') });
}

function useDelivery() {
  return useQuery({ queryKey: ['config'], retry: false,
    queryFn: () => api<{ mail_delivery_configured: boolean }>('/config') });
}

/** Prove control of the address. Verification is implemented and testable locally; only
 *  delivering the message waits on the provider. */
export function EmailVerification() {
  const w = useWorkspace();
  const delivery = useDelivery();
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState(false);
  if (!w.user) return null;
  const verified = !!w.user.email_verified;
  return <section className="panel settings-card">
    <div className="section-heading"><h2>Email address</h2>{verified ? <MailCheck size={18}/> : <ShieldAlert size={18}/>}</div>
    <dl className="metadata">
      <div><dt>Address</dt><dd>{w.user.email}</dd></div>
      <div><dt>Ownership</dt><dd>{verified
        ? `Verified ${dateTime(w.user.email_verified_at ?? undefined)}`
        : 'Not verified'}</dd></div>
    </dl>
    {verified
      ? <Notice>This address has been confirmed by redeeming a verification token.</Notice>
      : <>
        <Notice kind="amber">Nobody has proved control of this address yet. Existing accounts were
          deliberately not marked verified when verification was added.
          {!delivery.data?.mail_delivery_configured &&
            ' No mail transport is configured on this deployment, so a verification message cannot be delivered — an operator can issue a token instead.'}
        </Notice>
        <div className="stack">
          <button className="button secondary" disabled={busy || !delivery.data?.mail_delivery_configured}
            onClick={async () => { setBusy(true);
              try { await post('/auth/email-verification/request', {}); toast.success('Verification message sent'); }
              catch (problem) { toast.error((problem as Error).message); } finally { setBusy(false); } }}>
            <MailCheck size={15}/>Send a verification message
          </button>
          <label>Verification token
            <input value={token} onChange={event => setToken(event.target.value)}
                   placeholder="Paste the token from your message" autoComplete="off"/>
          </label>
          <button className="button primary" disabled={busy || token.trim().length < 20}
            onClick={async () => { setBusy(true);
              try { await post('/auth/email-verification/confirm', { token: token.trim() });
                    setToken(''); await w.refresh(); toast.success('Email address verified'); }
              catch (problem) { toast.error((problem as Error).message); } finally { setBusy(false); } }}>
            <ShieldCheck size={15}/>Verify this address
          </button>
        </div>
      </>}
  </section>;
}

/** Change the password while signed in. Every other session ends, and so does every
 *  outstanding recovery token (review finding F02). */
export function ChangePassword() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return <section className="panel settings-card">
    <div className="section-heading"><h2>Password</h2><KeyRound size={18}/></div>
    <form className="stack" onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError('');
      const data = new FormData(event.currentTarget);
      if (data.get('new_password') !== data.get('confirm_password')) {
        setError('The two new passwords do not match.'); setBusy(false); return;
      }
      try {
        const result = await post<{ sessions_revoked: number }>('/auth/password', {
          current_password: data.get('current_password'), new_password: data.get('new_password') });
        (event.target as HTMLFormElement).reset();
        toast.success(result.sessions_revoked
          ? `Password changed. ${result.sessions_revoked} other session(s) ended.`
          : 'Password changed.');
      } catch (problem) { setError((problem as Error).message); } finally { setBusy(false); }
    }}>
      <label>Current password<input name="current_password" type="password" required minLength={12}
        maxLength={128} autoComplete="current-password"/></label>
      <label>New password<input name="new_password" type="password" required minLength={12}
        maxLength={128} autoComplete="new-password" placeholder="At least 12 characters"/></label>
      <label>Confirm new password<input name="confirm_password" type="password" required minLength={12}
        maxLength={128} autoComplete="new-password"/></label>
      {error && <div role="alert" className="form-error">{error}</div>}
      <p className="form-caption">Changing your password ends every other session on this account and
        invalidates any password-reset link that has already been issued.</p>
      <button className="button primary" disabled={busy}>{busy ? 'Changing…' : 'Change password'}</button>
    </form>
  </section>;
}

/** Every session open on this account, and a way to end one. */
export function ActiveSessions() {
  const w = useWorkspace();
  const client = useQueryClient();
  const sessions = useSessions(!!w.user && !w.demo);
  const [ending, setEnding] = useState('');
  return <section className="panel settings-card">
    <div className="section-heading"><h2>Active sessions</h2><LogOut size={18}/></div>
    {sessions.isError
      ? <Notice kind="amber">Your sessions could not be loaded, so none are listed — this is not a
          statement that you have none. <button className="text-button"
          onClick={() => void sessions.refetch()}>Retry</button></Notice>
      : <div className="table-scroll"><table>
        <thead><tr><th>Signed in</th><th>Client</th><th>Expires</th><th/></tr></thead>
        <tbody>{(sessions.data?.sessions ?? []).map(session => <tr key={session.id}>
          <td>{dateTime(session.started_at)}{session.current && <small>This device</small>}</td>
          <td><small>{session.client || 'Unknown client'}</small></td>
          <td>{dateTime(session.expires_at)}</td>
          <td><button className="icon-button" disabled={ending === session.id}
            aria-label={session.current ? 'End this session and sign out' : 'End this session'}
            onClick={async () => { setEnding(session.id);
              try {
                const result = await del<{ was_current: boolean }>(`/auth/sessions/${session.id}`);
                await client.invalidateQueries({ queryKey: ['auth-sessions'] });
                if (result.was_current) { await w.refresh(); toast.success('Signed out on this device'); }
                else toast.success('That session was ended');
              } catch (problem) { toast.error((problem as Error).message); } finally { setEnding(''); } }}>
            <LogOut size={15}/></button></td>
        </tr>)}</tbody>
      </table></div>}
    <p className="form-caption">A session is addressed by a one-way handle, never by its token.</p>
  </section>;
}

/** Irreversible, so it asks for the password and the workspace name typed exactly. */
export function DeleteWorkspace() {
  const w = useWorkspace();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const phrase = `DELETE ${w.user?.name ?? ''}`;
  return <section className="panel settings-card danger-card">
    <div className="section-heading"><h2>Delete this workspace</h2><Trash2 size={18}/></div>
    <p>Every product, investigation, evidence record, assessment, quote, watch and audit event
      in this workspace is removed permanently. This cannot be undone, and no copy is kept.
      Export your records first if you want them.</p>
    <button className="button danger" onClick={() => { setError(''); setOpen(true); }}>
      <Trash2 size={15}/>Delete workspace…</button>
    <Modal open={open} onOpenChange={setOpen} title="Delete this workspace"
      description="This removes every record permanently. There is no undo and no backup copy.">
      <form className="stack" onSubmit={async event => {
        event.preventDefault(); setBusy(true); setError('');
        const data = new FormData(event.currentTarget);
        try {
          await del('/auth/account', { password: data.get('password'), confirmation: data.get('confirmation') });
          setOpen(false); await w.refresh();
          toast.success('Workspace deleted. Nothing was retained.');
        } catch (problem) { setError((problem as Error).message); } finally { setBusy(false); }
      }}>
        <Notice kind="amber">This deletes the workspace and everything in it, for everyone.</Notice>
        <label>Your password<input name="password" type="password" required minLength={12}
          maxLength={128} autoComplete="current-password"/></label>
        <label>Type <code>{phrase}</code> to confirm
          <input name="confirmation" required autoComplete="off" placeholder={phrase}/></label>
        {error && <div role="alert" className="form-error">{error}</div>}
        <button className="button danger" disabled={busy}>
          {busy ? 'Deleting…' : 'Permanently delete this workspace'}</button>
      </form>
    </Modal>
  </section>;
}

/** The whole account-security group, for the Settings screen. */
export function AccountSecurity() {
  const w = useWorkspace();
  if (w.demo) return <Notice kind="amber">Account security is unavailable in the demo workspace.</Notice>;
  if (!w.user) return <Notice>Sign in to manage your account security.</Notice>;
  return <>
    <EmailVerification/>
    <ChangePassword/>
    <ActiveSessions/>
    <DeleteWorkspace/>
  </>;
}
