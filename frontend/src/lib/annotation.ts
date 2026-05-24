import type { PromptPair } from "./types";

const staleTranslationMarkers = [
  "该 Prompt 适合",
  "该 prompt 适合",
  "重点参考其主体描述",
  "原文需结合来源 License",
  "原文需要结合来源 License",
  "适合用于图像生成场景",
  "适合用于视频生成场景"
];

export function isStaleTranslation(value?: string | null) {
  const text = value?.trim();
  if (!text) return false;
  return staleTranslationMarkers.some((marker) => text.includes(marker));
}

export function effectiveCnExplanation(pair: PromptPair) {
  const formal = pair.prompt_cn_explanation?.trim() || "";
  if (formal && !isStaleTranslation(formal)) return formal;
  return pair.latest_suggested_cn_explanation?.trim() || "";
}

export function hasEffectiveAnnotation(pair: PromptPair) {
  const hasTags = Boolean((pair.tag_count || pair.tags?.length || pair.latest_suggested_tags?.length || 0) > 0);
  return Boolean(effectiveCnExplanation(pair) && hasTags);
}
