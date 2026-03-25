export type StructuredLogEntry = {
  timestamp: string;
  level: string;
  service: string;
  message: string;
  [key: string]: unknown;
};

export type LogEntry = string | StructuredLogEntry;

export type AnalyzeRequestPayload = {
  logs: LogEntry[];
  source: string;
  unknown_ratio_threshold: number;
};

export type AnalyzeResponse = {
  source?: string;
  analysis?: {
    anomaly_score?: number | null;
    is_anomaly?: boolean | null;
    threshold?: number;
    model_mode?: string;
    final_status?: string;
    events_parsed?: number;
  };
  llm_explanation?: {
    attack_type?: string;
    reason?: string;
    recommended_action?: string;
    source?: string;
  };
  policy?: {
    severity?: string;
    score?: number | null;
    top_service?: string;
    critical_service?: boolean;
    attack_type?: string;
    allowed_actions?: string[];
    requires_human_approval?: boolean;
  };
  response?: {
    actions?: string[];
    executed_actions?: string[];
    human_in_the_loop?: boolean;
  };
  decision?: {
    status?: string;
    severity?: string;
    final_action_count?: number;
  };
  compatibility?: {
    is_supported?: boolean;
    reason?: string;
    total_events?: number;
    unknown_event_ratio?: number;
    known_event_ratio?: number;
    threshold?: number;
  };
  cloud_metrics?: {
    total_logs?: number;
    failed_logs?: number;
    error_rate?: number;
    unique_source_ips?: number;
    top_service?: string;
    service_distribution?: Record<string, number>;
  };
  model_card?: {
    model_mode?: string;
    model_threshold?: number;
    max_seq_len?: number;
    vocab_size?: number;
  };
  [key: string]: unknown;
};
