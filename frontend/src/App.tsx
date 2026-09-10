import React, { useEffect, useState } from 'react';
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { Activity, ArrowDownUp, ArrowRight, ArrowUpRight, Bell, ChevronDown, Compass, Factory, FlaskConical, Home, LogIn, Menu, Moon, PanelLeftClose, ScanLine, Search, Settings as SettingsIcon, ShieldCheck, Sun, TrendingUp, X } from 'lucide-react';
import { Toaster, toast } from 'sonner';
import { useQuery } from '@tanstack/react-query';
import { WorkspaceProvider, useWorkspace } from '@/shared/Workspace';
import { Loading, Modal, Notice } from '@/shared/UI';
import { api, post } from '@/lib/api';
import type { User } from '@/types';

/** Screens load on the route that needs them.
 *
 *  The charting library is imported by the product screens alone, and the demo fixtures
 *  by nobody until the demo is entered, but a single bundle made every visitor download
 *  both before Today could paint. Each route is its own chunk instead. `CaptureInput`
 *  stays eagerly imported because the landing screen renders it immediately.
 */
const Today = React.lazy(() => import('@/features/Today'));
const Xray = React.lazy(() => import('@/features/Xray'));
const DecisionRoom = React.lazy(() => import('@/features/DecisionRoom'));
const named = <T extends string>(load: () => Promise<Record<string, unknown>>, name: T) =>
  React.lazy(async () => ({ default: (await load())[name] as React.ComponentType }));
const Discover = named(() => import('@/features/Products'), 'Discover');
const ProductView = named(() => import('@/features/Products'), 'ProductView');
const MarketGaps = named(() => import('@/features/Products'), 'MarketGaps');
const DataHealth = named(() => import('@/features/Operations'), 'DataHealth');
const Settings = named(() => import('@/features/Operations'), 'Settings');
const Suppliers = named(() => import('@/features/Operations'), 'Suppliers');
const Watchtower = named(() => import('@/features/Operations'), 'Watchtower');

const navigation=[{name:'Today',path:'/',icon:Home},{name:'Discover',path:'/discover',icon:Compass},{name:'Product X-Ray',path:'/xray',icon:ScanLine},{name:'Market Gaps',path:'/market-gaps',icon:ArrowDownUp},{name:'Decision Room',path:'/decisions',icon:FlaskConical},{name:'Watchlist',path:'/watchtower',icon:Bell},{name:'Suppliers',path:'/suppliers',icon:Factory}];
/** Ask for a reset link, then redeem the token it carries.
 *
 *  Both steps live here because a locked-out person cannot reach Settings. The response
 *  to a request is deliberately identical whether or not the account exists, so this
 *  screen must not imply otherwise. With no mail transport configured the deployment
 *  cannot deliver the message, and the panel says so rather than pretending one is on
 *  its way — the token box still works for a token an operator issued. */
function PasswordRecovery({onDone}:{onDone:()=>void}){
 const [stage,setStage]=useState<'request'|'redeem'>('request');
 const [busy,setBusy]=useState(false);const [error,setError]=useState('');
 const {data:config}=useQuery({queryKey:['config'],queryFn:()=>api<{mail_delivery_configured:boolean}>('/config'),retry:false});
 if(stage==='request')return <form className="stack" onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');
  const data=new FormData(e.currentTarget);
  try{const result=await post<{delivery_configured:boolean}>('/auth/recovery/request',{email:data.get('email')});setStage('redeem');
   toast.success(result.delivery_configured
    ? 'If that address has a workspace and delivery succeeds, reset instructions will arrive.'
    : 'Request accepted. No message was sent; ask an operator for a reset token.');}
  catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>
  <p className="form-caption">{config?.mail_delivery_configured
   ? 'Enter your address and we will try to send a reset link.'
   : 'Enter your address to start recovery, then ask an operator for the reset token.'} The answer is
   the same either way — it never reveals whether an account exists.</p>
  {config&&!config.mail_delivery_configured&&<Notice kind="amber">This deployment has no mail
   transport configured, so no message can actually be delivered. Ask an operator to issue a
   reset token, then enter it on the next step.</Notice>}
  <label>Email address<input name="email" type="email" required autoComplete="email" placeholder="you@company.com"/></label>
  {error&&<div role="alert" className="form-error">{error}</div>}
  <button className="button primary full" disabled={busy}>{busy?'Please wait…':config?.mail_delivery_configured?'Send a reset link':'Continue to token'}<ArrowRight size={16}/></button>
  <button className="text-button centered" type="button" onClick={onDone}>Back to sign in</button>
 </form>;
 return <form className="stack" onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');
  const data=new FormData(e.currentTarget);
  try{await post('/auth/recovery/reset',{token:String(data.get('token')).trim(),password:data.get('password')});
   toast.success('Password reset. Every session on the account was ended — sign in again.');onDone();}
  catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>
  <p className="form-caption">Enter the token from your reset message and choose a new password.
   Redeeming it ends every session on the account, including any an intruder holds.</p>
  <label>Reset token<input name="token" required minLength={20} maxLength={200} autoComplete="off" placeholder="Paste the token from your message"/></label>
  <label>New password<input name="password" type="password" required minLength={12} maxLength={128} autoComplete="new-password" placeholder="At least 12 characters"/></label>
  {error&&<div role="alert" className="form-error">{error}</div>}
  <button className="button primary full" disabled={busy}>{busy?'Please wait…':'Set a new password'}<ArrowRight size={16}/></button>
  <button className="text-button centered" type="button" onClick={()=>{setStage('request');setError('');}}>Ask for another link</button>
 </form>;
}
function AuthDialog(){
 const {authOpen,setAuthOpen,refresh}=useWorkspace();const [register,setRegister]=useState(false);const [recovering,setRecovering]=useState(false);const [busy,setBusy]=useState(false);const [error,setError]=useState('');
 const {data:config}=useQuery({queryKey:['config'],queryFn:()=>api<{allow_registration:boolean}>('/config'),retry:false,enabled:authOpen});
 const close=(open:boolean)=>{setAuthOpen(open);if(!open){setRecovering(false);setError('');}};
 return <Modal open={authOpen} onOpenChange={close} title={recovering?'Reset your password':register?'Create your workspace':'Welcome to TrendSell'} description={recovering?'Recover access to your workspace.':'Keep your investigations, decisions, and supplier quotes together.'}>
 {recovering?<PasswordRecovery onDone={()=>{setRecovering(false);setError('');}}/>:<form className="stack" onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');const data=new FormData(e.currentTarget);try{await post<User>(`/auth/${register?'register':'login'}`,{email:data.get('email'),password:data.get('password'),name:data.get('name')||'My workspace'});await refresh();setAuthOpen(false);toast.success(register?'Workspace created':'Welcome back');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>
 {register&&<label>Workspace name<input name="name" required minLength={1} maxLength={80} autoComplete="organization" placeholder="Your business"/></label>}
 <label>Email address<input name="email" type="email" required autoComplete="email" placeholder="you@company.com"/></label><label>Password<input name="password" type="password" required minLength={12} maxLength={128} autoComplete={register?'new-password':'current-password'} placeholder="At least 12 characters"/></label>
 {error&&<div role="alert" className="form-error">{error}</div>}<button className="button primary full" disabled={busy}>{busy?'Please wait…':register?'Create workspace':'Sign in'}<ArrowRight size={16}/></button>
 {!register&&<button className="text-button centered" type="button" onClick={()=>{setRecovering(true);setError('');}}>Forgot your password?</button>}
 {config?.allow_registration&&<button className="text-button centered" type="button" onClick={()=>{setRegister(!register);setError('');}}>{register?'Already have an account? Sign in':'New here? Create a workspace'}</button>}
 </form>}</Modal>;
}
function Shell(){
 const w=useWorkspace();const location=useLocation();const navigate=useNavigate();const [menu,setMenu]=useState(false);const [search,setSearch]=useState('');
 const [theme,setTheme]=useState(localStorage.getItem('trendsell-theme-v2')||'dark');
 useEffect(()=>{document.documentElement.className=theme;localStorage.setItem('trendsell-theme-v2',theme);},[theme]);
 useEffect(()=>{setMenu(false);window.scrollTo(0,0);},[location.pathname]);
 useEffect(()=>{const key=(e:KeyboardEvent)=>{if(e.key==='/'&& !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)){e.preventDefault();document.getElementById('workspace-search')?.focus();}};document.addEventListener('keydown',key);return()=>document.removeEventListener('keydown',key);},[]);
 const nav=<><div className="nav-label">WORKSPACE</div><nav aria-label="Main navigation">{navigation.map(({name,path,icon:Icon})=><NavLink key={path} to={path} end={path==='/'} className={({isActive})=>`nav-item ${isActive?'active':''}`} onClick={()=>setMenu(false)}><Icon size={18}/><span>{name}</span>{path==='/xray'&&<span className="nav-new">NEW</span>}{path==='/watchtower'&&w.watches.length>0&&<span className="nav-count">{w.watches.length}</span>}</NavLink>)}</nav><div className="nav-bottom"><div className="nav-label">MANAGE</div><NavLink to="/data-health" className={({isActive})=>`nav-item ${isActive?'active':''}`}><Activity size={18}/><span>Data Health</span><span className="health-dot"/></NavLink><NavLink to="/settings" className={({isActive})=>`nav-item ${isActive?'active':''}`}><SettingsIcon size={18}/><span>Settings</span></NavLink></div></>;
 return <div className="app-shell"><a href="#main-content" className="skip-link">Skip to content</a><aside className="sidebar"><Link to="/" className="brand"><span className="brand-mark"><TrendingUp size={23} strokeWidth={2.6}/></span><span>TrendSell<span className="brand-dot">.</span></span></Link><button className="workspace-switch" onClick={()=>w.user||w.demo?navigate('/settings'):w.setAuthOpen(true)}><span className="workspace-avatar">{w.demo?'D':(w.user?.name||'My')[0].toUpperCase()}</span><span>{w.demo?'Demo workspace':w.user?.name||'My workspace'}<small>{w.demo?'Explore the experience':'China → Nigeria pilot'}</small></span><ChevronDown size={14}/></button>{nav}<div className="sidebar-note"><ShieldCheck size={20}/><h4>Evidence over guesswork.</h4><p>Every good decision starts with knowing what you know.</p><Link to="/data-health">View data coverage<ArrowUpRight size={13}/></Link></div><button className="profile" onClick={()=>w.user||w.demo?navigate('/settings'):w.setAuthOpen(true)}><span className="profile-avatar">{w.demo?'DE':w.user?w.user.name.slice(0,2).toUpperCase():<LogIn size={18}/>}</span><span>{w.demo?'Demo explorer':w.user?.name||'Your next opportunity'}<small>{w.demo?'Sample data only':w.user?'Workspace owner':'Sign in to get started'}</small></span><ChevronDown size={14}/></button></aside>
 <div className="main-shell"><header className="topbar"><button className="icon-button mobile-menu" onClick={()=>setMenu(true)} aria-label="Open navigation"><Menu size={21}/></button><div className="breadcrumb">Workspace<ChevronRightIcon/><span>{location.pathname.startsWith('/products/')?'Product investigation':navigation.find(n=>n.path===location.pathname)?.name|| (location.pathname==='/data-health'?'Data Health':'Settings')}</span></div><form className="global-search" onSubmit={e=>{e.preventDefault();navigate(`/discover?q=${encodeURIComponent(search)}`);}}><Search size={16}/><input id="workspace-search" aria-label="Search investigations" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search your workspace…"/><kbd>/</kbd></form><div className="topbar-actions"><Link to="/settings" className="market-pill"><span className="nigeria-flag"/>Nigeria<ChevronDown size={13}/></Link><span className="topbar-divider"/><button className="icon-button" aria-label={`Switch to ${theme==='dark'?'light':'dark'} mode`} onClick={()=>setTheme(theme==='dark'?'light':'dark')}>{theme==='dark'?<Sun size={18}/>:<Moon size={18}/>}</button><Link to="/watchtower" className="icon-button" aria-label="Open your watchlist"><Bell size={18}/></Link></div></header>
 {w.demo?<div className="mode-banner"><FlaskConical size={14}/><strong>DEMO WORKSPACE</strong><span>Synthetic examples. No live market data or real investment recommendations.</span><button onClick={w.exitDemo}>Exit demo<X size={13}/></button></div>:<div className="pilot-banner"><span className="small-dot"/>PILOT WORKSPACE<span className="pilot-banner-detail">A focused corridor. A clearer decision.</span><button onClick={()=>void w.enterDemo()}>Explore demo<ArrowUpRight size={13}/></button></div>}
 <main id="main-content" tabIndex={-1}>{w.error&&<div className="connection-error"><Notice kind="amber">{w.error} <button className="text-button" onClick={()=>void w.refresh()}>Retry connection</button></Notice></div>}<React.Suspense fallback={<Loading/>}><Routes><Route path="/" element={<Today/>}/><Route path="/discover" element={<Discover/>}/><Route path="/xray" element={<Xray/>}/><Route path="/products/:id" element={<ProductView/>}/><Route path="/market-gaps" element={<MarketGaps/>}/><Route path="/decisions" element={<DecisionRoom/>}/><Route path="/watchtower" element={<Watchtower/>}/><Route path="/suppliers" element={<Suppliers/>}/><Route path="/data-health" element={<DataHealth/>}/><Route path="/settings" element={<Settings/>}/><Route path="/products" element={<Navigate to="/discover" replace/>}/><Route path="/research" element={<Navigate to="/xray" replace/>}/><Route path="/watchlist" element={<Navigate to="/watchtower" replace/>}/><Route path="*" element={<div className="not-found"><h1>Let’s get you back on track.</h1><p>This page has moved in the new TrendSell workspace.</p><Link to="/" className="button primary">Back to Today<ArrowRight size={16}/></Link></div>}/></Routes></React.Suspense></main><footer className="app-footer"><span><ShieldCheck size={13}/>Built on evidence. Made for better decisions.</span><span>TrendSell · China → Nigeria pilot</span></footer></div>
 <Modal open={menu} onOpenChange={setMenu} title="TrendSell" description="Your opportunity workspace" drawer><div className="mobile-nav">{nav}</div></Modal><AuthDialog/><Toaster theme={theme==='dark'?'dark':'light'} position="bottom-right" closeButton/>
 </div>;
}
function ChevronRightIcon(){return <span className="breadcrumb-divider">/</span>;}
export default function App(){return <BrowserRouter><WorkspaceProvider><Shell/></WorkspaceProvider></BrowserRouter>;}
