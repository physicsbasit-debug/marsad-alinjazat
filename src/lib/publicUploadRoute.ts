export function resolvePublicUploadToken(
  pathname: string,
  search: string,
  baseUrl: string,
): string | null {
  const queryToken = new URLSearchParams(search).get('upload')?.trim();
  if (queryToken) return queryToken;

  const basePath = (baseUrl || '/').replace(/\/+$/, '');
  const relativePath = basePath && basePath !== '/' && pathname.startsWith(basePath)
    ? pathname.slice(basePath.length)
    : pathname;
  const encodedToken = relativePath.match(/^\/?upload\/([^/]+)\/?$/)?.[1];
  if (!encodedToken) return null;

  try {
    return decodeURIComponent(encodedToken);
  } catch {
    return encodedToken;
  }
}

export function buildPublicUploadUrl(token: string, origin: string, baseUrl: string): string {
  const base = new URL(baseUrl || '/', origin);
  const uploadUrl = new URL(base);
  uploadUrl.searchParams.set('upload', token);
  return uploadUrl.toString();
}
