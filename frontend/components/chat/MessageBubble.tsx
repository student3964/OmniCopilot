import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { MessageRole, ToolCallState } from "../../hooks/useChat";
import { ToolStepCard } from "./ToolStepCard";

interface MessageBubbleProps {
  role: MessageRole;
  content: string;
  toolCalls?: ToolCallState[];
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ role, content, toolCalls }) => {
  const isUser = role === "user";
  const isSystem = role === "system";

  if (isSystem) {
    // Special rendering for file uploads
    const fileName = content.split("\n")[0].replace("Uploaded file: ", "");
    return (
      <div className="flex w-full justify-center my-4">
        <div className="flex items-center gap-3 px-4 py-2 bg-gray-100 dark:bg-gray-800 rounded-full border border-gray-200 dark:border-gray-700 shadow-sm animate-in fade-in duration-500">
          <div className="text-xl">📄</div>
          <div className="flex flex-col">
             <span className="text-xs font-black text-gray-500 uppercase tracking-widest">Document Attached</span>
             <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">{fileName}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"} mb-6 animate-in slide-in-from-bottom-2 duration-300`}>
      <div className={`flex flex-col gap-2 max-w-[85%] ${isUser ? "items-end" : "items-start"}`}>
        
        {/* Assistant Tool Calls */}
        {!isUser && toolCalls && toolCalls.length > 0 && (
          <div className="flex flex-col gap-2 w-full max-w-md mb-2">
            {toolCalls.map((tc, idx) => (
              <ToolStepCard key={idx} toolCall={tc} />
            ))}
          </div>
        )}

        {/* Message Bubble */}
        {(content || (isUser)) && (
          <div
            className={`px-5 py-3 rounded-2xl shadow-sm border text-[15px] leading-relaxed prose dark:prose-invert
              ${isUser 
                ? "bg-blue-600 text-white rounded-br-sm border-transparent prose-p:text-white prose-headings:text-white" 
                : "bg-white text-gray-800 rounded-bl-sm border-gray-200 dark:bg-gray-800 dark:text-gray-100 dark:border-gray-700"
              }`}
          >
            {isUser ? (
              <div className="whitespace-pre-wrap">{content}</div>
            ) : (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
