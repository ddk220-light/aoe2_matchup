import type {APIRoute} from 'astro';
import {isPublicHost, robotsPolicy} from '../lib/site-policy.mjs';
export const prerender = false;
export const GET: APIRoute = ({url}) => new Response(robotsPolicy(url.hostname), {
  headers: {'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store',
    ...(!isPublicHost(url.hostname) ? {'X-Robots-Tag':'noindex, nofollow'} : {})},
});
