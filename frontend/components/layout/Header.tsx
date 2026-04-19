import React from "react";
import { useAuth } from "../../hooks/useAuth";

export const Header: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <header className="h-16 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between px-6 bg-white/80 dark:bg-gray-900/80 backdrop-blur-md sticky top-0 z-10 w-full transition-colors">
      <div className="flex items-center gap-2">
        <span className="text-xl font-medium tracking-tight text-gray-800 dark:text-gray-100">
          Chat
        </span>
      </div>
      
      <div className="flex items-center gap-4">
        {user ? (
          <div className="flex items-center gap-3">
             <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
               {user.email}
             </div>
             <button 
               onClick={logout}
               className="text-xs px-3 py-1.5 rounded-full bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition"
             >
               Logout
             </button>
          </div>
        ) : (
          <div className="text-sm text-gray-500">Not logged in</div>
        )}
      </div>
    </header>
  );
};
