import React from "react";
import { API_BASE_URL } from "../../lib/api";

interface ConnectCardProps {
  provider: string;
  connected: boolean;
  onDisconnect: (provider: string) => void;
}

export const ConnectCard: React.FC<ConnectCardProps> = ({ provider, connected, onDisconnect }) => {
  const handleConnect = () => {
    // Pass JWT as query param since browser redirects don't send Authorization headers
    const token = localStorage.getItem("omni_token");
    const tokenParam = token ? `?token=${token}` : "";
    window.location.href = `${API_BASE_URL}/api/auth/${provider}/login${tokenParam}`;
  };

  const logos: Record<string, string> = {
    google: "🔵 Google",
    slack: "🟣 Slack",
    notion: "⬛ Notion",
    zoom: "🟦 Zoom",
  };

  const displayName = provider.charAt(0).toUpperCase() + provider.slice(1);

  return (
    <div className="flex items-center justify-between p-3 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-lg shadow-sm">
      <div className="flex items-center gap-3">
         <span className="font-semibold text-gray-700 dark:text-gray-300">
           {logos[provider] || displayName}
         </span>
      </div>
      
      {connected ? (
        <button 
          onClick={() => onDisconnect(provider)}
          className="text-xs px-3 py-1.5 text-gray-600 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded border border-gray-200 dark:border-gray-700 transition"
        >
          Disconnect
        </button>
      ) : (
        <button 
          onClick={handleConnect}
          className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 transition shadow-sm"
        >
          Connect
        </button>
      )}
    </div>
  );
};
