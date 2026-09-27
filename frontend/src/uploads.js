// Mirrors the server's checks so people get instant feedback; the server still validates.
export const IMAGE_ACCEPT = 'image/png,image/jpeg,image/webp'
const IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp']
const MAX_IMAGE_BYTES = 2 * 1024 * 1024

export function imageProblem(file) {
  if (!IMAGE_TYPES.includes(file.type)) return 'Choose a PNG, JPG or WebP image.'
  if (file.size > MAX_IMAGE_BYTES) return 'Images must be 2 MB or smaller.'
  return null
}
