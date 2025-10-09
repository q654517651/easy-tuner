/**
 * 格式化日期字符串为本地时间格式
 * @param dateString ISO 格式的日期字符串
 * @param options 可选的格式化选项
 * @returns 格式化后的日期字符串
 *
 * @example
 * formatDate('2024-01-01T12:30:00Z'); // "2024-01-01 12:30"
 * formatDate('2024-01-01T12:30:00Z', { includeSeconds: true }); // "2024-01-01 12:30:45"
 */
export function formatDate(
  dateString: string | null | undefined,
  options?: {
    includeSeconds?: boolean;
    locale?: string;
  }
): string {
  if (!dateString) return '';

  try {
    const date = new Date(dateString);

    // 检查日期是否有效
    if (isNaN(date.getTime())) {
      return dateString;
    }

    const locale = options?.locale || 'zh-CN';
    const includeSeconds = options?.includeSeconds || false;

    return date.toLocaleString(locale, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      ...(includeSeconds && { second: '2-digit' }),
    });
  } catch {
    return dateString;
  }
}

/**
 * 格式化日期为短格式（仅日期）
 * @param dateString ISO 格式的日期字符串
 * @returns 格式化后的日期字符串，如 "2024-01-01"
 */
export function formatDateShort(
  dateString: string | null | undefined,
  locale: string = 'zh-CN'
): string {
  if (!dateString) return '';

  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) {
      return dateString;
    }

    return date.toLocaleDateString(locale, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  } catch {
    return dateString;
  }
}

/**
 * 格式化时间为短格式（仅时间）
 * @param dateString ISO 格式的日期字符串
 * @returns 格式化后的时间字符串，如 "12:30"
 */
export function formatTimeShort(
  dateString: string | null | undefined,
  locale: string = 'zh-CN'
): string {
  if (!dateString) return '';

  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) {
      return dateString;
    }

    return date.toLocaleTimeString(locale, {
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateString;
  }
}

/**
 * 将秒数格式化为 HH:MM:SS 或 MM:SS 格式
 * @param seconds 秒数
 * @returns 格式化后的时间字符串
 *
 * @example
 * formatDuration(90); // "1:30"
 * formatDuration(3661); // "1:01:01"
 */
export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return '0:00';
  }

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

/**
 * 计算相对时间（如 "5分钟前"）
 * @param dateString ISO 格式的日期字符串
 * @returns 相对时间描述
 *
 * @example
 * formatRelativeTime('2024-01-01T12:00:00Z'); // "5分钟前"
 */
export function formatRelativeTime(dateString: string | null | undefined): string {
  if (!dateString) return '';

  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) {
      return dateString;
    }

    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) {
      return '刚刚';
    } else if (diffMin < 60) {
      return `${diffMin}分钟前`;
    } else if (diffHour < 24) {
      return `${diffHour}小时前`;
    } else if (diffDay < 7) {
      return `${diffDay}天前`;
    } else {
      return formatDate(dateString);
    }
  } catch {
    return dateString;
  }
}

/**
 * 判断日期是否为今天
 * @param dateString ISO 格式的日期字符串
 * @returns 是否为今天
 */
export function isToday(dateString: string | null | undefined): boolean {
  if (!dateString) return false;

  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) {
      return false;
    }

    const today = new Date();
    return (
      date.getDate() === today.getDate() &&
      date.getMonth() === today.getMonth() &&
      date.getFullYear() === today.getFullYear()
    );
  } catch {
    return false;
  }
}
