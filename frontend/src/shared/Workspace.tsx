import React, { createContext, useContext, useEffect, useState } from 'react';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError, post } from '@/lib/api';
import { stored } from '@/lib/utils';
import type { Assessment, Product, Quote, User, Watch } from '@/types';

type QuoteDraft = Omit<Quote,'id'|'truth_state'|'verification'>;
/** Every list endpoint returns its page plus the total that matched, so a screen can say
 *  how much it is not showing instead of implying the page is everything (action plan T05). */
interface Page { total: number; limit: number; next_cursor: string | null }
const PAGE = 50;
/** Quotes and watches load in one request today; the total tells us when that stops being true. */
const FLAT_PAGE = 200;

interface Store {
  demo: boolean; user: User | null; products: Product[]; watches: Watch[]; decisions: Assessment[]; quotes: Quote[];
  productTotal: number; decisionTotal: number; quoteTotal: number; watchTotal: number;
  productSearch: string; setProductSearch: (term: string)=>void;
  moreProducts: boolean; loadMoreProducts: ()=>void; loadingMoreProducts: boolean;
  moreDecisions: boolean; loadMoreDecisions: ()=>void;
  loading: boolean; error: string | null; authOpen: boolean; setAuthOpen: (open: boolean)=>void;
  enterDemo: ()=>Promise<void>; exitDemo: ()=>void; refresh: ()=>Promise<void>; requireUser: ()=>boolean;
  addDemoProduct: (p: Product)=>void; confirm: (id:string,name:string)=>Promise<Product>;
  watch: (id:string,threshold?:number)=>Promise<void>; unwatch: (id:string)=>Promise<void>;
  saveDecision: (result:Assessment, product:Product, requestKey:string)=>Promise<Assessment>;
  saveQuote: (quote:QuoteDraft)=>Promise<void>;
}
const Context=createContext<Store>(null!);
export const useWorkspace=()=>useContext(Context);
const safeArray = <T,>(key:string): T[] => { const value=stored<unknown>(key,[]); return Array.isArray(value) ? value as T[] : []; };
const query=(params:Record<string,string|number|undefined>)=>Object.entries(params).filter(([,v])=>v!==undefined&&v!=='').map(([k,v])=>`${k}=${encodeURIComponent(String(v))}`).join('&');
export function WorkspaceProvider({children}:{children:React.ReactNode}) {
  const client=useQueryClient();
  const [demo,setDemo]=useState(sessionStorage.getItem('trendsell-mode')==='demo');
  const [authOpen,setAuthOpen]=useState(false);
  const [productSearch,setProductSearch]=useState('');
  const [demoProducts,setDemoProducts]=useState<Product[]>([]);
  const [demoWatches,setDemoWatches]=useState<Watch[]>(()=>safeArray('trendsell-demo-v2-watches'));
  const [demoDecisions,setDemoDecisions]=useState<Assessment[]>(()=>safeArray('trendsell-demo-v2-decisions'));
  const [demoQuotes,setDemoQuotes]=useState<Quote[]>(()=>safeArray('trendsell-demo-v2-quotes'));
  const me=useQuery({queryKey:['me'],queryFn:()=>api<User>('/auth/me'),retry:false,enabled:!demo});
  const user=me.data ?? null;
  const enabled=!!user && !demo;
  // Search is a server parameter, not a filter over a loaded page: a match on the 900th
  // product must be findable, and it is the database that knows about it.
  const products=useInfiniteQuery({
    queryKey:['products',user?.workspace_id,productSearch],
    queryFn:({pageParam})=>api<{products:Product[]}&Page>(`/products?${query({limit:PAGE,search:productSearch,cursor:pageParam})}`),
    initialPageParam:'' as string,
    getNextPageParam:(last:{next_cursor:string|null})=>last.next_cursor ?? undefined,
    enabled});
  const decisions=useInfiniteQuery({
    queryKey:['decisions',user?.workspace_id],
    queryFn:({pageParam})=>api<{decisions:Assessment[]}&Page>(`/decisions?${query({limit:PAGE,cursor:pageParam})}`),
    initialPageParam:'' as string,
    getNextPageParam:(last:{next_cursor:string|null})=>last.next_cursor ?? undefined,
    enabled});
  const watches=useQuery({queryKey:['watches',user?.workspace_id],queryFn:()=>api<{items:Watch[]}&Page>(`/watchlists/default/items?limit=${FLAT_PAGE}`),enabled});
  const quotes=useQuery({queryKey:['quotes',user?.workspace_id],queryFn:()=>api<{quotes:Quote[]}&Page>(`/quotes?limit=${FLAT_PAGE}`),enabled});
  const enterDemo=async()=>{
    const {demoProducts:fixtures}=await import('@/demo');
    const saved=safeArray<Product>('trendsell-demo-v2-products');
    setDemoProducts(saved.length?saved:fixtures);
    setDemo(true); setAuthOpen(false); sessionStorage.setItem('trendsell-mode','demo');
  };
  useEffect(()=>{ if(demo) void enterDemo(); },[]); // only restore an explicitly selected demo
  const exitDemo=()=>{setDemo(false);sessionStorage.removeItem('trendsell-mode');void client.invalidateQueries();};
  useEffect(()=>{if(demo && demoProducts.length) localStorage.setItem('trendsell-demo-v2-products',JSON.stringify(demoProducts));},[demoProducts,demo]);
  useEffect(()=>{if(demo) localStorage.setItem('trendsell-demo-v2-watches',JSON.stringify(demoWatches));},[demoWatches,demo]);
  useEffect(()=>{if(demo) localStorage.setItem('trendsell-demo-v2-decisions',JSON.stringify(demoDecisions));},[demoDecisions,demo]);
  useEffect(()=>{if(demo) localStorage.setItem('trendsell-demo-v2-quotes',JSON.stringify(demoQuotes));},[demoQuotes,demo]);
  const refresh=async()=>{await client.invalidateQueries();};
  const error=!demo ? [me,products,watches,decisions,quotes].map(q=>q.error).find(e=>e && (!(e instanceof ApiError) || e.status!==401))?.message || null : null;
  const term=productSearch.trim().toLowerCase();
  const demoMatches=term?demoProducts.filter(p=>`${p.name} ${p.asin}`.toLowerCase().includes(term)):demoProducts;
  const livePages=products.data?.pages ?? [];
  const liveProducts=livePages.flatMap(p=>p.products);
  const liveDecisions=decisions.data?.pages.flatMap(p=>p.decisions) ?? [];
  const value:Store={demo,user:demo?null:user,
    products:demo?demoMatches:liveProducts,
    watches:demo?demoWatches:watches.data?.items||[],
    decisions:demo?demoDecisions:liveDecisions,
    quotes:demo?demoQuotes:quotes.data?.quotes||[],
    productTotal:demo?demoMatches.length:livePages[0]?.total ?? 0,
    decisionTotal:demo?demoDecisions.length:decisions.data?.pages[0]?.total ?? 0,
    quoteTotal:demo?demoQuotes.length:quotes.data?.total ?? 0,
    watchTotal:demo?demoWatches.length:watches.data?.total ?? 0,
    productSearch,setProductSearch,
    moreProducts:!demo&&!!products.hasNextPage,loadMoreProducts:()=>{void products.fetchNextPage();},loadingMoreProducts:products.isFetchingNextPage,
    moreDecisions:!demo&&!!decisions.hasNextPage,loadMoreDecisions:()=>{void decisions.fetchNextPage();},
    loading:demo?demoProducts.length===0:me.isLoading||(enabled&&products.isLoading),error,authOpen,setAuthOpen,enterDemo,exitDemo,refresh,
    requireUser:()=>{if(demo||user)return true;setAuthOpen(true);return false;},
    addDemoProduct:p=>setDemoProducts(prev=>[p,...prev.filter(x=>x.id!==p.id)]),
    confirm:async(id,name)=>{
      if(demo){const p={...demoProducts.find(p=>p.id===id)!,name,confirmed:true};setDemoProducts(prev=>prev.map(x=>x.id===id?p:x));return p;}
      const p=await post<Product>(`/products/${id}/confirm`,{name});await refresh();return p;
    },
    watch:async(product_id,threshold_pct=15)=>{
      if(demo)setDemoWatches(prev=>[{id:`watch-${product_id}`,product_id,threshold_pct,status:'Demo · monitoring paused',scheduled:false,created_at:new Date().toISOString()},...prev.filter(w=>w.product_id!==product_id)]);
      else {await post('/watchlists/default/items',{product_id,threshold_pct});await refresh();}
    },
    unwatch:async id=>{if(demo)setDemoWatches(prev=>prev.filter(w=>w.id!==id));else{await api(`/watchlists/default/items/${id}`,{method:'DELETE'});await refresh();}},
    // requestKey identifies one logical submission, not one attempt: the caller keeps it
    // across retries so an ambiguous timeout cannot save the assessment twice (T06).
    saveDecision:async(result,product,requestKey)=>{
      if(demo){const saved={...result,id:requestKey,product_id:product.id,product_name:product.name,truth_state:'Demo' as const,created_at:new Date().toISOString()};setDemoDecisions(prev=>[saved,...prev.filter(d=>d.id!==requestKey)]);return saved;}
      const saved=await post<Assessment>('/decisions',{product_id:product.id,inputs:result.inputs},requestKey);await refresh();return saved;
    },
    saveQuote:async quote=>{if(demo)setDemoQuotes(prev=>[{...quote,id:crypto.randomUUID(),truth_state:'Demo',verification:'Unverified'},...prev]);else{await post('/quotes',quote);await refresh();}},
  };
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
