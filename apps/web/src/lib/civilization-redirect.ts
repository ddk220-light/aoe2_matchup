// Only noncanonical URLs reach these endpoints. Canonical pages remain static.
export function civilizationRedirect(url: URL, legacy: boolean) {
  const prefix = legacy ? '/civ' : '/civilizations';
  let name: string;
  try {name = decodeURIComponent(url.pathname.slice(prefix.length).replace(/^\//, '').replace(/\/$/, ''));}
  catch {return missing();}
  if (!name) return redirect('/civilizations' + url.search);
  if (!/^[a-z]+$/i.test(name)) return missing();
  const slug = name.toLowerCase();
  if (legacy || name !== slug) return redirect('/civilizations/' + slug + url.search);
  return missing();
}
function redirect(location: string) {
  return new Response(null, {status: 301, headers: {Location: location}});
}
function missing() {
  return new Response('Not Found', {status: 404, headers: {
    'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex',
  }});
}
