import { api } from "../../shared/api/client";
import type { AuthResult, Program } from "../../shared/api/types";

export interface RegisterInput {
  nickname: string;
  email: string;
  password: string;
  program_code: string;
  accepted_terms: boolean;
}

export const authApi = {
  programs: () => api.get<Program[]>("/programs"),
  register: (input: RegisterInput) => api.post<{ status: "pending_verification" }>("/auth/register", input),
  verifyEmail: (token: string) => api.post<AuthResult>("/auth/verify-email", { token }, { silentAuth: true }),
  resendVerification: (email: string) =>
    api.post<{ status: "accepted"; message: string }>("/auth/resend-verification", { email }),
  login: (email: string, password: string) =>
    api.post<AuthResult>("/auth/login", { email, password }, { silentAuth: true }),
  /** Un 401 significa que ya estaba cerrada: el que llama lo trata como éxito. */
  logout: () => api.post<void>("/auth/logout", undefined, { silentAuth: true }),
  deleteAccount: () => api.post<void>("/me/delete-account", { confirm: true }, { silentAuth: true }),
};
