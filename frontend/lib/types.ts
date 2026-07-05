export interface User {
  id: string;
  email: string;
  full_name: string;
  business_name: string | null;
  is_active: boolean;
  timezone: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface PendingApproval {
  agent: string;
  email_draft_id?: string;
  calendar_draft_id?: string;
  status?: string;
}

export interface GeneratedDocument {
  document_id: string;
  title?: string;
  download_url?: string;
}

export interface ChatResponse {
  conversation_id: string;
  reply: string;
  pending_approvals: PendingApproval[];
  documents: GeneratedDocument[];
  agent_run_id: string | null;
}

export interface MessageRead {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
}

export interface ConversationRead {
  id: string;
  title: string;
  channel: string;
  created_at: string;
}

export interface ConversationDetail extends ConversationRead {
  messages: MessageRead[];
}

export interface DocumentRead {
  id: string;
  title: string;
  doc_type: string;
  file_format: string;
  status: string;
  created_at: string;
}

export interface TaskRead {
  id: string;
  title: string;
  description: string | null;
  status: string;
  due_at: string | null;
  created_at: string;
}

export interface EmailDraftRead {
  id: string;
  to_addresses: string[];
  subject: string;
  body: string;
  status: string;
  created_at: string;
}

export interface CalendarEventDraftRead {
  id: string;
  title: string;
  description: string | null;
  start_time: string;
  end_time: string;
  attendees: string[];
  status: string;
  timezone: string;
  meet_link: string | null;
  created_at: string;
}

export interface NotificationRead {
  id: string;
  type: string;
  title: string;
  body: string | null;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

export interface MemoryItemRead {
  id: string;
  content: string;
  category: string;
  importance: number;
}
