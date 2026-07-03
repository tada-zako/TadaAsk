export interface RelativeDateMessages {
  unknown: string;
  justNow: string;
  minutesAgo: (count: number) => string;
  hoursAgo: (count: number) => string;
  daysAgo: (count: number) => string;
}

// 格式化绝对日期（如 "15 Jan 2026"）。
export function formatDate(value: string, unknownLabel: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return unknownLabel;
  }

  return date.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

// 格式化相对时间，如：刚刚、xx分钟前、xx小时前等。
export function formatRelativeDate(
  value: string,
  messages: RelativeDateMessages,
): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return messages.unknown;
  }

  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.max(0, Math.round(diffMs / 60_000));

  if (diffMinutes < 1) {
    return messages.justNow;
  }

  if (diffMinutes < 60) {
    return messages.minutesAgo(diffMinutes);
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return messages.hoursAgo(diffHours);
  }

  const diffDays = Math.round(diffHours / 24);
  if (diffDays < 8) {
    return messages.daysAgo(diffDays);
  }

  return formatDate(value, messages.unknown);
}
