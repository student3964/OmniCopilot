import React, { useEffect, useState } from "react";
import { fetchApi } from "../../lib/api";
import { ConnectCard } from "../ui/ConnectCard";

interface Conversation {
  id: string;
  title: string;
  created_at: string;
}

interface SidebarProps {
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  activeConversationId?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ 
  onNewChat, 
  onSelectConversation,
  activeConversationId 
}) => {
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchIntegrations = async () => {
    try {
      const data = await fetchApi<{ integrations: IntegrationStatus[] }>("/api/integrations/status");
      setIntegrations(data.integrations);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchConversations = async () => {
    try {
      const data = await fetchApi<Conversation[]>("/api/chat/conversations");
      setConversations(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this chat?")) return;
    
    try {
      await fetchApi(`/api/chat/conversations/${id}`, { method: "DELETE" });
      await fetchConversations();
      if (activeConversationId === id) {
        onNewChat();
      }
    } catch (e) {
      alert("Failed to delete chat");
    }
  };

  useEffect(() => {
    Promise.all([fetchIntegrations(), fetchConversations()]);
  }, []);

  const handleDisconnect = async (provider: string) => {
    if(!confirm(`Are you sure you want to disconnect ${provider}?`)) return;
    try {
      await fetchApi(`/api/integrations/${provider}`, { method: "DELETE" });
      await fetchIntegrations();
    } catch (e) {
      alert("Failed to disconnect");
    }
  };

  return (
    <div className="w-64 h-full bg-gray-50/50 dark:bg-gray-900/50 border-r border-gray-200 dark:border-gray-800 p-4 flex flex-col">
      <div className="mb-8">
        <h1 className="text-xl font-black bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-1">
          Omni Copilot
        </h1>
        <p className="text-xs text-gray-500 font-medium">Unified AI Assistant</p>
      </div>

      <div className="flex-1 overflow-y-auto space-y-6">
        {/* New Chat Button */}
        <button 
          onClick={onNewChat}
          className="w-full py-3 px-4 rounded-xl border-2 border-dashed border-blue-500/30 hover:border-blue-500 hover:bg-blue-50/50 dark:hover:bg-blue-900/10 text-blue-600 dark:text-blue-400 font-bold text-sm transition-all flex items-center justify-center gap-2"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Chat
        </button>

        {/* Recent Chats Section */}
        <div>
          <h3 className="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em] mb-3 px-1">Recent Chats</h3>
          <div className="flex flex-col gap-1">
            {conversations.length === 0 && !loading && (
              <p className="text-[11px] text-gray-400 px-1 italic">No recent chats</p>
            )}
            {conversations.map(conv => (
              <div key={conv.id} className="group relative">
                <button
                  onClick={() => onSelectConversation(conv.id)}
                  className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-all truncate pr-10 hover:bg-gray-100 dark:hover:bg-gray-800 ${
                    activeConversationId === conv.id 
                      ? "bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 font-semibold ring-1 ring-blue-500/20" 
                      : "text-gray-600 dark:text-gray-400"
                  }`}
                >
                  {conv.title || "Untitled Chat"}
                </button>
                <button
                  onClick={(e) => handleDelete(e, conv.id)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Delete chat"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Integrations Section */}
        <div>
          <h3 className="text-[10px] font-black text-gray-400 uppercase tracking-[0.2em] mb-3 px-1">Integrations</h3>
          
          {loading ? (
            <div className="animate-pulse space-y-3">
              {[1, 2].map(i => <div key={i} className="h-10 bg-gray-200 dark:bg-gray-800 rounded-lg"></div>)}
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {integrations.map(auth => (
                <ConnectCard 
                  key={auth.provider}
                  provider={auth.provider}
                  connected={auth.connected}
                  onDisconnect={handleDisconnect}
                />
              ))}
            </div>
          )}
        </div>
      </div>
      
      <div className="pt-4 border-t border-gray-200 dark:border-gray-800 text-xs text-gray-400 text-center">
        ⚡ Powered by LangGraph
      </div>
    </div>
  );
};
