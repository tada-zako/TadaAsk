// 可选文本规范化：空字符串/undefined 统一为 null。
export function normalizeOptionalText(
  value: string | null | undefined,
): string | null {
  if (value === undefined) {
    return null;
  }

  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

// 规范化进度值（0-100 整数），非法值返回 null。
// 后端可能返回 0-1 小数或 0-100 整数，统一按 <= 1 判别并放大。
export function normalizeProgress(
  value: number | null | undefined,
): number | null {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null;
  }

  const normalized = value <= 1 ? value * 100 : value;
  return Math.min(100, Math.max(0, Math.round(normalized)));
}
