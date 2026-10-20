export type Role = "admin" | "practitioner" | "client";
export type DeploymentMode = "demo" | "local" | "hosted";
export interface Health {
  status: string;
  mode: DeploymentMode;
  version: string;
  source_url: string | null;
  license: string | null;
}
export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  client_id: number | null;
  tour_completed: boolean;
}
export interface Client {
  is_test?: boolean;
  test_owner_id?: number | null;
  archived_at?: string | null;
  id: number;
  name: string;
  email: string;
  birth_date: string | null;
  birth_time: string | null;
  birth_place: string | null;
  themes: string[];
  chart: Chart | null;
  chart_shared?: boolean;
  created_at: string;
}
export interface Resource {
  id: number;
  client_id: number;
  kind: "note" | "task" | "audio";
  title: string;
  body: string;
  shared: boolean;
  audio_url: string | null;
  created_at: string;
}
export interface Appointment {
  id: number;
  client_id: number;
  client_name: string;
  start_at: string;
  duration_minutes: number;
  title: string;
  status: "scheduled" | "in_progress" | "completed" | "cancelled";
  prepared: boolean;
  price_cents: number;
}
export interface Place {
  id: string;
  label: string;
  latitude: number;
  longitude: number;
  timezone: string;
  source: string;
}
export interface Planet {
  name: string;
  longitude: number;
  sign: string;
  degree: number;
  house: number;
  retrograde: boolean;
}
export interface Chart {
  ascendant: { longitude: number; sign: string; degree: number };
  planets: Planet[];
  houses: { house: number; longitude: number; sign: string; degree: number }[];
  aspects: { planet1: string; planet2: string; aspect: string; orb: number }[];
  timezone: string;
  utc_datetime: string;
  coordinates: {
    latitude: number;
    longitude: number;
    label?: string;
    source?: string;
  };
  source:
    | {
        engine?: string;
        actual_ephemerides?: string[];
        version?: string;
        reference?: string;
        license?: string;
      }
    | string;
  timezone_source?: string;
  house_system?: string;
  warnings: string[];
}
export interface Lesson {
  id: number;
  title: string;
  category: string;
  summary: string;
  body: string;
  week: number;
  source_url: string;
  source_title: string;
  source_kind?:
    | "editorial"
    | "simulation_metadata"
    | "rss_metadata"
    | "source_reading_draft";
  status: "draft" | "published";
  available: boolean;
  completed: boolean;
  quiz: { id: string; question: string; options: string[] }[];
  track: string;
  level: "foundation" | "deepening" | "practice";
  learning_objective: string;
  exercise: string;
  reflection_prompt: string;
  content_version: number;
  source_note: string;
  bookmarked: boolean;
  pinned: boolean;
  practiced: boolean;
  reflected: boolean;
}
export interface AdminLesson extends Lesson {
  quiz: (Lesson["quiz"][number] & { correct_index: number })[];
}
export interface NotebookNote {
  id: number;
  user_id: number;
  lesson_id: number | null;
  lesson_title_snapshot: string | null;
  lesson_version_snapshot: number | null;
  title: string;
  body: string;
  created_at: string;
  updated_at: string;
}
export interface LearningData {
  lessons: Lesson[];
  progress: { completed_ids: number[]; quiz_scores: Record<string, number> };
  next_unlock_at: string | null;
}
export interface Dashboard {
  clients_count: number;
  upcoming_count: number;
  completed_count: number;
  revenue_cents: number;
  appointments: Appointment[];
  clients: Client[];
}
export interface Portal {
  client: Client;
  appointments: Appointment[];
  resources: Resource[];
}

export interface LearningUpdateSource {
  key: string;
  title: string;
  url: string;
  fetch_status?: string;
  fetched_at?: string;
  candidates?: number;
}
export interface LearningUpdateRun {
  id: number;
  trigger: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  created: number;
  error: string | null;
  sources: LearningUpdateSource[];
}
export interface LearningUpdatesStatus {
  enabled: boolean;
  interval_days: number;
  next_due_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  stale: boolean;
  last_run_at: string | null;
  last_run_status: string | null;
  active_run: LearningUpdateRun | null;
  recent_runs: LearningUpdateRun[];
  findings: {
    source_key: string;
    url: string;
    title: string;
    published_at: string | null;
    discovered_at: string;
    fetched_at: string;
    fetch_status: string;
    text_chars: number;
    lesson_id: number | null;
  }[];
  sources: LearningUpdateSource[];
  review_required: boolean;
  publication_automatic: boolean;
}
export interface LearningUpdateResult {
  status: string;
  created: number;
  run_id?: number;
  next_due_at?: string;
  sources?: LearningUpdateSource[];
  error?: string | null;
}
