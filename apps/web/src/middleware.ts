import {defineMiddleware} from 'astro:middleware';
import {isPublicHost} from './lib/site-policy.mjs';
// Static files already reject writes on Vercel. Keep dynamic Astro page families
// consistent with the original Flask GET/HEAD/OPTIONS contract too.
export const onRequest=defineMiddleware(async (context,next)=>{
 const path=context.url.pathname;
 const page=path==='/'||['/about','/matchups','/matchup-advisor','/patches','/civilizations','/units','/civ','/simulate','/replay','/sitemap.xml','/robots.txt'].includes(path)
  ||/^\/(units|civilizations|civ)\/[^/]+$/.test(path)
  ||/^\/patches\/[^/]+(?:\/[^/]+\/.+)?$/.test(path)
  ||/^\/vs\/[^/]+\/[^/]+\/[^/]+\/[^/]+$/.test(path)
  ||/^\/(static|assets|v3-runtime)\/.+$/.test(path);
 let response;
 if(page&&!['GET','HEAD'].includes(context.request.method)){
  const headers={'Allow':'GET, HEAD, OPTIONS','Cache-Control':'no-store'};
  response = new Response(null,{status:context.request.method==='OPTIONS'?200:405,headers});
 } else response = await next();
 if(response.status>=400) response.headers.set('Cache-Control','no-store');
 const {url}=context;
 if(!isPublicHost(url.hostname)||url.pathname.startsWith('/migration-review/')) {
  response.headers.set('X-Robots-Tag','noindex, nofollow');
 }
 return response;
});
