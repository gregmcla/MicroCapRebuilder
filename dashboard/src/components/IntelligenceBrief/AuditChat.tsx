/** AI Portfolio Audit Brief + chat interface — full GSCOTT tab. */

import { useState, useRef, useEffect } from "react";
import { api } from "../../lib/api";
import type { ChatMessage } from "../../lib/types";

const DATA_FONT = "'JetBrains Mono', 'SF Mono', monospace";
const PROSE_FONT = "-apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif";

// ---------- FormattedText (markdown-lite: bold **text**, newlines) ----------

function FormattedText({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div style={{ lineHeight: 1.75 }}>
      {lines.map((line, i) => {
        if (!line.trim()) return <div key={i} style={{ height: "8px" }} />;
        const parts = line.split(/(\*\*[^*]+\*\*)/g);
        const rendered = parts.map((p, j) => {
          if (p.startsWith("**") && p.endsWith("**")) {
            return (
              <strong key={j} style={{ color: "#e8e8f8", fontWeight: 600 }}>
                {p.slice(2, -2)}
              </strong>
            );
          }
          return <span key={j}>{p}</span>;
        });
        return (
          <p key={i} style={{
            margin: "0 0 2px",
            fontSize: "13px",
            fontFamily: PROSE_FONT,
            color: "#d8d8f0",
          }}>
            {rendered}
          </p>
        );
      })}
    </div>
  );
}

// ---------- Audit Brief sub-component ----------

function AuditBrief({ portfolioId }: { portfolioId: string }) {
  const [brief, setBrief] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fetched = useRef(false);

  useEffect(() => {
    if (fetched.current) return;
    fetched.current = true;
    setLoading(true);
    api.getAuditBrief(portfolioId)
      .then(r => {
        setBrief(r.brief);
        if (r.error) setError(r.error);
      })
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, [portfolioId]);

  // Skeleton loading
  if (loading) {
    return (
      <div style={{
        margin: "20px 24px 0",
        background: "rgba(124,92,252,0.06)",
        border: "1px solid rgba(124,92,252,0.22)",
        borderTop: "1px solid rgba(124,92,252,0.35)",
        borderLeft: "4px solid #7c5cfc",
        borderRadius: "10px",
        padding: "20px 24px",
        boxShadow: "inset 0 1px 0 rgba(124,92,252,0.2), 0 4px 20px rgba(0,0,0,0.5), 0 0 40px rgba(124,92,252,0.08)",
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
          <span style={{
            fontSize: "9px", letterSpacing: "0.12em", fontWeight: 700,
            background: "rgba(124,92,252,0.2)", color: "#7c5cfc",
            border: "1px solid rgba(124,92,252,0.3)", borderRadius: "3px",
            padding: "2px 8px", fontFamily: DATA_FONT,
          }}>
            GSCOTT
          </span>
          <span style={{ fontSize: "10px", color: "rgba(255,255,255,0.5)", letterSpacing: "0.1em", marginLeft: "8px", fontFamily: PROSE_FONT }}>
            PORTFOLIO AUDIT
          </span>
        </div>
        {[100, 85, 60].map((w, i) => (
          <div key={i} style={{
            background: "linear-gradient(90deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 100%)",
            backgroundSize: "200% 100%",
            animation: "shimmer 1.5s ease-in-out infinite",
            borderRadius: "4px",
            height: "12px",
            marginBottom: "8px",
            width: `${w}%`,
          }} />
        ))}
      </div>
    );
  }

  // Error state
  if (error && !brief) {
    return (
      <div style={{
        margin: "20px 24px 0",
        background: "rgba(124,92,252,0.06)",
        border: "1px solid rgba(124,92,252,0.22)",
        borderTop: "1px solid rgba(124,92,252,0.35)",
        borderLeft: "4px solid #7c5cfc",
        borderRadius: "10px",
        padding: "20px 24px",
        boxShadow: "inset 0 1px 0 rgba(124,92,252,0.2), 0 4px 20px rgba(0,0,0,0.5), 0 0 40px rgba(124,92,252,0.08)",
        flexShrink: 0,
      }}>
        <span style={{ fontSize: "12px", color: "#f87171", fontFamily: PROSE_FONT }}>
          {error}
        </span>
      </div>
    );
  }

  if (!brief) return null;

  return (
    <div style={{
      margin: "20px 24px 0",
      background: "rgba(124,92,252,0.06)",
      border: "1px solid rgba(124,92,252,0.22)",
      borderTop: "1px solid rgba(124,92,252,0.35)",
      borderLeft: "4px solid #7c5cfc",
      borderRadius: "10px",
      padding: "20px 24px",
      boxShadow: "inset 0 1px 0 rgba(124,92,252,0.2), 0 4px 20px rgba(0,0,0,0.5), 0 0 40px rgba(124,92,252,0.08)",
      flexShrink: 0,
      maxHeight: "280px",
      overflowY: "auto" as const,
    }}>
      {/* Top row */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "14px" }}>
        <span style={{
          fontSize: "9px", letterSpacing: "0.12em", fontWeight: 700,
          background: "rgba(124,92,252,0.2)", color: "#7c5cfc",
          border: "1px solid rgba(124,92,252,0.3)", borderRadius: "3px",
          padding: "2px 8px", fontFamily: DATA_FONT,
        }}>
          GSCOTT
        </span>
        <span style={{
          fontSize: "10px", color: "rgba(255,255,255,0.5)",
          letterSpacing: "0.1em", marginLeft: "8px", fontFamily: PROSE_FONT,
        }}>
          PORTFOLIO AUDIT
        </span>
        <span style={{
          fontSize: "9px", color: "rgba(255,255,255,0.2)",
          marginLeft: "auto", fontFamily: PROSE_FONT,
        }}>
          &middot; ask follow-up questions below
        </span>
      </div>

      {/* Audit text */}
      <div style={{ fontFamily: PROSE_FONT, fontSize: "13px", lineHeight: 1.75, color: "#d8d8f0" }}>
        <FormattedText text={brief} />
      </div>
    </div>
  );
}

// ---------- Main AuditChat component ----------

interface Props { portfolioId: string }

const SUGGESTIONS = [
  "Which positions should I consider closing?",
  "Is my portfolio executing its DNA?",
  "What's my biggest unacknowledged risk?",
  "Which factor is working best right now?",
  "Should I rotate sectors?",
];

export default function AuditChat({ portfolioId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [focusedInput, setFocusedInput] = useState(false);
  const [hoveredSuggestion, setHoveredSuggestion] = useState<number | null>(null);
  const [hoveredSend, setHoveredSend] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send() {
    const content = input.trim();
    if (!content || sending) return;
    const userMsg: ChatMessage = { role: "user", content };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setSending(true);
    try {
      const res = await api.postIntelligenceChat(portfolioId, [...messages, userMsg]);
      setMessages(prev => [...prev, { role: "assistant", content: res.reply }]);
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "Error connecting to GScott. Try again." }]);
    } finally {
      setSending(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  const sendDisabled = !input.trim() || sending;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>

      {/* Audit brief at top */}
      <AuditBrief portfolioId={portfolioId} />

      {/* Divider */}
      <div style={{ margin: "0 24px", borderTop: "1px solid rgba(255,255,255,0.06)", marginTop: "20px" }} />

      {/* Chat messages area */}
      <div
        className="ib-scroll"
        style={{
          flex: 1,
          overflowY: "auto" as const,
          padding: "16px 24px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        {messages.length === 0 ? (
          /* Empty chat state */
          <div style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            gap: "20px",
          }}>
            <span style={{
              fontSize: "10px",
              letterSpacing: "0.12em",
              color: "rgba(255,255,255,0.25)",
              fontFamily: PROSE_FONT,
            }}>
              ASK GSCOTT ANYTHING ABOUT THIS PORTFOLIO
            </span>
            <div style={{
              display: "flex",
              flexWrap: "wrap" as const,
              gap: "8px",
              justifyContent: "center",
              maxWidth: "600px",
            }}>
              {SUGGESTIONS.map((s, idx) => (
                <button
                  key={s}
                  onClick={() => { setInput(s); inputRef.current?.focus(); }}
                  onMouseEnter={() => setHoveredSuggestion(idx)}
                  onMouseLeave={() => setHoveredSuggestion(null)}
                  style={{
                    fontSize: "11px",
                    padding: "6px 14px",
                    borderRadius: "20px",
                    background: hoveredSuggestion === idx ? "rgba(124,92,252,0.15)" : "rgba(124,92,252,0.08)",
                    border: hoveredSuggestion === idx ? "1px solid rgba(124,92,252,0.35)" : "1px solid rgba(124,92,252,0.2)",
                    color: hoveredSuggestion === idx ? "#917aff" : "rgba(255,255,255,0.5)",
                    cursor: "pointer",
                    transition: "all 150ms ease",
                    fontFamily: PROSE_FONT,
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: msg.role === "user" ? "75%" : "80%",
                }}
              >
                <div style={msg.role === "user" ? {
                  background: "rgba(124,92,252,0.1)",
                  border: "1px solid rgba(124,92,252,0.18)",
                  borderRadius: "12px 12px 4px 12px",
                  padding: "10px 14px",
                } : {
                  background: "rgba(255,255,255,0.028)",
                  border: "1px solid rgba(255,255,255,0.07)",
                  borderLeft: "3px solid rgba(124,92,252,0.5)",
                  borderRadius: "4px 12px 12px 12px",
                  padding: "12px 16px",
                }}>
                  {msg.role === "assistant" ? (
                    <FormattedText text={msg.content} />
                  ) : (
                    <p style={{
                      fontSize: "13px",
                      fontFamily: PROSE_FONT,
                      color: "#e2e2f0",
                      lineHeight: 1.5,
                      margin: 0,
                    }}>
                      {msg.content}
                    </p>
                  )}
                </div>
                <span style={{
                  fontSize: "9px",
                  color: msg.role === "user" ? "rgba(255,255,255,0.2)" : "rgba(124,92,252,0.5)",
                  marginTop: "3px",
                  letterSpacing: "0.06em",
                  fontFamily: PROSE_FONT,
                }}>
                  {msg.role === "user" ? "YOU" : "GSCOTT"}
                </span>
              </div>
            ))}

            {/* Typing indicator */}
            {sending && (
              <div style={{
                display: "flex",
                flexDirection: "column",
                alignSelf: "flex-start",
                gap: "4px",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ display: "flex", gap: "3px" }}>
                    {[0, 1, 2].map(i => (
                      <div key={i} style={{
                        width: "5px",
                        height: "5px",
                        borderRadius: "50%",
                        background: "rgba(124,92,252,0.6)",
                        animation: `bounce 0.9s ease-in-out ${i * 0.15}s infinite`,
                      }} />
                    ))}
                  </div>
                  <span style={{
                    fontSize: "10px",
                    color: "rgba(255,255,255,0.25)",
                    fontFamily: PROSE_FONT,
                  }}>
                    GScott is thinking...
                  </span>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Chat input bar */}
      <div style={{
        padding: "12px 24px 20px",
        flexShrink: 0,
        borderTop: "1px solid rgba(255,255,255,0.06)",
        display: "flex",
        gap: "10px",
        alignItems: "flex-end",
      }}>
        <textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
          }}
          onFocus={() => setFocusedInput(true)}
          onBlur={() => setFocusedInput(false)}
          placeholder="Ask about this portfolio... (Enter to send)"
          rows={1}
          style={{
            flex: 1,
            resize: "none" as const,
            background: focusedInput ? "rgba(124,92,252,0.04)" : "rgba(255,255,255,0.04)",
            border: `1px solid ${focusedInput ? "rgba(124,92,252,0.5)" : "rgba(255,255,255,0.1)"}`,
            borderRadius: "8px",
            color: "#e2e2f0",
            fontSize: "13px",
            fontFamily: PROSE_FONT,
            padding: "10px 14px",
            outline: "none",
            lineHeight: 1.5,
            maxHeight: "120px",
            overflowY: "auto" as const,
            transition: "border-color 150ms ease, background 150ms ease",
          }}
        />
        <button
          onClick={send}
          disabled={sendDisabled}
          onMouseEnter={() => setHoveredSend(true)}
          onMouseLeave={() => setHoveredSend(false)}
          style={{
            background: sendDisabled
              ? "rgba(124,92,252,0.12)"
              : hoveredSend ? "#917aff" : "#7c5cfc",
            color: sendDisabled ? "rgba(255,255,255,0.3)" : "#fff",
            border: "none",
            borderRadius: "8px",
            padding: "10px 18px",
            fontSize: "12px",
            fontFamily: PROSE_FONT,
            fontWeight: 600,
            letterSpacing: "0.06em",
            cursor: sendDisabled ? "not-allowed" : "pointer",
            transition: "all 150ms ease",
            flexShrink: 0,
            boxShadow: (!sendDisabled && hoveredSend) ? "0 0 16px rgba(124,92,252,0.5)" : "none",
          }}
        >
          SEND
        </button>
      </div>

      {/* Keyframes */}
      <style>{`
        @keyframes shimmer {
          from { background-position: 200% 0; }
          to { background-position: -200% 0; }
        }
        @keyframes bounce {
          0%, 100% { transform: translateY(0); opacity: 0.4; }
          50% { transform: translateY(-4px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
