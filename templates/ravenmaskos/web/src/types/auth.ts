export interface CurrentUser {
  user_id: string;
  email: string;
  org_id: string;
  roles: string[];
  scopes: string[];
  token_type: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  name: string;
  org_name?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordReset {
  token: string;
  new_password: string;
}

export interface MFASetup {
  secret: string;
  qr_code_url: string;
}

export interface MFAVerification {
  code: string;
}
