import axios from 'axios';
import { API_URL } from '../config';

interface LoginResponse {
  access_token: string;
  token_type: string;
}

interface User {
  email: string;
  username: string;
  full_name?: string;
  disabled: boolean;
}

class AuthService {
  private tokenKey = 'aastreli_token';
  private userKey = 'aastreli_user';

  async login(email: string, password: string): Promise<LoginResponse> {
    const response = await axios.post<LoginResponse>(
      `${API_URL}/login`,
      { email, password }
    );

    if (response.data.access_token) {
      localStorage.setItem(this.tokenKey, response.data.access_token);
      this.extractTenantFromToken(response.data.access_token);
      await this.fetchUserInfo();
    }

    return response.data;
  }

  async register(email: string, username: string, password: string, fullName?: string, tenantCode?: string): Promise<LoginResponse> {
    const body: Record<string, string> = { email, username, password };
    if (fullName) body.full_name = fullName;
    if (tenantCode) body.tenant_code = tenantCode;

    const response = await axios.post<LoginResponse>(`${API_URL}/register`, body);

    if (response.data.access_token) {
      localStorage.setItem(this.tokenKey, response.data.access_token);
      this.extractTenantFromToken(response.data.access_token);
      await this.fetchUserInfo();
    }

    return response.data;
  }

  async fetchUserInfo(): Promise<User | null> {
    const token = this.getToken();
    if (!token) return null;

    try {
      const response = await axios.get<User>(`${API_URL}/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      localStorage.setItem(this.userKey, JSON.stringify(response.data));
      return response.data;
    } catch (error) {
      this.logout();
      return null;
    }
  }

  private extractTenantFromToken(token: string) {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) return;
      const payload = JSON.parse(atob(parts[1]));
      // Store scope and role
      if (payload.scope) localStorage.setItem('aastreli_scope', payload.scope);
      if (payload.role) localStorage.setItem('aastreli_role', payload.role);
      // Only store tenant_id for tenant-scoped users
      if (payload.tenant_id) {
        localStorage.setItem('aastreli_tenant_id', payload.tenant_id);
      } else {
        // Platform-scoped (super_admin) — clear any stale tenant_id
        localStorage.removeItem('aastreli_tenant_id');
      }
    } catch {
      // ignore decode errors
    }
  }

  logout() {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.userKey);
    localStorage.removeItem('aastreli_tenant_id');
    localStorage.removeItem('aastreli_scope');
    localStorage.removeItem('aastreli_role');
  }

  getToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  getCurrentUser(): User | null {
    const userStr = localStorage.getItem(this.userKey);
    if (userStr) {
      return JSON.parse(userStr);
    }
    return null;
  }

  isAuthenticated(): boolean {
    return this.getToken() !== null;
  }

  getAuthHeader(): { Authorization: string } | {} {
    const token = this.getToken();
    if (token) {
      return { Authorization: `Bearer ${token}` };
    }
    return {};
  }
}

export default new AuthService();
