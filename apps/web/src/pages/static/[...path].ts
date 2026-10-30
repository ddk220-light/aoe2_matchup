import type {APIRoute} from 'astro';
import {mediaRedirect} from '../../lib/media-redirect';
export const prerender=false;
export const GET:APIRoute=({params})=>mediaRedirect('/static/'+(params.path??''));
