const BASE = '/api'

async function request(url, options = {}) {
  const res = await fetch(BASE + url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.error || `请求失败: ${res.status}`)
  }
  return res.json()
}

export const api = {
  generate: (params) =>
    request('/generate', { method: 'POST', body: JSON.stringify(params) }),

  getTasks: () => request('/tasks'),

  getTask: (taskId) => request(`/tasks/${taskId}`),

  deleteTask: (taskId) =>
    request(`/tasks/${taskId}`, { method: 'DELETE' }),

  refreshTasks: (taskIds) =>
    request('/tasks/refresh', {
      method: 'POST',
      body: JSON.stringify({ task_ids: taskIds }),
    }),

  getWav: (clipId) => request(`/clips/${clipId}/wav`),

  chat: (message, history) =>
    request('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, history }),
    }),

  // --- Recommendations ---
  getCreateRecommendations: (count = 4) =>
    request(`/recommendations/create?count=${count}`),

  getChatRecommendations: (count = 4) =>
    request(`/recommendations/chat?count=${count}`),

  markRecommendationClicked: (text, context = 'create') =>
    request('/recommendations/click', {
      method: 'POST',
      body: JSON.stringify({ text, context }),
    }),

  // --- Chat History ---
  getChatHistory: () => request('/chat/history'),

  saveChatHistory: (messages) =>
    request('/chat/history', {
      method: 'POST',
      body: JSON.stringify({ messages }),
    }),

  clearChatHistory: () =>
    request('/chat/history', { method: 'DELETE' }),

  getConfig: () => request('/config'),

  getOutputFiles: () => request('/output'),

  // --- MV ---
  generateMV: (params) =>
    request('/mv/generate', { method: 'POST', body: JSON.stringify(params) }),

  getMVList: (clipId) =>
    request(clipId ? `/mv?clip_id=${clipId}` : '/mv'),

  getMV: (mvId) => request(`/mv/${mvId}`),

  deleteMV: (mvId) =>
    request(`/mv/${mvId}`, { method: 'DELETE' }),

  getMVModels: () => request('/mv/models'),

  getMVSceneVideoUrl: (mvId, sceneIndex) =>
    `${BASE}/mv/${mvId}/scene/${sceneIndex}/video`,

  getMVSceneImageUrl: (mvId, sceneIndex) =>
    `${BASE}/mv/${mvId}/scene/${sceneIndex}/image`,

  getMVFinalUrl: (mvId) =>
    `${BASE}/mv/${mvId}/final`,

  downloadMVFinal: async (mvId, fallbackName) => {
    const res = await fetch(`${BASE}/mv/${mvId}/final`)
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: res.statusText }))
      throw new Error(err.error || `下载失败: ${res.status}`)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fallbackName || `mv_${mvId.slice(0, 8)}.mp4`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },
}
