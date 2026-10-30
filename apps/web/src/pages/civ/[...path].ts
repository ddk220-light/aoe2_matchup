import type {APIRoute} from 'astro';
import {civilizationRedirect} from '../../lib/civilization-redirect';
export const prerender = false;
export const GET: APIRoute = ({url}) => civilizationRedirect(url, true);
