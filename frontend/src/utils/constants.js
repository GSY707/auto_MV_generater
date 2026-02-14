export const API_BASE = '/api'

export const TASK_STATUS = {
  NOT_START: 'NOT_START',
  SUBMITTED: 'SUBMITTED',
  QUEUED: 'QUEUED',
  IN_PROGRESS: 'IN_PROGRESS',
  SUCCESS: 'SUCCESS',
  FAILURE: 'FAILURE',
}

export const TERMINAL_STATUSES = new Set([TASK_STATUS.SUCCESS, TASK_STATUS.FAILURE])

export const SUNO_MODELS = [
  { value: 'chirp-v3-5', label: 'v3.5' },
  { value: 'chirp-v4', label: 'v4.0 (默认)' },
  { value: 'chirp-auk', label: 'v4.5' },
  { value: 'chirp-v5', label: 'v5.0' },
]

// --- MV ---
export const MV_STATUS = {
  PENDING: 'PENDING',
  GENERATING_STORYBOARD: 'GENERATING_STORYBOARD',
  GENERATING_IMAGES: 'GENERATING_IMAGES',
  GENERATING_VIDEO: 'GENERATING_VIDEO',
  STITCHING: 'STITCHING',
  SUCCESS: 'SUCCESS',
  FAILURE: 'FAILURE',
  INTERRUPTED: 'INTERRUPTED',
}

export const MV_TERMINAL_STATUSES = new Set([MV_STATUS.SUCCESS, MV_STATUS.FAILURE])

export const MV_STATUS_LABELS = {
  PENDING: '等待中',
  GENERATING_STORYBOARD: '生成分镜',
  GENERATING_IMAGES: '生成参考图',
  GENERATING_VIDEO: '生成视频',
  STITCHING: '拼接视频',
  SUCCESS: '已完成',
  FAILURE: '失败',
  INTERRUPTED: '已中断(重启后恢复)',
}

export const VEO_MODELS = [
  { value: 'veo-3.1-fast-generate-preview', label: 'Veo 3.1 Fast (推荐)' },
  { value: 'veo-3.1-fast-generate-001', label: 'Veo 3.1 Fast 001' },
  { value: 'veo-3.0-fast-generate-preview', label: 'Veo 3.0 Fast' },
]
