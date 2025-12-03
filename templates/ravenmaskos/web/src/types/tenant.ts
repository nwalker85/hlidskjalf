export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  updated_at: string;
}

export interface BusinessUnit {
  id: string;
  org_id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface Team {
  id: string;
  business_unit_id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  team_id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  email: string;
  username: string | null;
  full_name: string | null;
  avatar_url: string | null;
  is_active: boolean;
  is_verified: boolean;
  roles: string[];
  scopes: string[];
  mfa_enabled: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserListResponse {
  users: User[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface CreateUserRequest {
  email: string;
  password: string;
  full_name?: string;
  username?: string;
  roles?: string[];
}

export interface UpdateUserRequest {
  full_name?: string;
  username?: string;
  avatar_url?: string;
  is_active?: boolean;
  preferences?: Record<string, unknown>;
}

export interface UpdateUserRolesRequest {
  roles: string[];
}

export interface InviteUserRequest {
  email: string;
  full_name?: string;
  roles?: string[];
  send_email?: boolean;
}

export interface InviteUserResponse {
  user_id: string;
  email: string;
  invite_token: string | null;
  message: string;
}

export interface BulkUserActionRequest {
  user_ids: string[];
  action: "activate" | "deactivate" | "delete";
}

export interface BulkUserActionResponse {
  success_count: number;
  failed_count: number;
  failed_ids: string[];
}

export interface Role {
  id: string;
  name: string;
  description: string;
  scopes: string[];
  created_at: string;
  updated_at: string;
}

export interface ApiKey {
  id: string;
  name: string;
  description: string | null;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  usage_count: number;
  allowed_ips: string[] | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApiKeyCreated extends ApiKey {
  key: string;
}

export interface ApiKeyListResponse {
  api_keys: ApiKey[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface CreateApiKeyRequest {
  name: string;
  description?: string;
  scopes?: string[];
  expires_in_days?: number | null;
  allowed_ips?: string[];
}

export interface UpdateApiKeyRequest {
  name?: string;
  description?: string;
  scopes?: string[];
  is_active?: boolean;
  allowed_ips?: string[];
}

export interface RevokeApiKeyResponse {
  id: string;
  revoked_at: string;
  message: string;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  actor_id: string;
  actor_type: "user" | "service" | "agent";
  action: string;
  resource_type: string;
  resource_id: string;
  org_id: string;
  ip_address: string;
  user_agent: string;
  outcome: "success" | "failure";
  details: Record<string, unknown>;
}
