import { zipSync, type Zippable } from "fflate";
import { base64ToUint8Array, downloadBlob } from "./api";

export const ZIP_MIME = "application/zip";
export const DATASET_ZIP_FILENAME = "dataset.zip";

export interface DatasetZipEntry {
  filename: string;
  base64: string;
  /**
   * Mark pre-compressed formats (e.g. xlsx) so the entry is stored (`level: 0`)
   * instead of re-deflated, per the fflate recommendation.
   */
  alreadyCompressed?: boolean;
}

/**
 * Build a flat zip archive (all entries at the archive root) from base64 file
 * payloads. Entry bytes are the decoded payloads unchanged, so each extracted
 * file is byte-identical to its individual download.
 */
export function buildDatasetZip(entries: DatasetZipEntry[]): Uint8Array<ArrayBuffer> {
  const files: Zippable = {};
  for (const entry of entries) {
    files[entry.filename] = [
      base64ToUint8Array(entry.base64),
      entry.alreadyCompressed ? { level: 0 } : {},
    ];
  }
  // fflate's types predate generic Uint8Array; zipSync allocates a fresh buffer.
  return zipSync(files) as Uint8Array<ArrayBuffer>;
}

/** Zip the given files and trigger a browser download (single user gesture, popup-safe). */
export function downloadDatasetZip(entries: DatasetZipEntry[]): void {
  const blob = new Blob([buildDatasetZip(entries)], { type: ZIP_MIME });
  downloadBlob(blob, DATASET_ZIP_FILENAME);
}
