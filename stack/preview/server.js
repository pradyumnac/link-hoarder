import dns from "node:dns";
import http from "node:http";

import { getLinkPreview } from "link-preview-js";

const PORT = Number(process.env.PREVIEW_PORT ?? "3001");
const FETCH_TIMEOUT_MS = Number(process.env.PREVIEW_FETCH_TIMEOUT_MS ?? "10000");

function resolveDNSHost(url) {
  return new Promise((resolvePromise, rejectPromise) => {
    let hostname;
    try {
      hostname = new URL(url).hostname;
    } catch {
      rejectPromise(new Error("The preview URL is invalid."));
      return;
    }
    dns.lookup(hostname, (error, address) => {
      if (error) {
        rejectPromise(error);
        return;
      }
      resolvePromise(address);
    });
  });
}

function sendJson(response, status, payload) {
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(body),
  });
  response.end(body);
}

const server = http.createServer(async (request, response) => {
  const requestUrl = new URL(request.url ?? "/", "http://preview");
  if (requestUrl.pathname === "/health") {
    sendJson(response, 200, { status: "ok" });
    return;
  }
  if (requestUrl.pathname !== "/preview") {
    sendJson(response, 404, { detail: "Unknown preview endpoint." });
    return;
  }
  const target = requestUrl.searchParams.get("url") ?? "";
  if (!target.startsWith("http://") && !target.startsWith("https://")) {
    sendJson(response, 422, { detail: "The preview URL must use HTTP or HTTPS." });
    return;
  }
  try {
    const preview = await getLinkPreview(target, {
      followRedirects: "follow",
      headers: { "user-agent": "link-hoarder-preview/0.1" },
      resolveDNSHost,
      timeout: FETCH_TIMEOUT_MS,
    });
    sendJson(response, 200, {
      url: preview.url ?? target,
      title: preview.title ?? null,
      description: preview.description ?? null,
      site_name: preview.siteName ?? null,
      images: preview.images ?? [],
      favicons: preview.favicons ?? [],
      media_type: preview.mediaType ?? null,
      content_type: preview.contentType ?? null,
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : "The preview failed.";
    sendJson(response, 422, { detail });
  }
});

server.listen(PORT, "0.0.0.0");
