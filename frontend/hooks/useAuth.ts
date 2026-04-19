import { useState, useEffect } from "react";
import { fetchApi, getToken } from "../lib/api";

export interface User {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const initAuth = async () => {
      const token = getToken();
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const userData = await fetchApi<User>("/api/auth/me");
        setUser(userData);
        setIsAuthenticated(true);
      } catch (error) {
        console.error("Auth check failed:", error);
        localStorage.removeItem("omni_token");
        setUser(null);
        setIsAuthenticated(false);
      } finally {
        setLoading(false);
      }
    };

    initAuth();
  }, []);

  const logout = () => {
    localStorage.removeItem("omni_token");
    setUser(null);
    setIsAuthenticated(false);
  };

  return { user, loading, isAuthenticated, logout };
}
