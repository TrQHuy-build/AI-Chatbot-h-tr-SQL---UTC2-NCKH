import React, { useState, useRef, useEffect } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sql?: string
  executionResult?: string
  error?: string
}

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

export default function Home() {
  const [question, setQuestion] = useState('')
  const [schema, setSchema] = useState(
    'students(id, name), courses(id, title), enrollments(student_id, course_id)'
  )
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [serverError, setServerError] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return

    const userMsg: Message = { role: 'user', content: question }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)
    setServerError('')

    try {
      const res = await fetch(`${BACKEND_URL}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, db_schema: schema }),
      })

      if (!res.ok) throw new Error(`Server trả về lỗi: ${res.status}`)

      const data = await res.json()

      const botMsg: Message = {
        role: 'assistant',
        content:
          data.status === 'success'
            ? 'Đây là truy vấn SQL phù hợp với câu hỏi của bạn:'
            : 'Đã xảy ra lỗi khi xử lý câu hỏi.',
        sql: data.sql_query,
        executionResult: data.execution_result,
        error: data.error,
      }
      setMessages(prev => [...prev, botMsg])
    } catch (err: any) {
      setServerError(`⚠️ Không thể kết nối server: ${err.message}`)
    } finally {
      setLoading(false)
      setQuestion('')
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg,#e0e7ff,#f0f9ff)', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '16px', fontFamily: 'sans-serif' }}>

      {/* Header */}
      <div style={{ width: '100%', maxWidth: '760px', background: '#4338ca', color: 'white', borderRadius: '12px 12px 0 0', padding: '16px', textAlign: 'center' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold', margin: 0 }}>🤖 SQL Chatbot AI</h1>
        <p style={{ fontSize: '0.85rem', opacity: 0.8, marginTop: '4px' }}>Hỗ trợ gợi ý giải bài tập Cơ sở Dữ liệu</p>
      </div>

      {/* Schema */}
      <div style={{ width: '100%', maxWidth: '760px', background: 'white', padding: '12px', borderLeft: '1px solid #c7d2fe', borderRight: '1px solid #c7d2fe' }}>
        <label style={{ fontSize: '0.8rem', fontWeight: '600', color: '#6b7280', display: 'block', marginBottom: '4px' }}>📊 Database Schema:</label>
        <input
          type="text"
          value={schema}
          onChange={e => setSchema(e.target.value)}
          style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.8rem', fontFamily: 'monospace', boxSizing: 'border-box' }}
          placeholder="Nhập schema..."
        />
      </div>

      {/* Chat Window */}
      <div style={{ width: '100%', maxWidth: '760px', background: 'white', borderLeft: '1px solid #c7d2fe', borderRight: '1px solid #c7d2fe', minHeight: '400px', maxHeight: '500px', overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: '#9ca3af', marginTop: '60px' }}>
            <div style={{ fontSize: '3rem' }}>💬</div>
            <p style={{ fontSize: '1rem', marginTop: '8px' }}>Hãy đặt câu hỏi về SQL!</p>
            <p style={{ fontSize: '0.8rem', marginTop: '4px' }}>Ví dụ: &quot;Tìm tên tất cả sinh viên đăng ký khóa học Database Systems&quot;</p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
            <div style={{
              maxWidth: '85%', borderRadius: '12px', padding: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
              background: msg.role === 'user' ? '#4338ca' : '#f3f4f6',
              color: msg.role === 'user' ? 'white' : '#1f2937',
              borderBottomRightRadius: msg.role === 'user' ? '2px' : '12px',
              borderBottomLeftRadius: msg.role === 'user' ? '12px' : '2px',
            }}>
              <p style={{ fontSize: '0.75rem', fontWeight: '600', marginBottom: '4px', opacity: 0.8 }}>
                {msg.role === 'user' ? '👤 Bạn' : '🤖 Chatbot'}
              </p>
              <p style={{ fontSize: '0.875rem', margin: 0 }}>{msg.content}</p>

              {msg.sql && (
                <div style={{ marginTop: '8px', background: '#1f2937', borderRadius: '6px', padding: '10px' }}>
                  <p style={{ fontSize: '0.7rem', color: '#9ca3af', marginBottom: '4px' }}>SQL Query:</p>
                  <pre style={{ fontSize: '0.8rem', color: '#34d399', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{msg.sql}</pre>
                </div>
              )}

              {msg.executionResult && (
                <div style={{ marginTop: '8px', background: '#eff6ff', borderRadius: '6px', padding: '10px' }}>
                  <p style={{ fontSize: '0.7rem', color: '#3b82f6', fontWeight: '600', marginBottom: '4px' }}>📋 Kết quả thực thi:</p>
                  <pre style={{ fontSize: '0.75rem', color: '#1e40af', margin: 0, whiteSpace: 'pre-wrap' }}>{msg.executionResult}</pre>
                </div>
              )}

              {msg.error && (
                <p style={{ fontSize: '0.8rem', color: '#ef4444', marginTop: '6px' }}>❌ {msg.error}</p>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <div style={{ background: '#f3f4f6', borderRadius: '12px', padding: '12px', fontSize: '0.875rem', color: '#6b7280' }}>
              🤖 Đang xử lý câu hỏi...
            </div>
          </div>
        )}

        {serverError && (
          <div style={{ background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626', borderRadius: '8px', padding: '12px', fontSize: '0.875rem' }}>
            {serverError}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <div style={{ width: '100%', maxWidth: '760px', background: 'white', padding: '12px', border: '1px solid #c7d2fe', borderRadius: '0 0 12px 12px', boxShadow: '0 4px 6px rgba(0,0,0,0.07)' }}>
        <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '8px' }}>
          <textarea
            rows={2}
            placeholder="Nhập câu hỏi về SQL... (Enter để gửi)"
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(e) } }}
            disabled={loading}
            style={{ flex: 1, padding: '8px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '0.875rem', resize: 'none', outline: 'none' }}
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            style={{ background: loading || !question.trim() ? '#9ca3af' : '#4338ca', color: 'white', padding: '8px 16px', borderRadius: '8px', border: 'none', cursor: loading || !question.trim() ? 'not-allowed' : 'pointer', fontWeight: '600', fontSize: '0.875rem' }}
          >
            {loading ? '⏳' : '🚀 Gửi'}
          </button>
        </form>
        <p style={{ fontSize: '0.7rem', color: '#9ca3af', marginTop: '4px' }}>Enter để gửi | Shift+Enter xuống dòng</p>
      </div>
    </div>
  )
}
