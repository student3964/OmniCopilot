"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export default function AuthCallback() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    // 1. Google Auth returns a JWT token
    const token = searchParams.get("token");
    if (token) {
      localStorage.setItem("omni_token", token);
    }
    
    // 2. Integrations return status
    const status = searchParams.get("status");
    if (status === "ok") {
      // Integration successful
      console.log("Integration connected:", searchParams.get("provider"));
    }

    // Replace URL to prevent token leaking in history and redirect to chat
    router.replace("/chat");
  }, [router, searchParams]);

  return (
    <div className="flex h-screen items-center justify-center bg-gray-50 dark:bg-gray-900">
      <div className="flex flex-col items-center gap-4">
        <svg className="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span className="text-lg font-medium text-gray-700 dark:text-gray-300">Authenticating...</span>
      </div>
    </div>
  );
}
