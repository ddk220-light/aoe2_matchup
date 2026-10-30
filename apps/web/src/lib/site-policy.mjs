export const PUBLIC_ORIGIN = 'https://aoe2matchup.com';
export const isPublicHost = hostname => ['aoe2matchup.com', 'www.aoe2matchup.com'].includes(hostname);

export function robotsPolicy(hostname) {
    return isPublicHost(hostname)
        ? `User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /migration-review/\nSitemap: ${PUBLIC_ORIGIN}/sitemap.xml\n`
        : 'User-agent: *\nDisallow: /\n';
}
