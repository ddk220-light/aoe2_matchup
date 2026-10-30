/** Pure shared resolver. Clients receive only media used by their feature. */
export interface MediaAsset {
  url: string; sha256: string; bytes: number; content_type: string;
  width: number; height: number; frames: number; duration_ms: number[];
  transparency: boolean;
}
export type MediaAliases = Record<string, MediaAsset>;
export function resolveMedia(alias: string, aliases: MediaAliases): MediaAsset {
  const asset = aliases[alias];
  if (!asset) throw new Error(`Media is not published: ${alias}`);
  return asset;
}
