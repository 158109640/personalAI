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