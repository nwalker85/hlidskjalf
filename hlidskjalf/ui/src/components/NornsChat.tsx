"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  MessageCircle, 
  Send, 
  X, 
  Loader2,
  Sparkles,
  Clock,
  Eye,
  Wand2
} from "lucide-react";

interface Message {
  id: string;
  role: "user" | "norn";
  content: string;
  norn?: "urd" | "verdandi" | "skuld";
  timestamp: Date;
}

const NORN_INFO = {
  urd: {
    name: "Urðr",
    title: "That which has become",
    icon: Clock,
    color: "text-amber-400",
    bgColor: "bg-amber-500/10",
    borderColor: "border-amber-500/30",
  },
  verdandi: {
    name: "Verðandi",
    title: "That which is happening",
    icon: Eye,
    color: "text-huginn-400",
    bgColor: "bg-huginn-500/10",
    borderColor: "border-huginn-500/30",
  },
  skuld: {
    name: "Skuld",
    title: "That which shall be",
    icon: Wand2,
    color: "text-muninn-400",
    bgColor: "bg-muninn-500/10",
    borderColor: "border-muninn-500/30",
  },
};

const SUGGESTED_QUESTIONS = [
  "What is the status of my deployments?",
  "Show me the port allocations",
  "Are there any health issues?",
  "Help me deploy a new project",
];

export function NornsChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (content: string) => {
    if (!content.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: content.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/v1/norns/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: content,
          thread_id: threadId,
        }),
      });

      if (!response.ok) throw new Error("Failed to get response");

      const data = await response.json();
      
      setThreadId(data.thread_id);

      const nornMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "norn",
        content: data.response,
        norn: data.current_norn as "urd" | "verdandi" | "skuld",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, nornMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "norn",
        content: "The threads of fate are tangled... I cannot reach the Well of Urðr at this moment. Please try again.",
        norn: "verdandi",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  return (
    <>
      {/* Toggle Button */}
      <motion.button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 p-4 bg-gradient-to-br from-odin-500 to-odin-600 
                   rounded-full shadow-lg shadow-odin-500/25 hover:shadow-odin-500/40 
                   transition-shadow duration-300"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Sparkles className="w-6 h-6 text-raven-950" />
      </motion.button>

      {/* Chat Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, x: 400 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 400 }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 bottom-0 w-[420px] z-50 
                       bg-raven-950/95 backdrop-blur-xl border-l border-raven-800/50
                       flex flex-col shadow-2xl"
          >
            {/* Header */}
            <div className="p-4 border-b border-raven-800/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="relative">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-odin-400 to-muninn-500 
                                    flex items-center justify-center">
                      <Sparkles className="w-5 h-5 text-raven-950" />
                    </div>
                    <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-healthy 
                                     rounded-full border-2 border-raven-950 status-breathe" />
                  </div>
                  <div>
                    <h2 className="font-display font-semibold text-raven-100">The Norns</h2>
                    <p className="text-xs text-raven-500">Weavers of Fate</p>
                  </div>
                </div>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-2 hover:bg-raven-800/50 rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-raven-400" />
                </button>
              </div>

              {/* Norn Indicators */}
              <div className="flex gap-2 mt-3">
                {Object.entries(NORN_INFO).map(([key, info]) => (
                  <div
                    key={key}
                    className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs
                               ${info.bgColor} ${info.color} border ${info.borderColor}`}
                  >
                    <info.icon className="w-3 h-3" />
                    <span>{info.name}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="text-center py-8">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-raven-800/50 
                                  flex items-center justify-center">
                    <MessageCircle className="w-8 h-8 text-raven-500" />
                  </div>
                  <p className="text-raven-400 text-sm mb-4">
                    The Norns await your questions about the Nine Realms.
                  </p>
                  <div className="space-y-2">
                    {SUGGESTED_QUESTIONS.map((q, i) => (
                      <button
                        key={i}
                        onClick={() => sendMessage(q)}
                        className="block w-full text-left px-3 py-2 text-sm text-raven-300
                                   bg-raven-800/30 hover:bg-raven-800/50 rounded-lg
                                   border border-raven-700/50 transition-colors"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((message) => (
                  <motion.div
                    key={message.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    {message.role === "norn" && message.norn && (
                      <div className="flex-shrink-0 mr-2">
                        <div className={`w-8 h-8 rounded-full ${NORN_INFO[message.norn].bgColor}
                                        flex items-center justify-center`}>
                          {(() => {
                            const Icon = NORN_INFO[message.norn].icon;
                            return <Icon className={`w-4 h-4 ${NORN_INFO[message.norn].color}`} />;
                          })()}
                        </div>
                      </div>
                    )}
                    <div
                      className={`max-w-[80%] px-4 py-2 rounded-2xl ${
                        message.role === "user"
                          ? "bg-odin-500 text-raven-950"
                          : `${NORN_INFO[message.norn || "verdandi"].bgColor} 
                             border ${NORN_INFO[message.norn || "verdandi"].borderColor}`
                      }`}
                    >
                      {message.role === "norn" && message.norn && (
                        <div className={`text-xs ${NORN_INFO[message.norn].color} mb-1 font-medium`}>
                          {NORN_INFO[message.norn].name}
                        </div>
                      )}
                      <p className={`text-sm whitespace-pre-wrap ${
                        message.role === "user" ? "" : "text-raven-200"
                      }`}>
                        {message.content}
                      </p>
                    </div>
                  </motion.div>
                ))
              )}

              {isLoading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center gap-2 text-raven-400"
                >
                  <div className="w-8 h-8 rounded-full bg-raven-800/50 flex items-center justify-center">
                    <Loader2 className="w-4 h-4 animate-spin" />
                  </div>
                  <span className="text-sm italic">The Norns are weaving...</span>
                </motion.div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form onSubmit={handleSubmit} className="p-4 border-t border-raven-800/50">
              <div className="flex gap-2">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask the Norns..."
                  disabled={isLoading}
                  className="flex-1 input"
                />
                <button
                  type="submit"
                  disabled={!input.trim() || isLoading}
                  className="btn-primary p-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

