export function throttle(fn: (...args: any[]) => void, delay = 100) {
  let timer: number | null = null;
  return function(...args: any[]) {
    if (timer) return;
    timer = setTimeout(() => {
      fn.apply(null, args);
      timer = null;
    }, delay);
  };
}

export const formatTime = (time: string) => {
  const date = new Date(time)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return `${date.getMonth() + 1}月${date.getDate()}日`
}