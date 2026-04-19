import { useState, useRef, useCallback } from "react";
import { API_BASE_URL, fetchApi, getToken } from "../lib/api";

export type MessageRole = "user" | "assistant" | "system" | "tool";

export interface ToolCallState {
  tool_name: string;
  description?: string;
  status: "pending" | "running" | "success" | "error";
  error?: string;
  result_summary?: string;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  tool_calls?: ToolCallState[];
}

export interface ConfirmRequest {
  confirm_id: string;
  tool_name: string;
  action_description: string;
  tool_input: any;
  message: string;
}

export function useChat(conversationId?: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamingMessage, setStreamingMessage] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  
  // Current active tool calls for the latest assistant message
  const [activeToolCalls, setActiveToolCalls] = useState<ToolCallState[]>([]);
  const [thinkingState, setThinkingState] = useState<string>("");
  
  // Pending sensitive action that needs user confirmation
  const [pendingConfirm, setPendingConfirm] = useState<ConfirmRequest | null>(null);
  
  const [currentConvId, setCurrentConvId] = useState<string | undefined>(conversationId);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (content: string, confirmed?: boolean, confirm_id?: string) => {
    if (!content.trim() && !confirmed) return;

    setError(null);
    setPendingConfirm(null);
    setActiveToolCalls([]);
    setThinkingState("Thinking...");
    setIsStreaming(true);

    const userMessageTime = new Date().getTime().toString();
    const newUserMsg: ChatMessage = { id: userMessageTime, role: "user", content };
    
    // Optimistic UI update only for regular messages
    if (!confirmed) {
      setMessages(prev => [...prev, newUserMsg]);
    }

    abortControllerRef.current = new AbortController();
    const token = getToken();

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token && { Authorization: `Bearer ${token}` })
        },
        body: JSON.stringify({
          content,
          conversation_id: currentConvId,
          confirmed,
          confirm_id,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error("Failed to send message: " + response.statusText);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let done = false;
      let streamedResponse = "";

      // [FIX]: Use a local flag for the confirm check because the state 'pendingConfirm'
      // is stale inside this turn's closure.
      let foundConfirmEvent = false;

      // Parse SSE stream
      let buffer = "";
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          buffer += decoder.decode(value, { stream: true });
        }

        const lines = buffer.split("\n\n");
        buffer = lines.pop() || ""; // keep incomplete event in buffer

        for (const line of lines) {
          if (!line.trim()) continue;
          
          const eventMatch = line.match(/^event:\s*(.*?)\s*$/m);
          const dataMatch = line.match(/^data:\s*(.*?)\s*$/m);
          
          if (!eventMatch || !dataMatch) continue;

          const event = eventMatch[1];
          if (event === "confirm_request") foundConfirmEvent = true;

          let data;
          try {
            data = JSON.parse(dataMatch[1]);
          } catch { continue; }

          switch (event) {
            case "meta":
              if (data.conversation_id) setCurrentConvId(data.conversation_id);
              break;
            case "thinking":
              setThinkingState(data.message || "Planning...");
              break;
            case "tool_start":
              setActiveToolCalls(prev => [...prev, {
                tool_name: data.tool_name,
                description: data.description,
                status: "running"
              }]);
              break;
            case "tool_result":
            case "tool_error":
              setActiveToolCalls(prev => prev.map(tc => 
                tc.tool_name === data.tool_name 
                  ? { ...tc, status: event === "tool_result" ? "success" : "error", result_summary: data.result_summary, error: data.error }
                  : tc
              ));
              break;
            case "confirm_request":
              setPendingConfirm(data);
              setIsStreaming(false); // Pause streaming UI for confirmation
              break;
            case "done":
              streamedResponse = data.response;
              setStreamingMessage(streamedResponse);
              break;
            case "error":
              setError(data.message);
              break;
          }
        }
      }

      if (streamedResponse && !foundConfirmEvent) {
         const newAssistantMsg: ChatMessage = {
           id: (new Date().getTime() + 1).toString(),
           role: "assistant",
           content: streamedResponse,
           tool_calls: [...activeToolCalls]
         };
         setMessages(prev => [...prev, newAssistantMsg]);
      }

    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setError(err.message || "An error occurred");
      }
    } finally {
      // Only clear UI if we aren't waiting for a button click
      // We check the 'activeToolCalls' or a heuristic if state is stale
      setIsStreaming(false);
      setThinkingState("");
    }
  }, [currentConvId, pendingConfirm, activeToolCalls]);

  const confirmAction = useCallback(async (approved: boolean) => {
    if (!pendingConfirm) return;
    
    const confirm_id = pendingConfirm.confirm_id;
    const originalContent = "Confirmed: " + pendingConfirm.action_description;

    try {
      await fetchApi("/api/chat/confirm", {
        method: "POST",
        body: JSON.stringify({
          confirm_id,
          approved
        })
      });
      
      // Clear pending confirm state
      setPendingConfirm(null);
      
      // Auto-resume agent turn
      if (approved) {
        sendMessage(originalContent, true, confirm_id);
      } else {
        setIsStreaming(false);
      }
      
    } catch (err: any) {
      setError("Failed to confirm action: " + err.message);
      setIsStreaming(false);
    }
  }, [pendingConfirm, sendMessage]);

  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setIsStreaming(false);
  }, []);

  const resetChat = useCallback(() => {
    setMessages([]);
    setCurrentConvId(undefined);
    setStreamingMessage("");
    setIsStreaming(false);
    setError(null);
    setPendingConfirm(null);
    setActiveToolCalls([]);
    setThinkingState("");
  }, []);

  const loadConversation = useCallback(async (id: string) => {
    setError(null);
    setIsStreaming(true); // Show loading state
    setThinkingState("Loading history...");
    
    try {
      const data = await fetchApi<any[]>(`/api/chat/conversations/${id}/messages`);
      
      const mappedMessages: ChatMessage[] = data.map(m => ({
        id: m.id,
        role: m.role,
        content: m.content,
        tool_calls: m.tool_calls?.map((tc: any) => ({
          tool_name: tc.tool_name,
          status: tc.status,
          error: tc.error,
          result_summary: tc.status === "success" ? "Task completed" : tc.error
        }))
      }));
      
      setMessages(mappedMessages);
      setCurrentConvId(id);
    } catch (err: any) {
      setError("Failed to load conversation: " + err.message);
    } finally {
      setIsStreaming(false);
      setThinkingState("");
    }
  }, []);

  const uploadFile = useCallback(async (file: File) => {
    setIsStreaming(true);
    setThinkingState("Uploading file...");
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      if (currentConvId) {
        formData.append("conversation_id", currentConvId);
      }

      const result = await fetchApi<any>("/api/chat/upload", {
        method: "POST",
        body: formData
      });

      // The backend now persists this to the DB history and returns the conversation_id.
      // Sync the state and refresh the view.
      if (result.conversation_id) {
        if (!currentConvId) {
          setCurrentConvId(result.conversation_id);
        }
        await loadConversation(result.conversation_id);
      }
      return true;
    } catch (err: any) {
      setError("Failed to upload file: " + err.message);
      return false;
    } finally {
      setIsStreaming(false);
      setThinkingState("");
    }
  }, []);

  return {
    messages,
    setMessages,
    sendMessage,
    isStreaming,
    streamingMessage,
    activeToolCalls,
    thinkingState,
    pendingConfirm,
    confirmAction,
    error,
    currentConvId,
    stopStreaming,
    resetChat,
    loadConversation,
    uploadFile
  };
}
