import React, { useState, useEffect, useRef } from "react";
import { useAuth } from "../../hooks/useAuth";
import { useTheme } from "../ThemeProvider";
import { fetchApi } from "../../lib/api";
import { ConnectCard } from "../ui/ConnectCard";
import { Sun, Moon, Plug } from "lucide-react";

interface IntegrationStatus {
  provider: string;
  connected: boolean;
  scope?: string;
  expires_at?: string;
}

export const Header: React.FC = () => {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  
  const [integrationsOpen, setIntegrationsOpen] = useState(false);
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [loading, setLoading] = useState(false);
  
  const menuRef = useRef<HTMLDivElement>(null);

  const fetchIntegrations = async () => {
    setLoading(true);
    try {
      const data = await fetchApi<{ integrations: IntegrationStatus[] }>("/api/integrations/status");
      setIntegrations(data.integrations);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (integrationsOpen) {
      fetchIntegrations();
    }
  }, [integrationsOpen]);

  // Click outside to close the popover
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIntegrationsOpen(false);
      }
    };
    if (integrationsOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [integrationsOpen]);

  const handleDisconnect = async (provider: string) => {
    if(!confirm(`Are you sure you want to disconnect ${provider}?`)) return;
    try {
      await fetchApi(`/api/integrations/${provider}`, { method: "DELETE" });
      await fetchIntegrations(); // Refresh
    } catch (e) {
      alert("Failed to disconnect");
    }
  };

  return (
    <header className="h-16 border-b border-gray-200/50 dark:border-white/10 flex items-center justify-between px-6 bg-white/60 dark:bg-gray-900/50 backdrop-blur-xl sticky top-0 z-30 w-full transition-colors shadow-sm">
      <div className="flex items-center gap-2">
      </div>
      
      <div className="flex items-center gap-4">
        {/* Toggle Theme */}
        <button
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          className="p-2 rounded-full bg-gray-100/80 dark:bg-gray-800/80 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition-all shadow-sm"
          title="Toggle Theme"
        >
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        {user ? (
          <>
            {/* Integrations Popover */}
            <div className="relative" ref={menuRef}>
              <button 
                onClick={() => setIntegrationsOpen(!integrationsOpen)}
                className={`flex items-center gap-2 text-sm px-3 py-2 rounded-xl transition-all shadow-sm font-medium border ${
                  integrationsOpen 
                  ? "bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-800/50" 
                  : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 border-gray-200 dark:border-gray-700/50"
                }`}
              >
                <Plug size={16} />
                <span>Integrations</span>
              </button>

              {integrationsOpen && (
                <div className="absolute right-0 mt-3 w-80 bg-white/90 dark:bg-gray-900/90 backdrop-blur-xl border border-gray-200 dark:border-gray-700 rounded-2xl shadow-2xl overflow-hidden py-3 px-4 animate-fade-in origin-top">
                  <h3 className="text-xs font-black text-gray-400 dark:text-gray-500 uppercase tracking-widest pl-1 mb-3">
                    Connected Services
                  </h3>
                  
                  {loading ? (
                    <div className="animate-pulse space-y-3">
                      {[1, 2, 3].map(i => <div key={i} className="h-12 bg-gray-200 dark:bg-gray-800 rounded-xl"></div>)}
                    </div>
                  ) : (
                    <div className="flex flex-col gap-2 max-h-[60vh] overflow-y-auto scrollbar-hide">
                      {integrations.length === 0 ? (
                         <div className="text-sm text-gray-500 py-2">No integrations available.</div>
                      ) : (
                         integrations.map(auth => (
                           <ConnectCard 
                             key={auth.provider}
                             provider={auth.provider}
                             connected={auth.connected}
                             onDisconnect={handleDisconnect}
                           />
                         ))
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Profile / Logout */}
            <div className="flex items-center gap-3 pl-2 border-l border-gray-200 dark:border-gray-700">
               <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
                 {user.email}
               </div>
               <button 
                 onClick={logout}
                 className="text-xs font-bold px-4 py-2 rounded-xl bg-gradient-to-r from-red-500/10 to-red-600/10 hover:from-red-500/20 hover:to-red-600/20 text-red-600 dark:text-red-400 transition"
               >
                 Logout
               </button>
            </div>
          </>
        ) : (
          <div className="text-sm text-gray-500">Not logged in</div>
        )}
      </div>
    </header>
  );
};
