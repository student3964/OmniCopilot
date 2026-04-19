import React, { useEffect, useState, useRef, useCallback } from "react";
import { fetchApi } from "../../lib/api";
import { ConnectCard } from "../ui/ConnectCard";
import { Pencil, Trash2, Check, X, Plus } from "lucide-react";

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

interface IntegrationStatus {
  provider: string;
  connected: bool;
  scope?: string;
  expires_at?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ 
  onNewChat, 
  onSelectConversation,
  activeConversationId 
}) => {
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(256); // default 256px (w-64)
  const isResizing = useRef(false);
  
  // Renaming state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizing.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const onMouseMove = (e: MouseEvent) => {
      if (!isResizing.current) return;
      const newWidth = Math.min(520, Math.max(180, e.clientX));
      setSidebarWidth(newWidth);
    };

    const onMouseUp = () => {
      isResizing.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }, []);

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

  const startEditing = (e: React.MouseEvent, conversation: Conversation) => {
    e.stopPropagation();
    setEditingId(conversation.id);
    setEditTitle(conversation.title || "");
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditTitle("");
  };

  const handleRename = async (id: string) => {
    if (!editTitle.trim()) return;
    try {
      await fetchApi(`/api/chat/conversations/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ title: editTitle })
      });
      setEditingId(null);
      await fetchConversations();
    } catch (e) {
      alert("Failed to rename chat");
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
    <div
      className="h-full bg-gray-50/50 dark:bg-gray-900/50 border-r border-gray-200 dark:border-gray-800 p-4 flex flex-col relative flex-shrink-0"
      style={{ width: `${sidebarWidth}px` }}
    >
      <div className="mb-8">
        <h1 className="text-xl font-black bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-1">
          Omni Copilot
        </h1>
        <p className="text-xs text-gray-500 font-medium">Unified AI Assistant</p>
      </div>

      <div className="flex-1 overflow-y-auto space-y-6 scrollbar-hide">
        {/* New Chat Button */}
        <button 
          onClick={onNewChat}
          className="w-full py-3 px-4 rounded-xl border-2 border-dashed border-blue-500/30 hover:border-blue-500 hover:bg-blue-50/50 dark:hover:bg-blue-900/10 text-blue-600 dark:text-blue-400 font-bold text-sm transition-all flex items-center justify-center gap-2 group"
        >
          <Plus className="w-4 h-4 group-hover:scale-110 transition-transform" />
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
                {editingId === conv.id ? (
                  <div className="flex items-center gap-1 px-2 py-1.5 bg-white dark:bg-gray-800 rounded-lg ring-2 ring-blue-500/50">
                    <input
                      autoFocus
                      className="bg-transparent border-none outline-none text-sm w-full"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleRename(conv.id)}
                    />
                    <button onClick={() => handleRename(conv.id)} className="p-1 text-green-500 hover:bg-green-50 rounded">
                      <Check className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={cancelEditing} className="p-1 text-gray-400 hover:bg-gray-50 rounded">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <>
                    <button
                      onClick={() => onSelectConversation(conv.id)}
                      className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-all truncate pr-16 hover:bg-gray-100 dark:hover:bg-gray-800 ${
                        activeConversationId === conv.id 
                          ? "bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 font-semibold ring-1 ring-blue-500/20" 
                          : "text-gray-600 dark:text-gray-400"
                      }`}
                    >
                      {conv.title || "Untitled Chat"}
                    </button>
                    <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-l from-gray-50 dark:from-gray-900 via-gray-50 dark:via-gray-900 to-transparent pl-4">
                      <button
                        onClick={(e) => startEditing(e, conv)}
                        className="p-1.5 text-gray-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded"
                        title="Rename chat"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => handleDelete(e, conv.id)}
                        className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded"
                        title="Delete chat"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </>
                )}
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
      
      <div className="pt-4 border-t border-gray-200 dark:border-gray-800 text-xs text-gray-400 text-center font-medium">
        ⚡ Powered by LangGraph
      </div>

      {/* Drag-to-resize handle */}
      <div
        onMouseDown={startResize}
        className="absolute top-0 right-0 h-full w-1.5 cursor-col-resize group z-10"
        title="Drag to resize"
      >
        <div className="absolute right-0 top-1/2 -translate-y-1/2 h-12 w-1 rounded-full bg-gray-300 dark:bg-gray-600 opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    </div>
  );
};


