export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

const apiBaseUrl = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

function toUpstreamUrl(path: string[], requestUrl: string): string {
  const currentUrl = new URL(requestUrl);
  const cleanBaseUrl = apiBaseUrl.replace(/\/$/, "");
  const encodedPath = path.map((segment) => encodeURIComponent(segment)).join("/");

  return `${cleanBaseUrl}/${encodedPath}${currentUrl.search}`;
}

async function proxyApiRequest(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");

  if (contentType) {
    headers.set("content-type", contentType);
  }

  const response = await fetch(toUpstreamUrl(path, request.url), {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
    cache: "no-store",
  });
  const responseHeaders = new Headers();
  const responseContentType = response.headers.get("content-type");

  if (responseContentType) {
    responseHeaders.set("content-type", responseContentType);
  }

  return new Response(await response.text(), {
    status: response.status,
    headers: responseHeaders,
  });
}

export {
  proxyApiRequest as DELETE,
  proxyApiRequest as GET,
  proxyApiRequest as PATCH,
  proxyApiRequest as POST,
};
