import { describe, expect, it } from "vitest";
import { buildStopConfig, buildTruckConfig } from "./build-config";
import { defaultWizardValues, type WizardFormValues } from "./wizard-schema";
import type { TruckGenerationResponse } from "./wizard-types";

const values: WizardFormValues = {
  ...defaultWizardValues,
  depots: [{ ...defaultWizardValues.depots[0], address: "1 Warehouse Way", city: "Salt Lake City", state: "UT", zip: "84101" }],
  volumes: [{ name: "Cases", capacity: 2000 }],
  volumeAnswers: [{ name: "Cases", mode: "averaged", value: 40 }],
};

const truckResponse: TruckGenerationResponse = {
  truck_row_count: 70,
  weeks: 2,
  territory_count: 5,
  depot_count: 1,
  depots: [{ address: "1 Warehouse Way", city: "Salt Lake City", state: "UT", zip: "84101", truck_count: 5 }],
  volume_names: [{ name: "Cases", capacity: 2000 }],
  seed: 0,
  filename: "fleet.truck",
  truck_file_base64: "",
};

describe("buildTruckConfig", () => {
  it("maps form values to the snake_case TruckConfig contract", () => {
    const config = buildTruckConfig(values);
    expect(config).toMatchObject({
      weeks: 2,
      mi_cost: 1.39,
      hr_cost: 30,
      fixed_cost: 250,
      max_work: 14,
      max_drive: 11,
      pre_trip: 15,
      post_trip: 30,
      sp_eq: "",
      seed: 0,
    });
    expect(config.depots[0]).toEqual({
      address: "1 Warehouse Way",
      city: "Salt Lake City",
      state: "UT",
      zip: "84101",
      trucks: 5,
      latitude: null,
      longitude: null,
    });
    expect(config.volumes[0]).toEqual({ name: "Cases", capacity: 2000 });
  });
});

describe("buildStopConfig", () => {
  it("derives depots/weeks/volumes from the truck response", () => {
    const config = buildStopConfig(values, truckResponse);
    expect(config.depots).toEqual([
      {
        ...truckResponse.depots[0],
        latitude: null,
        longitude: null,
      },
    ]);
    expect(config.weeks).toBe(truckResponse.weeks);
    expect(config.volumes).toEqual(truckResponse.volume_names);
  });

  it("builds radius selection and nulls the state field", () => {
    const config = buildStopConfig({ ...values, selectionMode: "radius", radiusMiles: 50 }, truckResponse);
    expect(config.selection).toEqual({
      mode: "radius",
      radius_miles: 50,
      states: null,
      zips: null,
    });
  });

  it("builds state selection from comma text", () => {
    const config = buildStopConfig(
      { ...values, selectionMode: "state", states: "ut, nv" },
      truckResponse,
    );
    expect(config.selection).toEqual({
      mode: "state",
      radius_miles: null,
      states: ["UT", "NV"],
      zips: null,
    });
  });

  it("builds zip selection and maps session manual stops", () => {
    const config = buildStopConfig(
      {
        ...values,
        selectionMode: "zip",
        zips: "84101, 67861-67942",
        manualStops: [
          {
            address: "9 Custom Rd",
            address2: "",
            city: "Denver",
            state: "CO",
            zip: "80202",
            latitude: undefined,
            longitude: undefined,
          },
        ],
      },
      truckResponse,
    );
    expect(config.selection.mode).toBe("zip");
    expect(config.selection.zips?.[0]).toBe("84101");
    expect(config.selection.zips).toContain("67861");
    expect(config.selection.zips).toContain("67942");
    expect(config.manual_stops).toEqual([
      {
        address: "9 Custom Rd",
        address2: "",
        city: "Denver",
        state: "CO",
        zip: "80202",
        latitude: null,
        longitude: null,
      },
    ]);
  });

  it("forwards depot paste coords on the truck config", () => {
    const config = buildTruckConfig({
      ...values,
      depots: [
        {
          ...values.depots[0],
          latitude: 38.38080520110032,
          longitude: -97.4279212147894,
        },
      ],
    });
    expect(config.depots[0].latitude).toBe(38.38080520110032);
    expect(config.depots[0].longitude).toBe(-97.4279212147894);
  });

  it("nulls fixed-window times in randomized mode and omits optional blocks", () => {
    const config = buildStopConfig(values, truckResponse);
    expect(config.time_window.open1).toBeNull();
    expect(config.time_window.close1).toBeNull();
    expect(config.eq_code).toBeNull();
    expect(config.consolidation).toBeNull();
    expect(config.aliases).toBeNull();
    expect(config.generate_shapes).toBe(false);
    expect(config.generate_colors).toBe(false);
  });

  it("includes optional blocks when enabled", () => {
    const config = buildStopConfig(
      {
        ...values,
        eqCodeEnabled: true,
        eqCodes: "LIFT, DOCK",
        eqFraction: 0.5,
        consolidationEnabled: true,
        linesPerCustomer: 3,
      },
      truckResponse,
    );
    expect(config.eq_code).toEqual({ enabled: true, codes: ["LIFT", "DOCK"], fraction: 0.5 });
    expect(config.consolidation).toEqual({ enabled: true, lines_per_customer: 3 });
  });

  it("sends only id2/id3 aliases when aliasesEnabled is false", () => {
    const config = buildStopConfig(
      { ...values, aliasesEnabled: false, aliasId2: "Customer ID", aliasId3: "Route Zone" },
      truckResponse,
    );
    expect(config.aliases).toEqual({
      name: null,
      contact: null,
      phone: null,
      id1: null,
      id2: "Customer ID",
      id3: "Route Zone",
      address_2: null,
    });
  });

  it("still gates the other five alias fields behind aliasesEnabled", () => {
    const config = buildStopConfig(
      { ...values, aliasesEnabled: false, aliasName: "Customer Name" },
      truckResponse,
    );
    expect(config.aliases).toBeNull();
  });

  it("sends id2/id3 alongside the other five aliases when aliasesEnabled is true", () => {
    const config = buildStopConfig(
      {
        ...values,
        aliasesEnabled: true,
        aliasName: "Customer Name",
        aliasId2: "Customer ID",
        aliasId3: "Route Zone",
      },
      truckResponse,
    );
    expect(config.aliases).toEqual({
      name: "Customer Name",
      contact: null,
      phone: null,
      id1: null,
      id2: "Customer ID",
      id3: "Route Zone",
      address_2: null,
    });
  });

  it("maps shape/color generation toggles", () => {
    const config = buildStopConfig(
      { ...values, generateShapes: true, generateColors: true },
      truckResponse,
    );
    expect(config.generate_shapes).toBe(true);
    expect(config.generate_colors).toBe(true);
  });
});
