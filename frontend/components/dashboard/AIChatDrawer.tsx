'use client';

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  MessageSquare, 
  X, 
  Send, 
  Bot, 
  User, 
  Loader2, 
  Sparkles,
  TrendingUp,
  ShoppingBag,
  Tag,
  ChevronRight
} from 'lucide-react';
import { useAIChat, AIProductSuggestion, AICampaignIdea } from '@/lib/hooks/useAIChat';
import { ChatMessage } from '@/lib/hooks/useAIChat';

interface AIChatDrawerProps {
  merchantId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function AIChatDrawer({ merchantId, isOpen, onClose }: AIChatDrawerProps) {
  const { messages, isLoading, isThinking, sendMessage, clearChat } = useAIChat(merchantId);
  const [inputValue, setInputValue] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isThinking]);

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;
    const message = inputValue;
    setInputValue('');
    try {
      await sendMessage(message);
    } catch (error) {
      console.error('Failed to send message:', error);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const quickSuggestions = [
    "What inventory is at risk?",
    "Suggest a flash sale campaign",
    "Which products should I discount?",
    "Forecast next month's revenue",
  ];

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40"
          />

          {/* Drawer */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="fixed right-0 top-0 bottom-0 w-full max-w-lg bg-[hsl(var(--bg-primary))] border-l border-[hsl(var(--border-default))] z-50 shadow-2xl flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-[hsl(var(--border-subtle))]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[hsl(var(--accent-primary))] to-[hsl(var(--accent-secondary))] flex items-center justify-center">
                  <Bot className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h3 className="font-semibold text-[hsl(var(--text-primary))]">
                    Cephly AI Assistant
                  </h3>
                  <div className="flex items-center gap-1.5 text-xs text-emerald-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    Online
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={clearChat}
                  className="p-2 rounded-lg hover:bg-[hsl(var(--bg-secondary))] text-[hsl(var(--text-tertiary))] hover:text-[hsl(var(--text-primary))] transition-colors text-sm"
                >
                  Clear
                </button>
                <button
                  onClick={onClose}
                  className="p-2 rounded-lg hover:bg-[hsl(var(--bg-secondary))] text-[hsl(var(--text-tertiary))] hover:text-[hsl(var(--text-primary))] transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div 
              ref={scrollRef}
              className="flex-1 overflow-y-auto p-4 space-y-4"
            >
              {messages.length === 0 && !isLoading && (
                <div className="space-y-4">
                  <div className="text-center py-8">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[hsl(var(--accent-primary)/0.2)] to-[hsl(var(--accent-secondary)/0.1)] flex items-center justify-center mx-auto mb-4">
                      <Sparkles className="w-8 h-8 text-[hsl(var(--accent-primary))]" />
                    </div>
                    <h4 className="text-lg font-semibold text-[hsl(var(--text-primary))] mb-2">
                      How can I help you?
                    </h4>
                    <p className="text-sm text-[hsl(var(--text-secondary))] max-w-xs mx-auto">
                      Ask me about your inventory, campaigns, or business insights. I&apos;ll analyze your data and provide actionable recommendations.
                    </p>
                  </div>

                  {/* Quick suggestions */}
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-[hsl(var(--text-tertiary))] uppercase tracking-wider px-1">
                      Quick Suggestions
                    </p>
                    {quickSuggestions.map((suggestion, i) => (
                      <button
                        key={i}
                        onClick={() => {
                          setInputValue(suggestion);
                        }}
                        className="w-full text-left p-3 rounded-xl bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-subtle))] hover:border-[hsl(var(--accent-primary)/0.3)] hover:bg-[hsl(var(--accent-primary)/0.05)] transition-all group"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-[hsl(var(--text-secondary))] group-hover:text-[hsl(var(--text-primary))]">
                            {suggestion}
                          </span>
                          <ChevronRight className="w-4 h-4 text-[hsl(var(--text-tertiary))] group-hover:text-[hsl(var(--accent-primary))]" />
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((msg, idx) => (
                <ChatMessageComponent key={idx} message={msg} />
              ))}

              {/* Thinking indicator */}
              {isThinking && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex gap-3"
                >
                  <div className="w-8 h-8 rounded-lg bg-[hsl(var(--bg-tertiary))] flex items-center justify-center shrink-0">
                    <Sparkles className="w-4 h-4 text-[hsl(var(--accent-primary))]" />
                  </div>
                  <div className="bg-[hsl(var(--bg-secondary))] rounded-2xl rounded-tl-sm px-4 py-3 border border-[hsl(var(--border-subtle))]">
                    <div className="flex items-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin text-[hsl(var(--accent-primary))]" />
                      <span className="text-sm text-[hsl(var(--text-secondary))]">
                        Analyzing your data...
                      </span>
                    </div>
                  </div>
                </motion.div>
              )}
            </div>

            {/* Input */}
            <div className="p-4 border-t border-[hsl(var(--border-subtle))] bg-[hsl(var(--bg-secondary))]">
              <div className="relative">
                <input
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={isLoading}
                  type="text"
                  placeholder="Ask about your inventory, campaigns, or insights..."
                  className="w-full bg-[hsl(var(--bg-primary))] border border-[hsl(var(--border-default))] rounded-xl py-3 pl-4 pr-12 text-sm text-[hsl(var(--text-primary))] placeholder:text-[hsl(var(--text-tertiary))] focus:outline-none focus:border-[hsl(var(--accent-primary)/0.5)] transition-colors"
                />
                <button
                  onClick={handleSend}
                  disabled={!inputValue.trim() || isLoading}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-[hsl(var(--accent-primary))] text-white hover:bg-[hsl(var(--accent-primary)/0.9)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </button>
              </div>
              <p className="text-xs text-[hsl(var(--text-tertiary))] mt-2 text-center">
                Cephly AI analyzes your data to provide personalized recommendations
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function ChatMessageComponent({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
    >
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
        isUser 
          ? 'bg-[hsl(var(--accent-primary))]' 
          : 'bg-[hsl(var(--bg-tertiary))]'
      }`}>
        {isUser ? (
          <User className="w-4 h-4 text-white" />
        ) : (
          <Bot className="w-4 h-4 text-[hsl(var(--accent-primary))]" />
        )}
      </div>

      <div className={`flex flex-col max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
          isUser 
            ? 'bg-[hsl(var(--accent-primary))] text-white rounded-tr-sm' 
            : 'bg-[hsl(var(--bg-secondary))] text-[hsl(var(--text-primary))] rounded-tl-sm border border-[hsl(var(--border-subtle))]'
        }`}>
          <MarkdownContent content={message.content} />
        </div>

        {/* Suggestions */}
        {message.suggestions && message.suggestions.length > 0 && (
          <div className="mt-3 space-y-2 w-full">
            {message.suggestions.map((suggestion) => (
              <ProductSuggestionCard key={suggestion.product_id} suggestion={suggestion} />
            ))}
          </div>
        )}

        {/* Campaign Idea */}
        {message.campaign_idea && (
          <div className="mt-3 w-full">
            <CampaignIdeaCard idea={message.campaign_idea} />
          </div>
        )}

        <span className="text-[10px] text-[hsl(var(--text-tertiary))] mt-1">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>
    </motion.div>
  );
}

// Simple markdown-like content renderer (no external deps)
function MarkdownContent({ content }: { content: string }) {
  // Split content by newlines and process each line
  const lines = content.split('\n');
  
  return (
    <div className="space-y-2">
      {lines.map((line, idx) => {
        // Headers
        if (line.startsWith('### ')) {
          return <h3 key={idx} className="font-bold text-base mt-2">{line.replace('### ', '')}</h3>;
        }
        if (line.startsWith('## ')) {
          return <h2 key={idx} className="font-bold text-lg mt-3">{line.replace('## ', '')}</h2>;
        }
        if (line.startsWith('# ')) {
          return <h1 key={idx} className="font-bold text-xl mt-4">{line.replace('# ', '')}</h1>;
        }
        
        // Bold text **text**
        let processedLine = line;
        const boldPattern = /\*\*(.*?)\*\*/g;
        if (boldPattern.test(line)) {
          const parts = line.split(boldPattern);
          return (
            <p key={idx}>
              {parts.map((part, pidx) => 
                pidx % 2 === 1 ? <strong key={pidx} className="font-semibold">{part}</strong> : part
              )}
            </p>
          );
        }
        
        // Code `text`
        const codePattern = /`([^`]+)`/g;
        if (codePattern.test(line)) {
          const parts = line.split(codePattern);
          return (
            <p key={idx}>
              {parts.map((part, pidx) => 
                pidx % 2 === 1 ? (
                  <code key={pidx} className="bg-white/10 px-1.5 py-0.5 rounded text-xs">{part}</code>
                ) : part
              )}
            </p>
          );
        }
        
        // Empty lines
        if (!line.trim()) {
          return <div key={idx} className="h-2" />;
        }
        
        // List items
        if (line.startsWith('- ') || line.startsWith('* ')) {
          return (
            <div key={idx} className="flex items-start gap-2">
              <span className="text-[hsl(var(--accent-primary))] mt-1">•</span>
              <span>{line.substring(2)}</span>
            </div>
          );
        }
        
        // Regular paragraph
        return <p key={idx}>{processedLine}</p>;
      })}
    </div>
  );
}

function ProductSuggestionCard({ suggestion }: { suggestion: AIProductSuggestion }) {
  return (
    <div className="p-3 rounded-xl bg-[hsl(var(--bg-tertiary))] border border-[hsl(var(--border-subtle))] hover:border-[hsl(var(--accent-primary)/0.3)] transition-colors">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-lg bg-[hsl(var(--accent-primary)/0.1)] flex items-center justify-center shrink-0">
          <ShoppingBag className="w-5 h-5 text-[hsl(var(--accent-primary))]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <h5 className="font-medium text-[hsl(var(--text-primary))] text-sm truncate">
              {suggestion.name}
            </h5>
            <span className="text-xs font-bold text-emerald-400">
              {suggestion.confidence}% match
            </span>
          </div>
          <p className="text-xs text-[hsl(var(--text-secondary))] mt-1 line-clamp-2">
            {suggestion.reason}
          </p>
          {suggestion.suggested_price && (
            <div className="flex items-center gap-2 mt-2">
              <span className="text-xs text-[hsl(var(--text-tertiary))] line-through">
                ${suggestion.current_price.toFixed(2)}
              </span>
              <span className="text-sm font-bold text-emerald-400">
                ${suggestion.suggested_price.toFixed(2)}
              </span>
              <Tag className="w-3 h-3 text-amber-400" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CampaignIdeaCard({ idea }: { idea: AICampaignIdea }) {
  return (
    <div className="p-4 rounded-xl bg-gradient-to-br from-[hsl(var(--accent-primary)/0.1)] to-[hsl(var(--accent-secondary)/0.05)] border border-[hsl(var(--accent-primary)/0.2)]">
      <div className="flex items-center gap-2 mb-2">
        <TrendingUp className="w-4 h-4 text-[hsl(var(--accent-primary))]" />
        <span className="text-xs font-bold text-[hsl(var(--accent-primary))] uppercase tracking-wider">
          Campaign Idea
        </span>
        <span className="text-xs font-bold text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded-full">
          {idea.confidence}% confidence
        </span>
      </div>
      <h4 className="font-semibold text-[hsl(var(--text-primary))] mb-1">
        {idea.title}
      </h4>
      <p className="text-sm text-[hsl(var(--text-secondary))] mb-3">
        {idea.description}
      </p>
      <div className="flex items-center justify-between text-xs">
        <div className="flex gap-3">
          <span className="text-[hsl(var(--text-tertiary))]">
            Target: <span className="text-[hsl(var(--text-primary))]">{idea.target_segment}</span>
          </span>
          <span className="text-[hsl(var(--text-tertiary))]">
            Discount: <span className="text-emerald-400">{idea.discount_percentage}%</span>
          </span>
        </div>
        <span className="font-bold text-emerald-400">
          +{idea.expected_lift}% lift
        </span>
      </div>
    </div>
  );
}
