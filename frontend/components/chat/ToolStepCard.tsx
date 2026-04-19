import React from "react";
import { ToolCallState } from "../../hooks/useChat";

interface ToolStepCardProps {
  toolCall: ToolCallState;
}

export const ToolStepCard: React.FC<ToolStepCardProps> = ({ toolCall }) => {
  const { tool_name, status, description, result_summary, error } = toolCall;

  return (
    <div className="bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-xl p-3 shadow-sm flex flex-col gap-1 text-sm animate-fade-in transition-all">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {status === "pending" && <span className="text-gray-400">⏳</span>}
          {status === "running" && (
             <svg className="animate-spin h-4 w-4 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
               <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
               <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
             </svg>
          )}
          {status === "success" && <span className="text-green-500">✅</span>}
          {status === "error" && <span className="text-red-500">❌</span>}
          
          <span className="font-semibold text-gray-700 dark:text-gray-300">
            {description || tool_name.replace(/_/g, ' ')}
          </span>
        </div>
      </div>

      {status === "success" && result_summary && (
        <div className="text-gray-500 dark:text-gray-400 pl-6 text-xs border-l-2 ml-1 mt-1 border-gray-100 dark:border-gray-700">
          {result_summary}
        </div>
      )}

      {status === "error" && error && (
        <div className="text-red-400 pl-6 text-xs border-l-2 ml-1 mt-1 border-red-100">
          {error}
        </div>
      )}
    </div>
  );
};
