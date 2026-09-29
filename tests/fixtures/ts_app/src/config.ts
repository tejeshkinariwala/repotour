/**
 * Runtime settings for the Acme storefront.
 * Read once at startup.
 */
export const API_URL = "https://api.acme.example";
export const MAX_RETRIES = 3;
export const lowercaseValue = 5;

export interface Settings {
  url: string;
  retries: number;
}

export type Mode = "dev" | "prod";

export enum Level {
  Low,
  High,
}

export default function loadSettings(): Settings {
  return { url: API_URL, retries: MAX_RETRIES };
}
