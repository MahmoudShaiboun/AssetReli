import axios from 'axios';
import { API_URL } from '../config';

interface LoginResponse {
  access_token: string;
  token_type: string;
}

interface User {
  id: string;
  tenant_id: string;
  email: string;
  username: string;
  full_name?: string;
  role: string;
  is_active: boolean;
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
      await this.fetchUserInfo();
    }

    return response.data;
  }

  async register(email: string, username: string, password: string, fullName?: string): Promise<LoginResponse> {
    const response = await axios.post<LoginResponse>(`${API_URL}/register`, {
      email,
      username,
      password,
      full_name: fullName
    });

    if (response.data.access_token) {
      localStorage.setItem(this.tokenKey, response.data.access_token);
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

  logout() {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.userKey);
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
