import { defineConfig } from 'astro/config';
import vercel from '@astrojs/vercel';

export default defineConfig({
  site: 'https://aoe2matchup.com',
  output: 'static',
  trailingSlash: 'never',
  devToolbar: { enabled: false },
  adapter: vercel({
    maxDuration: 60,
    webAnalytics: { enabled: true },
  }),
});
