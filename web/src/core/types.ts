// 1:1 port of qviability/core/project.py data model. Field names are kept in
// snake_case so the serialized session JSON round-trips with the desktop app.

export const SCHEMA_VERSION = 2;
export const SESSION_SUFFIX = ".qviability.json";
export const DEFAULT_GREEN_BG_RADIUS = 75;
export const DEFAULT_RED_BG_RADIUS = 5;

export const Channel = {
  GREEN: "Green",
  RED: "Red",
} as const;
export type ChannelName = (typeof Channel)[keyof typeof Channel];

/** A raw single-channel image as it lives in memory (mirrors a numpy array). */
export interface RawImage {
  data: Uint8Array | Uint16Array;
  width: number;
  height: number;
}

export interface Measurement {
  threshold: number;
  positive_pixels: number;
  total_pixels: number;
  positive_area_pct: number;
  mean_intensity_positive: number;
  integrated_intensity: number;
  method: string;
}

/** [x, y, w, h] exclusion rectangle. */
export type Rect = [number, number, number, number];

export interface ImageEntry {
  path: string;
  display_name: string;
  channel: string;
  bit_depth: number;
  max_value: number;
  width: number;
  height: number;
  threshold: number | null;
  auto_method: string;
  brightness: number;
  contrast: number;
  done: boolean;
  missing: boolean;
  exclusions: Rect[];
  measurement: Measurement | null;
}

export interface Project {
  green_folder: string | null;
  red_folder: string | null;
  images: ImageEntry[];
  current_index: number;
  fine_step: number;
  coarse_step: number;
  output_folder: string | null;
  subtract_background: boolean;
  green_bg_radius: number;
  red_bg_radius: number;
  schema_version: number;
}

export function makeImageEntry(
  path: string,
  display_name: string,
  channel: string,
): ImageEntry {
  return {
    path,
    display_name,
    channel,
    bit_depth: 8,
    max_value: 255,
    width: 0,
    height: 0,
    threshold: null,
    auto_method: "MaxEntropy",
    brightness: 0.0,
    contrast: 1.0,
    done: false,
    missing: false,
    exclusions: [],
    measurement: null,
  };
}

export function radiusFor(project: Project, channel: string): number {
  return channel === Channel.RED
    ? project.red_bg_radius
    : project.green_bg_radius;
}
