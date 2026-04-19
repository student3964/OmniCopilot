import React, { useEffect, useRef } from "react";
import { useChat } from "../../hooks/useChat";
import { MessageBubble } from "./MessageBubble";
import { ActionConfirm } from "./ActionConfirm";

interface ChatWindowProps {
  chatState: ReturnType<typeof useChat>;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({ chatState }) => {
  const { 
    messages, 
    isStreaming, 
    streamingMessage, 
    activeToolCalls, 
    thinkingState,
    pendingConfirm,
    confirmAction,
    error
  } = chatState;

  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingMessage, activeToolCalls, pendingConfirm]);

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900 rounded-xl overflow-hidden shadow-inner border border-gray-100 dark:border-gray-800">
      
      {/* Messages Area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 scroll-smooth">
        
        {messages.length === 0 && !isStreaming && (
          <div className="h-full flex flex-col items-center justify-center text-gray-400">
            <div className="text-4xl mb-4">💬</div>
            <p className="text-lg font-medium">How can I help you today?</p>
            <p className="text-sm mt-2 text-gray-500">Connect your apps in the sidebar and ask me anything.</p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble 
            key={msg.id} 
            role={msg.role} 
            content={msg.content} 
            toolCalls={msg.tool_calls} 
          />
        ))}

        {/* Current Streaming State */}
        {isStreaming && (
          <div className="mb-6 flex flex-col items-start w-full">
            
            {/* Thinking / Tool Execution Indicator */}
            {thinkingState && activeToolCalls.length === 0 && (
               <div className="text-sm text-gray-500 mb-4 animate-pulse flex items-center gap-2">
                 <span>🤔</span> {thinkingState}
               </div>
            )}

            {/* Active Tool Calls rendering directly via MessageBubble (faking Assistant role) */}
            {(activeToolCalls.length > 0 || streamingMessage) && (
              <MessageBubble 
                role="assistant" 
                content={streamingMessage} 
                toolCalls={activeToolCalls} 
              />
            )}
          </div>
        )}

        {/* Action Confirmation Request */}
        {pendingConfirm && (
          <ActionConfirm request={pendingConfirm} onConfirm={confirmAction} />
        )}

        {/* Error State */}
        {error && (
           <div className="mt-4 p-4 bg-red-50 text-red-600 rounded-lg border border-red-100 text-sm">
             <strong>Error:</strong> {error}
           </div>
        )}
      </div>

    </div>
  );
};
