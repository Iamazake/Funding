export type UserRole = "ADMIN" | "ANALYST";
export type UserStatus = "ACTIVE" | "INACTIVE";

export interface AppUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface LoginResponse {
  user: AppUser;
  expires_at: string;
}

export interface UserCreateInput {
  name: string;
  email: string;
  password: string;
  role: UserRole;
}

export interface UserUpdateInput {
  name?: string;
  role?: UserRole;
  status?: UserStatus;
}
