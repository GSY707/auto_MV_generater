import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import styles from './Chat.module.css'

// Prompts that need extra user input - fill input box instead of auto-sending
const FILL_INPUT_PROMPTS = new Set([
  '帮我改进这段歌词',
])

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [promptChips, setPromptChips] = useState([])
  const navigate = useNavigate()
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  // Load persisted chat history on mount
  useEffect(() => {
    api.getChatHistory()
      .then(data => {
        if (data.messages?.length > 0) {
          setMessages(data.messages)
        }
      })
      .catch(() => {})
      .finally(() => setHistoryLoaded(true))
  }, [])

  // Load dynamic recommendation chips
  useEffect(() => {
    api.getChatRecommendations(4)
      .then(data => setPromptChips(data.recommendations || []))
      .catch(() => setPromptChips([
        '帮我写一首关于旅行的歌',
        '推荐一些适合夜晚的音乐风格',
        '我想做一首EDM，有什么建议？',
        '帮我改进这段歌词',
      ]))
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Persist chat history whenever messages change
  useEffect(() => {
    if (historyLoaded && messages.length > 0) {
      api.saveChatHistory(messages).catch(() => {})
    }
  }, [messages, historyLoaded])

  const send = async (text) => {
    const msg = text || input.trim()
    if (!msg || loading) return
    setInput('')

    const userMsg = { role: 'user', text: msg }
    setMessages(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const history = [...messages, userMsg].map(m => ({
        role: m.role,
        text: m.text,
      }))
      const data = await api.chat(msg, history)
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: data.reply || data.text || '',
        suggestions: data.suggestions,
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: `抱歉，出现了错误：${err.message}`,
      }])
    } finally {
      setLoading(false)
    }
  }

  const handlePromptChipClick = async (prompt) => {
    // Mark as clicked and refresh chips
    api.markRecommendationClicked(prompt, 'chat').catch(() => {})
    api.getChatRecommendations(4)
      .then(data => setPromptChips(data.recommendations || []))
      .catch(() => setPromptChips(prev => prev.filter(p => p !== prompt)))

    // For prompts that need extra input, fill the input box
    if (FILL_INPUT_PROMPTS.has(prompt)) {
      setInput(prompt + '：\n')
      textareaRef.current?.focus()
      return
    }

    // Otherwise send directly
    send(prompt)
  }

  const handleSuggestion = (sug) => {
    navigate('/create', {
      state: {
        suggestion: {
          title: sug.title || '',
          tags: sug.tags || '',
          prompt: sug.prompt || sug.lyrics || '',
          model: sug.model || 'chirp-v4',
        },
      },
    })
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const handleClearHistory = useCallback(() => {
    setMessages([])
    api.clearChatHistory().catch(() => {})
  }, [])

  if (!historyLoaded) return null

  if (messages.length === 0 && !loading) {
    return (
      <div className={styles.page}>
        <div className={styles.welcome}>
          <div className={styles.welcomeTitle}>AI 音乐助手</div>
          <div className={styles.welcomeSub}>让我帮你创作独特的音乐作品</div>
          <div className={styles.prompts}>
            {promptChips.map(p => (
              <button key={p} className={styles.promptChip} onClick={() => handlePromptChipClick(p)}>
                {p}
              </button>
            ))}
          </div>
        </div>
        <div className={styles.inputArea}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入你的想法..."
          />
          <button className={styles.sendBtn} onClick={() => send()} disabled={!input.trim()}>
            发送
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <div className={styles.headerRow}>
        <h1 className="page-title" style={{ flexShrink: 0, margin: 0 }}>AI 助手</h1>
        <button className={styles.clearBtn} onClick={handleClearHistory} title="清空聊天记录">
          清空记录
        </button>
      </div>
      <div className={styles.messages}>
        {messages.map((msg, i) => (
          <div key={i} className={`${styles.message} ${styles[msg.role]}`}>
            <div>{msg.text}</div>
            {msg.suggestions?.length > 0 && (
              <div className={styles.suggestions}>
                {msg.suggestions.map((sug, j) => (
                  <button key={j} className={styles.chip} onClick={() => handleSuggestion(sug)}>
                    <div className={styles.chipTitle}>{sug.title || '创作建议'}</div>
                    {sug.tags && <div className={styles.chipTags}>{sug.tags}</div>}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className={styles.typing}>
            <span className={styles.dot} />
            <span className={styles.dot} />
            <span className={styles.dot} />
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className={styles.inputArea}>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入你的想法..."
        />
        <button className={styles.sendBtn} onClick={() => send()} disabled={!input.trim() || loading}>
          发送
        </button>
      </div>
    </div>
  )
}
