import type {APIRoute} from 'astro';
import projection from '../../generated/ranking-pages.json';
export const prerender = false;
export const GET:APIRoute = ({params,url}) => {
  const slug = params.path || '';
  const lower = slug.toLowerCase();
  if(slug !== lower && Object.hasOwn(projection.guides,lower)) {
    return new Response(null,{status:301,headers:{Location:`/units/${lower}${url.search}`}});
  }
  return new Response('Not found',{status:404,headers:{'Cache-Control':'no-store'}});
};
