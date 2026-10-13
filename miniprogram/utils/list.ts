/**
 * 游标分页 loader 工厂。
 * 后端三种分页约定（utils 层统一适配）：
 *  - items feed：字符串游标 "ts|id"
 *  - 其余列表：整数 id 游标
 *  - chat：since 增量（页面自行处理，不用本工厂）
 */

export interface PageResult<T> {
  list: T[];
  next_cursor: string | number | null;
}

export interface ListLoader<T> {
  items: T[];
  refreshing: boolean;
  loadingMore: boolean;
  finished: boolean;
  error: boolean;
  refresh(): Promise<void>;
  loadMore(): Promise<void>;
}

export interface LoaderOptions<T> {
  /** 拉取一页。cursor 为 null 表示第一页；返回 next_cursor 为 null 表示到底 */
  fetch(cursor: string | number | null, limit: number): Promise<PageResult<T>>;
  /** 数据变化时回调（页面里 setData） */
  onUpdate(state: { items: T[]; finished: boolean }): void;
  onError?(e: any): void;
  limit?: number;
}

export function createListLoader<T>(opts: LoaderOptions<T>): ListLoader<T> {
  const limit = opts.limit || 20;
  let items: T[] = [];
  let cursor: string | number | null = null;
  let refreshing = false;
  let loadingMore = false;
  let finished = false;
  let error = false;

  function emit() {
    opts.onUpdate({ items: [...items], finished });
  }

  async function refresh(): Promise<void> {
    if (refreshing) return;
    refreshing = true;
    error = false;
    try {
      const res = await opts.fetch(null, limit);
      items = res.list || [];
      cursor = res.next_cursor;
      finished = cursor === null || cursor === undefined || items.length === 0;
      emit();
    } catch (e) {
      error = true;
      opts.onError && opts.onError(e);
    } finally {
      refreshing = false;
    }
  }

  async function loadMore(): Promise<void> {
    if (loadingMore || finished || error) return;
    if (cursor === null && items.length > 0) return;
    loadingMore = true;
    try {
      const res = await opts.fetch(cursor, limit);
      items = items.concat(res.list || []);
      cursor = res.next_cursor;
      finished = cursor === null || cursor === undefined;
      emit();
    } catch (e) {
      opts.onError && opts.onError(e);
    } finally {
      loadingMore = false;
    }
  }

  return {
    get items() { return items; },
    get refreshing() { return refreshing; },
    get loadingMore() { return loadingMore; },
    get finished() { return finished; },
    get error() { return error; },
    refresh,
    loadMore,
  };
}
