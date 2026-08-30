const _origFetch = window.fetch;
let _staticMode: boolean | null = null;

async function _isStatic(): Promise<boolean> {
  if (_staticMode !== null) return _staticMode;
  try {
    const r = await _origFetch('./api/STATIC.json', { cache: 'no-store' });
    _staticMode = r.ok;
  } catch {
    _staticMode = false;
  }
  return _staticMode;
}

function _staticize(url: string): string {
  if (!url.startsWith('/api/')) return url;
  if (url.endsWith('.geojson')) return '.' + url;
  const [path] = url.split('?');
  if (path.endsWith('.pdf')) return '.' + path;
  return '.' + path + '.json';
}

export async function apiFetch(url: string, opts?: RequestInit): Promise<Response> {
  if (url.startsWith('/api/')) {
    if (await _isStatic()) {
      return _origFetch(_staticize(url), opts);
    }
  }
  return _origFetch(url, opts);
}

export async function fetchJSON<T>(url: string): Promise<T> {
  const r = await apiFetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

export const fmt = (n: number, d = 1) => Number(n).toFixed(d);
