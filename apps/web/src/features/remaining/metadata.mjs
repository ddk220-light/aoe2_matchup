// Keep all existing metadata except the page-specific strings the legacy route varies.
export function frameFor(frame,title,description,canonical,structured){
 const meta=frame.meta.map(m=>m.name==='description'||m.property==='og:description'||m.name==='twitter:description'?{...m,content:description}:m.property==='og:title'||m.name==='twitter:title'?{...m,content:title}:m.property==='og:url'?{...m,content:canonical}:m);
 return {...frame,title,meta,links:frame.links.map(l=>l.rel==='canonical'?{...l,href:canonical}:l),structured:structured.map(x=>JSON.stringify(x).replaceAll('<','\\u003c'))};
}
