import type {APIRoute} from 'astro';
import pages from '../generated/remaining-pages.json';
export const GET:APIRoute=()=>new Response(pages.sitemap,{headers:{'Content-Type':'application/xml; charset=utf-8'}});
