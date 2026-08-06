import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DatasetWizard } from "./dataset-wizard";

const truckResponse = {
  truck_row_count: 70,
  weeks: 2,
  territory_count: 5,
  depot_count: 1,
  depots: [
    { address: "1 Warehouse Way", city: "Salt Lake City", state: "UT", zip: "84101", truck_count: 5 },
  ],
  volume_names: [{ name: "Cases", capacity: 2000 }],
  seed: 0,
  filename: "fleet.truck",
  truck_file_base64: "AAAA",
};

const stopResponse = {
  candidate_count: 100,
  selected_stop_count: 20,
  output_row_count: 20,
  seed: 0,
  filename: "stops.xlsx",
  stop_file_base64: "AAAA",
};

const drprojectConfigResponse = {
  filename: "DRProject.config",
  drproject_config_file_base64: "BBBB",
};

const okJson = (obj: unknown) => ({ ok: true, status: 200, json: async () => obj });

let clickSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  window.sessionStorage.clear();
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: vi.fn(() => "blob:mock"),
    revokeObjectURL: vi.fn(),
  });
  clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

async function fillDepot(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Street address"), "1 Warehouse Way");
  await user.type(screen.getByLabelText("City"), "Salt Lake City");
  await user.type(screen.getByLabelText("State"), "UT");
  await user.type(screen.getByLabelText("ZIP"), "84101");
}

describe("DatasetWizard", () => {
  it("starts on route questions with no mention of file types (AC1)", () => {
    render(<DatasetWizard />);
    expect(screen.getByRole("heading", { name: "Route details" })).toBeInTheDocument();
    expect(screen.queryByText(/truck file|stop file|\.truck|\.xlsx/i)).not.toBeInTheDocument();
  });

  it("blocks advancing when a required depot field is empty (AC-per-step)", async () => {
    const user = userEvent.setup();
    render(<DatasetWizard />);
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(await screen.findAllByText("Required")).not.toHaveLength(0);
    expect(screen.getByRole("heading", { name: "Route details" })).toBeInTheDocument();
  });

  it("advances into stop questions without announcing a phase change (AC2)", async () => {
    const user = userEvent.setup();
    render(<DatasetWizard />);
    await fillDepot(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));

    expect(await screen.findByRole("heading", { name: "Stop details" })).toBeInTheDocument();
  });

  it("preserves answers when navigating back (state NFR)", async () => {
    const user = userEvent.setup();
    render(<DatasetWizard />);
    await fillDepot(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByRole("heading", { name: "Stop details" });

    await user.click(screen.getByRole("button", { name: "Back" }));
    await screen.findByRole("heading", { name: "Route details" });

    expect(screen.getByLabelText("Street address")).toHaveValue("1 Warehouse Way");
  });

  it("completes the flow and offers all three downloads (AC3, AC4, AC6)", async () => {
    const fetchMock = vi.fn(async (url: string | URL) => {
      const u = String(url);
      if (u.includes("/api/trucks/generate")) return okJson(truckResponse);
      if (u.includes("/api/stops/generate")) return okJson(stopResponse);
      if (u.includes("/api/drproject-config/generate")) return okJson(drprojectConfigResponse);
      throw new Error(`unexpected url ${u}`);
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    const user = userEvent.setup();
    render(<DatasetWizard />);
    await fillDepot(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByRole("heading", { name: "Stop details" });
    await user.click(screen.getByRole("button", { name: "Continue" }));

    // Review step (AC3 preview summary).
    await screen.findByRole("heading", { name: "Check your answers" });
    expect(screen.getByText("Total trucks")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Generate dataset" }));

    await screen.findByRole("heading", { name: "Your dataset is ready" });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(screen.getByText(/DirectRoute user data directory/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Download stops CSV/ })).toBeInTheDocument();
    expect(screen.getByLabelText(/Branch name/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Download truck file/ }));
    await user.click(screen.getByRole("button", { name: /Download stop file/ }));
    await user.click(screen.getByRole("button", { name: /Download project config/ }));
    expect(clickSpy).toHaveBeenCalledTimes(3);
  });

  it("downloads a single zip via Download All without requiring a Branch name (SPEC-018)", async () => {
    const fetchMock = vi.fn(async (url: string | URL) => {
      const u = String(url);
      if (u.includes("/api/trucks/generate")) return okJson(truckResponse);
      if (u.includes("/api/stops/generate")) return okJson(stopResponse);
      if (u.includes("/api/drproject-config/generate")) return okJson(drprojectConfigResponse);
      throw new Error(`unexpected url ${u}`);
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    const user = userEvent.setup();
    render(<DatasetWizard />);
    await fillDepot(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByRole("heading", { name: "Stop details" });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByRole("heading", { name: "Check your answers" });
    await user.click(screen.getByRole("button", { name: "Generate dataset" }));
    await screen.findByRole("heading", { name: "Your dataset is ready" });

    // Branch name stays empty — the zip must not depend on it.
    await user.click(screen.getByRole("button", { name: /Download All/ }));

    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Required")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    // No extra network traffic — the zip is built from in-memory payloads.
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("shows an alert when zip preparation fails and keeps individual downloads usable (SPEC-018)", async () => {
    const fetchMock = vi.fn(async (url: string | URL) => {
      const u = String(url);
      // Invalid base64 makes the zip decode throw; the stop file stays valid.
      if (u.includes("/api/trucks/generate"))
        return okJson({ ...truckResponse, truck_file_base64: "!!!" });
      if (u.includes("/api/stops/generate")) return okJson(stopResponse);
      if (u.includes("/api/drproject-config/generate")) return okJson(drprojectConfigResponse);
      throw new Error(`unexpected url ${u}`);
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    const user = userEvent.setup();
    render(<DatasetWizard />);
    await fillDepot(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByRole("heading", { name: "Stop details" });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByRole("heading", { name: "Check your answers" });
    await user.click(screen.getByRole("button", { name: "Generate dataset" }));
    await screen.findByRole("heading", { name: "Your dataset is ready" });

    await user.click(screen.getByRole("button", { name: /Download All/ }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(clickSpy).not.toHaveBeenCalled();

    // Individual downloads are unaffected by the zip failure.
    await user.click(screen.getByRole("button", { name: /Download stop file/ }));
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  it("gates stops CSV download on a non-empty Branch name (SPEC-016)", async () => {
    const fetchMock = vi.fn(async (url: string | URL) => {
      const u = String(url);
      if (u.includes("/api/trucks/generate")) return okJson(truckResponse);
      if (u.includes("/api/stops/generate")) return okJson(stopResponse);
      if (u.includes("/api/drproject-config/generate")) return okJson(drprojectConfigResponse);
      if (u.includes("/api/stops-csv/download")) {
        return {
          ok: true,
          status: 200,
          headers: new Headers({
            "Content-Disposition": 'attachment; filename="stops.csv"',
            "Content-Type": "text/csv",
          }),
          blob: async () => new Blob(["csv"], { type: "text/csv" }),
        };
      }
      throw new Error(`unexpected url ${u}`);
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    const user = userEvent.setup();
    render(<DatasetWizard />);
    await fillDepot(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByRole("heading", { name: "Stop details" });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByRole("heading", { name: "Check your answers" });
    await user.click(screen.getByRole("button", { name: "Generate dataset" }));
    await screen.findByRole("heading", { name: "Your dataset is ready" });

    await user.click(screen.getByRole("button", { name: /Download stops CSV/ }));
    expect(await screen.findByText("Required")).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("stops-csv"))).toHaveLength(
      0,
    );

    await user.type(screen.getByLabelText(/Branch name/i), "ATL01");
    await user.click(screen.getByRole("button", { name: /Download stops CSV/ }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) => String(url).includes("/api/stops-csv/download")),
      ).toBe(true),
    );
    expect(clickSpy).toHaveBeenCalled();
  });

  it("maps a backend 422 back onto the owning field and returns to its step (AC5)", async () => {
    const fetchMock = vi.fn(async (url: string | URL) => {
      const u = String(url);
      if (u.includes("/api/trucks/generate")) {
        return {
          ok: false,
          status: 422,
          json: async () => ({
            detail: [{ loc: ["body", "weeks"], msg: "must be > 0", type: "value_error" }],
          }),
        };
      }
      return okJson(stopResponse);
    });
    vi.stubGlobal("fetch", fetchMock as unknown as typeof fetch);

    const user = userEvent.setup();
    render(<DatasetWizard />);
    await fillDepot(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByRole("heading", { name: "Stop details" });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByRole("heading", { name: "Check your answers" });
    await user.click(screen.getByRole("button", { name: "Generate dataset" }));

    // Error returns to the route step and shows the server message on the field.
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Route details" })).toBeInTheDocument(),
    );
    expect(await screen.findByText("must be > 0")).toBeInTheDocument();
    // Answers are preserved (no reset on failure).
    expect(screen.getByLabelText("Street address")).toHaveValue("1 Warehouse Way");
  });
});
