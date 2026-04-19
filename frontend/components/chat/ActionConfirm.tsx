import React from "react";
import { ConfirmRequest } from "../../hooks/useChat";

interface ActionConfirmProps {
  request: ConfirmRequest;
  onConfirm: (approved: boolean) => void;
}

export const ActionConfirm: React.FC<ActionConfirmProps> = ({ request, onConfirm }) => {
  return (
    <div className="flex w-full justify-start mb-6">
      <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 rounded-xl p-5 max-w-[85%] shadow-sm animate-slide-up">
        
        <div className="flex items-start gap-3 mb-4 text-amber-800 dark:text-amber-200">
          <span className="text-xl mt-0.5">⚠️</span>
          <div>
            <h4 className="font-bold mb-1">Action Required</h4>
            <div className="text-sm prose prose-amber dark:prose-invert" 
               dangerouslySetInnerHTML={{ __html: request.message?.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') || request.action_description }}>
            </div>
          </div>
        </div>

        <div className="bg-white/60 dark:bg-black/20 rounded p-3 text-xs font-mono text-gray-700 dark:text-gray-300 mb-5 overflow-auto max-h-40 border border-amber-100 dark:border-amber-900/50">
          {JSON.stringify(request.tool_input, null, 2)}
        </div>

        <div className="flex gap-3 justify-end">
          <button 
            onClick={() => onConfirm(false)}
            className="px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
          >
            Reject
          </button>
          <button 
            onClick={() => onConfirm(true)}
            className="px-4 py-2 text-sm font-medium bg-amber-500 hover:bg-amber-600 text-white rounded-lg transition-colors shadow-sm"
          >
            Approve Action
          </button>
        </div>
      </div>
    </div>
  );
};
