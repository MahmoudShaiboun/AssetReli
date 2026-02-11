import axios from 'axios';

const API_URL = 'http://localhost:8000';

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
      null,
      {
        params: { email, password }
      }
    );
    
    if (response.data.access_token) {
      localStorage.setItem(this.tokenKey, response.data.access_token);
      // Fetch user info
      await this.fetchUserInfo();
    }
    
    return response.data;
  }

  async register(email: string, username: string, password: string, fullName?: string): Promise<User> {
    const response = await axios.post<User>(`${API_URL}/register`, {
      email,
      username,
      password,
      full_name: fullName
    });
    
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
