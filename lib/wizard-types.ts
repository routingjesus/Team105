/**
 * TypeScript mirror of the backend Pydantic contract.
 *
 * Shapes intentionally match `backend/schemas/truck_config.py` and
 * `backend/schemas/stop_config.py` field-for-field (snake_case wire format),
 * so wizard form values can be sent as request bodies without a mapping layer.
 * Do not redefine these divergently — extend the backend contract instead.
 */

// --- Truck request (backend/schemas/truck_config.py) ---

export interface VolumeSpec {
  name: string;
  capacity: number;
}

export interface DepotSpec {
  address: string;
  city: string;
  state: string;
  zip: string;
  trucks: number;
}

export interface TruckConfig {
  weeks: number;
  depots: DepotSpec[];
  mi_cost: number;
  hr_cost: number;
  fixed_cost: number;
  max_work: number;
  max_drive: number;
  pre_trip: number;
  post_trip: number;
  sp_eq: string;
  volumes: VolumeSpec[];
  seed: number;
}

// --- Truck response ---

export interface DepotSummary {
  address: string;
  city: string;
  state: string;
  zip: string;
  truck_count: number;
}

export interface TruckGenerationResponse {
  truck_row_count: number;
  weeks: number;
  territory_count: number;
  depot_count: number;
  depots: DepotSummary[];
  volume_names: VolumeSpec[];
  seed: number;
  filename: string;
  truck_file_base64: string;
}

// --- Stop request (backend/schemas/stop_config.py) ---

export type SelectionMode = "radius" | "state";

export interface SelectionConfig {
  mode: SelectionMode;
  radius_miles?: number | null;
  states?: string[] | null;
}

export type VolumeAnswerMode = "fixed" | "averaged";

export interface VolumeAnswer {
  name: string;
  mode: VolumeAnswerMode;
  value: number;
}

export type PatternScope = "week" | "weekday" | "weekend" | "random" | "specific_days";

export type DayLetter = "S" | "M" | "T" | "W" | "R" | "F" | "A";

export interface TimeWindowConfig {
  mode: "fixed" | "randomized";
  open1?: number | null;
  close1?: number | null;
  pattern_scope: PatternScope;
  specific_days?: DayLetter[] | null;
}

export interface EqCodeConfig {
  enabled: boolean;
  codes: string[];
  fraction: number;
}

export interface ConsolidationConfig {
  enabled: boolean;
  lines_per_customer: number;
}

export interface AliasConfig {
  name?: string | null;
  contact?: string | null;
  phone?: string | null;
  id1?: string | null;
  id2?: string | null;
  id3?: string | null;
  address_2?: string | null;
}

export interface StopConfig {
  depots: DepotSummary[];
  weeks: number;
  volumes: VolumeSpec[];
  selection: SelectionConfig;
  stop_count: number;
  fixed_time_minutes: number;
  volume_answers: VolumeAnswer[];
  frequency_values: number[];
  time_window: TimeWindowConfig;
  eq_code?: EqCodeConfig | null;
  consolidation?: ConsolidationConfig | null;
  aliases?: AliasConfig | null;
  seed: number;
}

// --- Stop response ---

export interface StopGenerationResponse {
  candidate_count: number;
  selected_stop_count: number;
  output_row_count: number;
  seed: number;
  filename: string;
  stop_file_base64: string;
}

// --- FastAPI error contract (HTTP 422) ---

export interface FastApiValidationDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface FastApiErrorBody {
  detail?: string | FastApiValidationDetail[];
}

/**
 * Known DirectRoute Frequency values (service occurrences per week), mirroring
 * `FREQUENCY_VALUES` in `backend/schemas/stop_config.py`. The backend rejects
 * any value not in this set, so the wizard offers exactly these.
 */
export const FREQUENCY_VALUES: readonly number[] = [
  7, 6, 5, 4, 3, 2, 1, 0.5, 0.25, 0.125, 0.083, 0.077,
];

export const FREQUENCY_LABELS: Record<string, string> = {
  "7": "7x per week (daily)",
  "6": "6x per week",
  "5": "5x per week",
  "4": "4x per week",
  "3": "3x per week",
  "2": "2x per week",
  "1": "1x per week",
  "0.5": "2x per month",
  "0.25": "1x per month",
  "0.125": "Every 8 weeks",
  "0.083": "Quarterly",
  "0.077": "Every 13 weeks",
};

export const DAY_LETTERS: readonly DayLetter[] = ["S", "M", "T", "W", "R", "F", "A"];

export const DAY_LABELS: Record<DayLetter, string> = {
  S: "Sun",
  M: "Mon",
  T: "Tue",
  W: "Wed",
  R: "Thu",
  F: "Fri",
  A: "Sat",
};
