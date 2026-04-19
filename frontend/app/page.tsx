"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken, API_BASE_URL } from "../lib/api";

export default function LandingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (token) {
      router.replace("/chat");
    } else {
      setLoading(false);
    }
  }, [router]);

  if (loading) return null;

  return (
    <div className="flex h-screen flex-col items-center justify-center bg-gradient-to-br from-gray-900 to-black text-white px-4 text-center">
      <div className="max-w-md w-full flex flex-col items-center">
        
        <div className="w-20 h-20 bg-gradient-to-tr from-blue-600 to-purple-600 rounded-2xl flex items-center justify-center mb-8 shadow-2xl shadow-blue-900/50">
          <span className="text-4xl text-white">⌘</span>
        </div>

        <h1 className="text-5xl font-black mb-4 tracking-tight">Omni Copilot</h1>
        <p className="text-lg text-gray-400 mb-10 leading-relaxed">
          Your unified AI assistant. Connect Google Drive, Gmail, Calendar, Slack, Notion and more.
        </p>

        <button 
          onClick={() => window.location.href = `${API_BASE_URL}/api/auth/google/login`}
          className="flex items-center gap-3 bg-white hover:bg-gray-100 text-gray-900 font-bold px-8 py-4 rounded-xl transition shadow-lg w-full justify-center text-lg"
        >
          <svg viewBox="0 0 24 24" className="w-6 h-6" xmlns="http://www.w3.org/2000/svg"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/><path d="M1 1h22v22H1z" fill="none"/></svg>
          Continue with Google
        </button>
      </div>
    </div>
  );
}
