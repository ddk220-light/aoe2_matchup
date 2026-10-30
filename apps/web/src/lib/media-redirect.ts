import media from '../generated/media-manifest.json';
export function mediaRedirect(alias:string):Response {
  const asset=media.aliases[alias as keyof typeof media.aliases];
  if (!asset) return new Response('Media not found',{status:404,headers:{'Cache-Control':'no-store'}});
  return new Response(null,{status:302,headers:{Location:asset.url,'Cache-Control':'public, max-age=300'}});
}
