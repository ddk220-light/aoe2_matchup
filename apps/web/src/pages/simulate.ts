import type {APIRoute} from 'astro';
export const prerender=false;
// Preserve the legacy GET/HEAD query contract without redirecting POST/OPTIONS.
export const GET:APIRoute=({url})=>new Response(null,{status:301,headers:{Location:'/'+url.search}});
