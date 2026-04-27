import { useAppStore } from '../stores/appStore'

const store = useAppStore()

/** Files larger than this threshold are sent via the chunked-upload API. */
export const LARGE_FILE_THRESHOLD = 10 * 1024 * 1024 // 10 MB

/** Size of each individual chunk sent to /api/v1/upload/chunk. */
export const CHUNK_SIZE = 2 * 1024 * 1024 // 2 MB

/**
 * Upload an audio file and get back the job folder name.
 * POST /api/v1/transcribe
 */
export async function uploadAndTranscribe(file) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('google_token', store.state.token)

  const url = `${store.getBaseUrl()}/api/v1/transcribe`
  const response = await fetch(url, {
    method: 'POST',
    body: formData
  })

  if (!response.ok) {
    const err = await response.text()
    throw new Error(`Transcription failed (${response.status}): ${err}`)
  }

  return response.json()
}

/**
 * Run summarization on an already-transcribed job.
 * POST /api/v1/summarize
 */
export async function summarizeJob(folderName, fileName) {
  const url = `${store.getBaseUrl()}/api/v1/summarize`
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      google_token:store.state.token,
      folder_name: folderName,
      file_name: fileName,
      provider: store.state.settings.provider,
      model: store.state.settings.model || undefined,
      api_key: store.state.settings.apiKey || undefined
    })
  })

  if (!response.ok) {
    const err = await response.text()
    throw new Error(`Summarization failed (${response.status}): ${err}`)
  }

  return response.json()
}

/**
 * Run visualization on a summarized job.
 * POST /api/v1/visualize
 */
export async function visualizeJob(folderName, fileName) {
  const url = `${store.getBaseUrl()}/api/v1/visualize`
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      google_token:store.state.token,
      folder_name: folderName,
      file_name: fileName,
      provider: store.state.settings.provider,
      model: store.state.settings.model || undefined,
      api_key: store.state.settings.apiKey || undefined
    })
  })

  if (!response.ok) {
    const err = await response.text()
    throw new Error(`Visualization failed (${response.status}): ${err}`)
  }

  return response.json()
}

/**
 * Fetch job details.
 * GET /api/v1/job/{folder_name}
 */
export async function getJob(folderName) {
  const url = store.getAuthUrl(`/api/v1/job/${encodeURIComponent(folderName)}`)
  const response = await fetch(url)

  if (!response.ok) {
    const err = await response.text()
    throw new Error(`Job fetch failed (${response.status}): ${err}`)
  }

  return response.json()
}

/**
 * Fetch all past jobs.
 * GET /api/v1/history
 */
export async function getHistory() {
  const url = store.getAuthUrl('/api/v1/history')
  const response = await fetch(url)

  if (!response.ok) {
    const err = await response.text()
    throw new Error(`History fetch failed (${response.status}): ${err}`)
  }

  return response.json()
}

/**
 * Build a download URL for an artifact.
 * GET /api/v1/download/{folder_name}/{file_type}
 * @param {string} fileType - one of: 'audio', 'summary_txt', 'summary_html', 'image', 'transcript_txt', 'transcript_json'
 */
export function getDownloadUrl(folderName, fileType) {
  return store.getAuthUrl(`/api/v1/download/${encodeURIComponent(folderName)}/${encodeURIComponent(fileType)}`)
}

/**
 * Initialize a resumable chunked upload session.
 * POST /api/v1/upload/init
 */
export async function initChunkedUpload(filename, totalChunks, fileSize, transcribeLang) {
  const url = `${store.getBaseUrl()}/api/v1/upload/init`
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      google_token: store.state.token,
      filename,
      total_chunks: totalChunks,
      file_size: fileSize,
      transcribe_lang: transcribeLang || undefined
    })
  })

  if (!response.ok) {
    const err = await response.text()
    throw new Error(`Upload init failed (${response.status}): ${err}`)
  }

  return response.json()
}

/**
 * Upload one chunk of a resumable upload session.
 * POST /api/v1/upload/chunk
 */
export async function uploadChunk(uploadId, chunkIndex, chunkBlob) {
  const formData = new FormData()
  formData.append('google_token', store.state.token)
  formData.append('upload_id', uploadId)
  formData.append('chunk_index', String(chunkIndex))
  formData.append('file', chunkBlob, `chunk_${chunkIndex}`)

  const url = `${store.getBaseUrl()}/api/v1/upload/chunk`
  const response = await fetch(url, {
    method: 'POST',
    body: formData
  })

  if (!response.ok) {
    const err = await response.text()
    throw new Error(`Chunk ${chunkIndex} upload failed (${response.status}): ${err}`)
  }

  return response.json()
}

/**
 * Query which chunks have been received for an upload session.
 * GET /api/v1/upload/status/{upload_id}
 */
export async function getUploadStatus(uploadId) {
  const url = store.getAuthUrl(`/api/v1/upload/status/${encodeURIComponent(uploadId)}`)
  const response = await fetch(url)

  if (!response.ok) {
    const err = await response.text()
    throw new Error(`Upload status check failed (${response.status}): ${err}`)
  }

  return response.json()
}

/**
 * Assemble uploaded chunks and start transcription.
 * POST /api/v1/upload/complete
 */
export async function completeChunkedUpload(uploadId, transcribeLang) {
  const url = `${store.getBaseUrl()}/api/v1/upload/complete`
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      google_token: store.state.token,
      upload_id: uploadId,
      transcribe_lang: transcribeLang || undefined
    })
  })

  if (!response.ok) {
    const err = await response.text()
    throw new Error(`Upload complete failed (${response.status}): ${err}`)
  }

  return response.json()
}

/**
 * Translate job artifacts into a target language.
 * POST /api/v1/translate
 * @param {string[]} [files] - subset of ['json', 'txt', 'summary_txt']; defaults to all three
 */
export async function translateJob(folderName, fileName, sourceLang, targetLang, files) {
  const url = `${store.getBaseUrl()}/api/v1/translate`
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      google_token: store.state.token,
      folder_name: folderName,
      file_name: fileName,
      source_language: sourceLang,
      target_language: targetLang,
      files: files || undefined
    })
  })

  if (!response.ok) {
    const err = await response.text()
    throw new Error(`Translation failed (${response.status}): ${err}`)
  }

  return response.json()
}
