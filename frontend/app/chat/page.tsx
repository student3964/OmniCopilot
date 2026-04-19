"use client";

import React, { useState, useRef } from "react";
import { Sidebar } from "../../components/layout/Sidebar";
import { Header } from "../../components/layout/Header";
import { ChatWindow } from "../../components/chat/ChatWindow";
import { useChat } from "../../hooks/useChat";

export default function ChatPage() {
  const chatState = useChat();
  const [inputMessage, setInputMessage] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || chatState.isStreaming || chatState.pendingConfirm) return;
    
    chatState.sendMessage(inputMessage);
    setInputMessage("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(e as unknown as React.FormEvent);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await chatState.uploadFile(file);
      // Reset input so searching the same file again triggers change
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-white dark:bg-black text-gray-900 dark:text-gray-100 font-sans">
      <Sidebar 
        onNewChat={chatState.resetChat}
        onSelectConversation={chatState.loadConversation}
        activeConversationId={chatState.currentConvId}
      />
      
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        
        <main className="flex-1 flex flex-col overflow-hidden p-6 gap-4">
          {/* Main Chat Area */}
          <div className="flex-1 overflow-hidden">
            <ChatWindow chatState={chatState} />
          </div>

          {/* Input Box */}
          <div className="w-full">
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleFileChange} 
              className="hidden" 
              accept=".pdf,.txt,.md,.py,.js,.ts"
            />
            <form onSubmit={handleSend} className="relative w-full shadow-sm rounded-xl overflow-hidden border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 transition-shadow focus-within:ring-2 focus-within:ring-blue-500/50">
              <button
                type="button"
                onClick={handleUploadClick}
                disabled={chatState.isStreaming || !!chatState.pendingConfirm}
                className="absolute left-2 top-0 bottom-0 px-2 text-gray-400 hover:text-blue-600 transition disabled:opacity-30 disabled:hover:text-gray-400"
                title="Upload file from system"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
                </svg>
              </button>
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={chatState.isStreaming || !!chatState.pendingConfirm}
                placeholder={chatState.pendingConfirm ? "Please confirm the action above first..." : "Ask Omni Copilot..."}
                className="w-full resize-none bg-transparent py-4 pl-12 pr-14 outline-none max-h-32 min-h-[60px] text-sm disabled:opacity-50"
                rows={1}
              />
              <div className="absolute right-3 bottom-0 top-0 flex items-center">
                 {!chatState.isStreaming && !chatState.pendingConfirm ? (
                    <button 
                      type="submit" 
                      disabled={!inputMessage.trim()}
                      className="p-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:hover:bg-blue-600 transition shadow"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                        <path d="M3.478 2.404a.75.75 0 00-.926.941l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.404z" />
                      </svg>
                    </button>
                 ) : (
                    <button 
                      type="button" 
                      onClick={chatState.stopStreaming}
                      disabled={!!chatState.pendingConfirm}
                      className="p-2 rounded-lg bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 transition disabled:opacity-0"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                        <path fillRule="evenodd" d="M4.5 7.5a3 3 0 013-3h9a3 3 0 013 3v9a3 3 0 01-3 3h-9a3 3 0 01-3-3v-9z" clipRule="evenodd" />
                      </svg>
                    </button>
                 )}
              </div>
            </form>
            <div className="text-center mt-2 text-[10px] text-gray-400">
              Omni Copilot can make mistakes. Check important info.
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
