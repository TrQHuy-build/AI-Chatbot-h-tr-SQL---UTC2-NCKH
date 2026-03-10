import React, { useState, useRef, useEffect } from 'react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sql?: string;
  executionResult?: string;
}

const Chatbot: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [schema, setSchema] = useState('students(id, name), courses(id, title), enrollments(student_id, course_id)');
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    const userMessage: Message = { role: 'user', content: question };
    setMessages(prev => [...prev, userMessage]);
    setLoading(true);
    setError('');

    try {
      const res = await fetch('http://localhost:8000/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, schema }),
      });

      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);

      const data = await res.json();

      const assistantMessage: Message = {
        role: 'assistant',
        content: data.status === 'success'
          ? 'Đây là truy vấn SQL phù hợp với câu hỏi của bạn:'
          : 'Đã xảy ra lỗi khi xử lý câu hỏi.',
        sql: data.sql_query,
        executionResult: data.execution_result,
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (err: any) {
      setError(`Lỗi kết nối đến server: ${err.message}`);
    } finally {
      setLoading(false);
      setQuestion('');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex flex-col items-center justify-start p-4">
      {/* Header */}
      <div className="w-full max-w-3xl bg-indigo-600 text-white rounded-t-xl p-4 shadow-lg">
        <h1 className="text-2xl font-bold text-center">🤖 SQL Chatbot AI</h1>
        <p className="text-center text-indigo-200 text-sm mt-1">
          Hỗ trợ gợi ý giải bài tập Cơ sở Dữ liệu
        </p>
      </div>

      {/* Schema Input */}
      <div className="w-full max-w-3xl bg-white p-3 border-x border-indigo-200 shadow">
        <label className="block text-sm font-semibold text-gray-600 mb-1">📊 Database Schema:</label>
        <input
          type="text"
          className="w-full p-2 border border-gray-300 rounded text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-400"
          value={schema}
          onChange={(e) => setSchema(e.target.value)}
          placeholder="Nhập schema database..."
        />
      </div>

      {/* Chat Window */}
      <div className="w-full max-w-3xl bg-white border-x border-indigo-200 shadow flex-1 overflow-y-auto p-4 space-y-4"
        style={{ minHeight: '400px', maxHeight: '500px', overflowY: 'auto' }}>
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-16">
            <p className="text-4xl mb-4">💬</p>
            <p className="text-lg">Hãy đặt câu hỏi về SQL!</p>
            <p className="text-sm mt-2">Ví dụ: "Tìm tên tất cả sinh viên đăng ký khóa học Database Systems"</p>
          </div>
        )}
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-2xl rounded-xl p-3 shadow-sm ${
              msg.role === 'user'
                ? 'bg-indigo-500 text-white rounded-br-none'
                : 'bg-gray-100 text-gray-800 rounded-bl-none'
            }`}>
              <p className="text-sm font-semibold mb-1">
                {msg.role === 'user' ? '👤 Bạn' : '🤖 Chatbot'}
              </p>
              <p className="text-sm">{msg.content}</p>
              {msg.sql && (
                <div className="mt-2 bg-gray-800 text-green-400 rounded p-2">
                  <p className="text-xs text-gray-400 mb-1">SQL Query:</p>
                  <pre className="text-xs overflow-x-auto whitespace-pre-wrap">{msg.sql}</pre>
                </div>
              )}
              {msg.executionResult && (
                <div className="mt-2 bg-blue-50 text-blue-800 rounded p-2">
                  <p className="text-xs font-semibold mb-1">📋 Kết quả thực thi:</p>
                  <pre className="text-xs overflow-x-auto">{msg.executionResult}</pre>
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-xl p-3 shadow-sm">
              <p className="text-sm text-gray-500 animate-pulse">🤖 Đang xử lý câu hỏi...</p>
            </div>
          </div>
        )}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-600 rounded-xl p-3 text-sm">
            ⚠️ {error}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <div className="w-full max-w-3xl bg-white p-3 border border-indigo-200 rounded-b-xl shadow-lg">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <textarea
            className="flex-1 p-2 border border-gray-300 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400"
            rows={2}
            placeholder="Nhập câu hỏi của bạn về SQL..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-semibold text-sm"
          >
            {loading ? '⏳' : '🚀 Gửi'}
          </button>
        </form>
        <p className="text-xs text-gray-400 mt-1">Nhấn Enter để gửi, Shift+Enter để xuống dòng</p>
      </div>
    </div>
  );
};

export default Chatbot;
