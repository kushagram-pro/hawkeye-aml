import { useRef, useState } from "react";
import { askAboutCase } from "../services/api";
import { ChatMessage } from "../types";

interface ChatPanelProps {
  scenarioId: string | null;
  onAsked?: () => void;
}

export function ChatPanel({ scenarioId, onAsked }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const disabled = !scenarioId || asking;

  const handleAsk = async () => {
    const trimmed = question.trim();
    if (!trimmed || !scenarioId || asking) {
      return;
    }

    const history = messages;
    const nextMessages: ChatMessage[] = [...history, { role: "user", content: trimmed }];
    setMessages(nextMessages);
    setQuestion("");
    setAsking(true);
    setError(null);

    try {
      const answer = await askAboutCase(scenarioId, trimmed, history);
      setMessages([...nextMessages, { role: "assistant", content: answer }]);
      onAsked?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reach the case assistant.");
    } finally {
      setAsking(false);
      requestAnimationFrame(() => {
        listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
      });
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void handleAsk();
    }
  };

  return (
    <section className="panel chat-panel">
      <div className="section-heading">
        <span className="eyebrow">Ask The Case</span>
        <h2>Chat with this investigation</h2>
      </div>

      {!scenarioId ? (
        <p className="helper-text">Run an investigation first, then ask follow-up questions about what it found.</p>
      ) : (
        <>
          <div className="chat-message-list" ref={listRef}>
            {messages.length === 0 ? (
              <p className="helper-text">
                Ask anything about this case - e.g. "Why is ACC406 high risk?" or "What should I check next?"
              </p>
            ) : (
              messages.map((message, index) => (
                <div key={index} className={`chat-bubble ${message.role}`}>
                  <span className="chat-bubble-role">{message.role === "user" ? "You" : "Case Assistant"}</span>
                  <p>{message.content}</p>
                </div>
              ))
            )}
            {asking ? (
              <div className="chat-bubble assistant pending">
                <span className="chat-bubble-role">Case Assistant</span>
                <p>Thinking...</p>
              </div>
            ) : null}
          </div>

          {error ? <p className="upload-error">{error}</p> : null}

          <div className="chat-input-row">
            <input
              type="text"
              className="upload-name-input"
              placeholder="Ask a question about this investigation..."
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              maxLength={300}
            />
            <button type="button" className="ghost-button" onClick={() => void handleAsk()} disabled={disabled || !question.trim()}>
              {asking ? "Asking..." : "Ask"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
