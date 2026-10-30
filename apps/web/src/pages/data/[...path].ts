import type {APIRoute} from 'astro';
export const prerender=false;
export const GET:APIRoute=()=>new Response('Data version not found. Reload the page.',{
  status:404,headers:{'Cache-Control':'no-store'}});
