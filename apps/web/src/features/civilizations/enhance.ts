// Enhance the generated HTML. There is no second client-side card renderer and
// no dependency on the simulator, API, or complete media/data catalog.
let active: HTMLElement | null = null;
let pinned = false;
let controller: AbortController | null = null;
let closeTimer: ReturnType<typeof setTimeout> | undefined;
const main = () => document.querySelector<HTMLElement>('[data-civ-page]');

function positionTooltip() {
  if (!active || window.innerWidth <= 600) return;
  const tooltip = active.querySelector<HTMLElement>('.unit-tooltip')!;
  const card = active.getBoundingClientRect();
  const margin = 12;
  const nav = document.querySelector('.site-nav')?.getBoundingClientRect().bottom ?? 0;
  const top = Math.max(nav + margin, Math.min(card.top, innerHeight - tooltip.offsetHeight - margin));
  const right = card.right + margin;
  const left = right + tooltip.offsetWidth <= innerWidth - margin ? right : card.left - tooltip.offsetWidth - margin;
  tooltip.style.top = `${top}px`;
  tooltip.style.left = `${Math.max(margin, Math.min(left, innerWidth - tooltip.offsetWidth - margin))}px`;
}

function closeTooltip() {
  clearTimeout(closeTimer);
  if (active) {
    const tooltip = active.querySelector<HTMLElement>('.unit-tooltip')!;
    tooltip.classList.remove('open');
    const image = tooltip.querySelector<HTMLImageElement>('[data-deferred-src]');
    if (image?.getAttribute('src')) image.src = image.dataset.deferredSrc!;
    active.classList.remove('tooltip-pinned');
    main()?.querySelector('.building-groups')?.classList.remove('tooltip-focus');
  }
  active = null;
  pinned = false;
}

function openTooltip(card: HTMLElement, pin = false) {
  clearTimeout(closeTimer);
  if (active !== card) closeTooltip();
  active = card;
  pinned = pin;
  const tooltip = card.querySelector<HTMLElement>('.unit-tooltip')!;
  tooltip.classList.add('open');
  card.classList.toggle('tooltip-pinned', pin);
  main()?.querySelector('.building-groups')?.classList.toggle('tooltip-focus', pin);
  const image = tooltip.querySelector<HTMLImageElement>('[data-deferred-src]');
  if (image) image.src = image.dataset.animationUrl || image.dataset.deferredSrc!;
  positionTooltip();
}

function enable() {
  main()?.setAttribute('data-enhanced', '');
  // WebKit touch synthesizes clicks for an element with a direct click
  // listener. A listener only on document leaves these existing div cards
  // untappable on some touch browsers.
  main()?.querySelectorAll<HTMLElement>('.unit-card').forEach(card => {
    card.addEventListener('click', event => {
      if (!(event.target instanceof Element)) return;
      event.stopPropagation();
      if (event.target.closest('.tooltip-close')) {event.preventDefault(); closeTooltip(); return;}
      if (event.target.closest('.unit-tooltip') && active === card && pinned) return;
      if (active === card && pinned) closeTooltip(); else openTooltip(card, true);
    });
  });
}
enable();

document.addEventListener('mouseover', event => {
  if (!matchMedia('(hover:hover)').matches || pinned || !(event.target instanceof Element)) return;
  const card = event.target.closest<HTMLElement>('.unit-card');
  if (card && !card.contains((event as MouseEvent).relatedTarget as Node | null)) openTooltip(card);
});
document.addEventListener('mouseout', event => {
  if (pinned || !(event.target instanceof Element)) return;
  const card = event.target.closest('.unit-card');
  if (card && active === card && !card.contains((event as MouseEvent).relatedTarget as Node | null)) {
    closeTimer = setTimeout(closeTooltip, 140);
  }
});
document.addEventListener('click', event => {
  if (!(event.target instanceof Element)) return;
  if (event.target.closest('.tooltip-close')) {event.preventDefault(); closeTooltip(); return;}
  const card = event.target.closest<HTMLElement>('.unit-card');
  if (card) return;
  closeTooltip();
  const link = event.target.closest<HTMLAnchorElement>('a[data-civ-link]');
  const mouse = event as MouseEvent;
  if (!link || mouse.button !== 0 || mouse.ctrlKey || mouse.metaKey || mouse.shiftKey || mouse.altKey) return;
  const url = new URL(link.href);
  if (url.origin !== location.origin) return;
  event.preventDefault();
  if (url.pathname === location.pathname) {
    // Reselecting the current civilization also cancels a slower selection.
    controller?.abort();
    main()?.removeAttribute('aria-busy');
    main()?.scrollIntoView({block: 'start', behavior: 'smooth'});
    return;
  }
  // Existing campaign/query parameters must survive an in-place selection.
  url.search = location.search;
  navigate(url, true);
});
document.addEventListener('keydown', event => {if (event.key === 'Escape') closeTooltip();});
window.addEventListener('resize', positionTooltip);
window.addEventListener('scroll', positionTooltip, {passive: true});
window.addEventListener('popstate', () => {
  if (location.pathname === '/civilizations' || location.pathname.startsWith('/civilizations/')) navigate(new URL(location.href), false);
});

async function navigate(url: URL, push: boolean) {
  controller?.abort();
  controller = new AbortController();
  const pending = controller;
  const current = main();
  current?.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(url, {signal: pending.signal, headers: {'Accept': 'text/html'}});
    if (!response.ok) throw new Error('Page unavailable');
    const html = new DOMParser().parseFromString(await response.text(), 'text/html');
    const next = html.querySelector<HTMLElement>('[data-civ-page]');
    if (!next || pending.signal.aborted) throw new Error('Page unavailable');
    closeTooltip();
    // These are our own static pages; scripts remain inert after DOMParser.
    next.querySelectorAll('script').forEach(script => script.remove());
    current?.replaceWith(document.importNode(next, true));
    document.title = html.title;
    for (const selector of ['meta[name="description"]', 'link[rel="canonical"]',
      'meta[property^="og:"]', 'meta[name^="twitter:"]', 'script[type="application/ld+json"]']) {
      document.head.querySelectorAll(selector).forEach(node => node.remove());
      html.head.querySelectorAll(selector).forEach(node => document.head.append(document.importNode(node, true)));
    }
    enable();
    if (push) {history.pushState({}, '', url); main()?.scrollIntoView({block: 'start'});}
  } catch (error) {
    if (!pending.signal.aborted) location.assign(url);
  } finally {
    if (controller === pending) main()?.removeAttribute('aria-busy');
  }
}
