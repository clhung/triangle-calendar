export interface KidEvent {
  uid: string;
  title: string;
  url: string;
  date: string;
  is_all_day: boolean;
  start_time: string | null;
  end_time: string | null;
  time_str: string;
  cost: string;
  location: string;
}

export interface SyncStatus {
  status: string;
  calendar: {
    exists: boolean;
    size: number;
    updatedAt: string | null;
    eventCount: number;
  };
  hasScript: boolean;
  hasWorkflow: boolean;
}

export interface SyncResult {
  success: boolean;
  durationMs: number;
  eventCount: number;
  stdout: string;
  stderr: string;
}
