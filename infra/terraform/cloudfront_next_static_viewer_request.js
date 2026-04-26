// Viewer-request: map Next.js static export paths (trailingSlash: true) to S3 object keys .../index.html.
// Without this, /upload and /upload/ request object keys "upload" / "upload/" and S3 returns AccessDenied.
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  if (uri === "/") {
    return request;
  }
  if (uri.indexOf("/_next/") === 0) {
    return request;
  }
  if (/\.[a-zA-Z0-9]+$/.test(uri)) {
    return request;
  }
  if (uri.endsWith("/")) {
    request.uri = uri + "index.html";
    return request;
  }
  request.uri = uri + "/index.html";
  return request;
}
