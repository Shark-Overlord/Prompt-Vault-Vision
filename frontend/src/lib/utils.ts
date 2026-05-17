import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function truncate(text = "", length = 120) {
  return text.length > length ? `${text.slice(0, length)}...` : text
}

export function assetUrl(path?: string | null) {
  if (!path) return ""
  if (path.startsWith("http")) return path
  return path.startsWith("/") ? path : `/${path}`
}
