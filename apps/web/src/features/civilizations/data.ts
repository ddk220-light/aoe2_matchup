import projection from '../../generated/civilization-pages.json';

export interface Image {url: string; width: number; height: number;}
export interface Unit {
  unit_name: string; line_slug: string; tier?: string | null; is_unique: boolean;
  score?: number | null; stats?: Record<string, number | boolean>;
  stat_baseline?: Record<string, number>; bonus_abilities?: string[];
  special_effects?: string[]; missing_techs?: string[];
  media: Image | null; sprite: boolean; animation_url: string | null;
}
export interface Civilization {
  name: string; slug: string; emblem: Image; strategy: string;
  groups: Record<string, Unit[]>; title: string;
  meta: Record<string, string>[]; links: Record<string, string>[]; structured: string[];
}
export const pages = projection.pages as unknown as Record<string, Civilization>;
export const roster = projection.roster;
export const frame = projection.frame;
export const tiers = projection.tiers as Record<string, {label: string; hint: string}>;
export const lines = projection.lines as Record<string, string>;
export const buildings = [
  ['barracks', 'Barracks'], ['archery_range', 'Archery Range'], ['stable', 'Stable'],
  ['castle', 'Castle'], ['siege_workshop', 'Siege Workshop'], ['dock', 'Dock'],
];
export function formatStat(value: number, suffix = '') {
  return (Math.abs(value - Math.round(value)) < 0.05 ? String(Math.round(value)) : value.toFixed(1)) + suffix;
}
