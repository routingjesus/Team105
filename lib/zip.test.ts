import { afterEach, describe, expect, it, vi } from "vitest";
import { unzipSync } from "fflate";
import { base64ToUint8Array } from "./api";
import {
  buildDatasetZip,
  DATASET_ZIP_FILENAME,
  downloadDatasetZip,
  ZIP_MIME,
  type DatasetZipEntry,
} from "./zip";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

// Text fixtures plus a full 0–255 byte-value fixture standing in for the
// binary xlsx payload, so decode corruption would be caught.
const truckBytes = new TextEncoder().encode("TruckID\tDepot\nT1\tD1\n");
const xlsxBytes = new Uint8Array(256).map((_, i) => i);
const configBytes = new TextEncoder().encode('<?xml version="1.0"?><DRProject />');

const entries: DatasetZipEntry[] = [
  { filename: "fleet.truck", base64: toBase64(truckBytes) },
  { filename: "stops.xlsx", base64: toBase64(xlsxBytes), alreadyCompressed: true },
  { filename: "DRProject.config", base64: toBase64(configBytes) },
];

describe("buildDatasetZip", () => {
  it("packages exactly the given entries at the archive root with byte-identical content", () => {
    const unzipped = unzipSync(buildDatasetZip(entries));

    expect(Object.keys(unzipped).sort()).toEqual(["DRProject.config", "fleet.truck", "stops.xlsx"]);
    // Compare plain arrays: typed-array deep-equality is sensitive to the
    // underlying buffer view, not just the bytes.
    expect(Array.from(unzipped["fleet.truck"])).toEqual(Array.from(truckBytes));
    expect(Array.from(unzipped["stops.xlsx"])).toEqual(Array.from(xlsxBytes));
    expect(Array.from(unzipped["DRProject.config"])).toEqual(
      Array.from(base64ToUint8Array(entries[2].base64)),
    );
  });

  it("round-trips arbitrary binary bytes without corruption", () => {
    const unzipped = unzipSync(buildDatasetZip(entries));
    expect(Array.from(unzipped["stops.xlsx"])).toEqual(
      Array.from({ length: 256 }, (_, i) => i),
    );
  });
});

describe("downloadDatasetZip", () => {
  it("triggers a single zip download named dataset.zip", () => {
    const createSpy = vi.fn((_blob: Blob | MediaSource) => "blob:mock");
    const revokeSpy = vi.fn();
    vi.stubGlobal("URL", { ...URL, createObjectURL: createSpy, revokeObjectURL: revokeSpy });
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);
    let downloadName: string | undefined;
    clickSpy.mockImplementation(function (this: HTMLAnchorElement) {
      downloadName = this.download;
    });

    downloadDatasetZip(entries);

    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(downloadName).toBe(DATASET_ZIP_FILENAME);
    expect(createSpy).toHaveBeenCalledTimes(1);
    const blob = createSpy.mock.calls[0][0] as Blob;
    expect(blob.type).toBe(ZIP_MIME);
    expect(revokeSpy).toHaveBeenCalledTimes(1);
  });
});
