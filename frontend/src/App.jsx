import React, { useEffect, useMemo, useState } from "react";

import {
  checkBackendHealth,
  ingestKnowledgeBase,
  sendChatMessage
} from "./api.js";

const DEMO_QUESTIONS = [
  "BABA 最近 7 天涨跌情况如何？",
  "阿里巴巴为何 5 月 6 日大涨？",
  "什么是市盈率？",
  "收入和净利润的区别是什么？",
  "现金流为什么重要？",
  "TSLA 最近 30 天走势如何？"
];

function RouteBadge({ route }) {
  const label = route || "unknown";

  return <span className={`route-badge route-${label}`}>{label}</span>;
}

function MarketTable({ history }) {
  if (!history || history.length === 0) {
    return null;
  }

  const lastRows = history.slice(-7);

  return (
    <div className="market-table-wrapper">
      <div className="section-label">Recent Price History</div>
      <table className="market-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Open</th>
            <th>High</th>
            <th>Low</th>
            <th>Close</th>
            <th>Volume</th>
          </tr>
        </thead>
        <tbody>
          {lastRows.map((row) => (
            <tr key={row.Date}>
              <td>{row.Date}</td>
              <td>{row.Open}</td>
              <td>{row.High}</td>
              <td>{row.Low}</td>
              <td>{row.Close}</td>
              <td>{Number(row.Volume).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MessageCard({ message }) {
  const isUser = message.role === "user";

  return (
    <div className={`message-card ${isUser ? "user-card" : "assistant-card"}`}>
      <div className="message-header">
        <span>{isUser ? "You" : "Financial QA Assistant"}</span>
        {!isUser && <RouteBadge route={message.route} />}
      </div>

      <div className="message-body">{message.content}</div>

      {!isUser && message.sources?.length > 0 && (
        <div className="sources">
          <div className="section-label">Sources</div>
          <ul>
            {message.sources.map((source) => (
              <li key={source}>{source}</li>
            ))}
          </ul>
        </div>
      )}

      {!isUser && message.data?.market?.history && (
        <MarketTable history={message.data.market.history} />
      )}
    </div>
  );
}

function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "你好，我是 Financial Asset QA System。你可以问我股票走势、涨跌分析、金融概念解释，或者事件型问题。",
      route: "system",
      sources: [],
      data: null
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [backendStatus, setBackendStatus] = useState("checking");
  const [ingestStatus, setIngestStatus] = useState("");

  const canSend = useMemo(() => {
    return question.trim().length > 0 && !isLoading;
  }, [question, isLoading]);

  useEffect(() => {
    async function checkHealth() {
      try {
        await checkBackendHealth();
        setBackendStatus("online");
      } catch (error) {
        setBackendStatus("offline");
      }
    }

    checkHealth();
  }, []);

  async function handleSend(customQuestion) {
    const finalQuestion = (customQuestion || question).trim();

    if (!finalQuestion) {
      return;
    }

    setQuestion("");
    setIsLoading(true);

    const userMessage = {
      role: "user",
      content: finalQuestion
    };

    setMessages((prev) => [...prev, userMessage]);

    try {
      const result = await sendChatMessage(finalQuestion);

      const assistantMessage = {
        role: "assistant",
        content: result.answer,
        route: result.route,
        sources: result.sources || [],
        data: result.data || null
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      const assistantMessage = {
        role: "assistant",
        content:
          "【前端请求失败】\n无法连接后端 API。请确认 FastAPI 正在 http://localhost:8000 运行。\n\n错误信息：" +
          error.message,
        route: "error",
        sources: [],
        data: null
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleIngest() {
    setIngestStatus("Building RAG index...");

    try {
      const result = await ingestKnowledgeBase();

      setIngestStatus(
        `RAG index built. Inserted chunks: ${result.inserted_chunks}. Files: ${result.files.join(", ")}`
      );
    } catch (error) {
      setIngestStatus(`RAG ingest failed: ${error.message}`);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">FQ</div>
          <div>
            <h1>Financial Asset QA</h1>
            <p>Market Data + RAG + Structured Answers</p>
          </div>
        </div>

        <div className="status-card">
          <div className="section-label">Backend Status</div>
          <div className={`status-dot status-${backendStatus}`}>
            {backendStatus}
          </div>
        </div>

        <div className="info-card">
          <div className="section-label">System Routes</div>
          <ul>
            <li>Market questions → Alpha Vantage / yfinance</li>
            <li>Knowledge questions → Chroma RAG</li>
            <li>Event analysis → Market data + volume analysis</li>
          </ul>
        </div>

        <div className="info-card">
          <div className="section-label">Demo Questions</div>
          <div className="demo-list">
            {DEMO_QUESTIONS.map((item) => (
              <button
                key={item}
                className="demo-button"
                onClick={() => handleSend(item)}
                disabled={isLoading}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="info-card">
          <div className="section-label">RAG Index</div>
          <button className="secondary-button" onClick={handleIngest}>
            Build / Rebuild Knowledge Base
          </button>
          {ingestStatus && <p className="small-text">{ingestStatus}</p>}
        </div>
      </aside>

      <main className="chat-panel">
        <div className="chat-header">
          <div>
            <h2>Ask about financial assets</h2>
            <p>
              The system separates objective market data from analytical
              interpretation to reduce hallucination.
            </p>
          </div>
        </div>

        <div className="messages">
          {messages.map((message, index) => (
            <MessageCard key={`${message.role}-${index}`} message={message} />
          ))}

          {isLoading && (
            <div className="message-card assistant-card">
              <div className="message-header">
                <span>Financial QA Assistant</span>
                <RouteBadge route="loading" />
              </div>
              <div className="message-body">Analyzing...</div>
            </div>
          )}
        </div>

        <div className="input-area">
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Try: BABA 最近 7 天涨跌情况如何？"
            rows={2}
          />
          <button onClick={() => handleSend()} disabled={!canSend}>
            {isLoading ? "Sending..." : "Send"}
          </button>
        </div>
      </main>
    </div>
  );
}

export default App;