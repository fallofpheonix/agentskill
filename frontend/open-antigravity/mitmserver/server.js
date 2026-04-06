const http = require('http');
const httpProxy = require('http-proxy');

const TARGET = process.env.OPEN_ANTIGRAVITY_PROXY_TARGET || 'http://localhost:3000';
const PORT = Number.parseInt(process.env.OPEN_ANTIGRAVITY_PROXY_PORT || process.env.PORT || '8080', 10);
const VERBOSE = /^(1|true|yes)$/i.test(process.env.OPEN_ANTIGRAVITY_PROXY_VERBOSE || '');
const SENSITIVE_HEADERS = new Set(['authorization', 'proxy-authorization', 'cookie', 'set-cookie', 'x-api-key']);

function redactHeaders(headers) {
  const sanitized = {};
  for (const [key, value] of Object.entries(headers || {})) {
    sanitized[key] = SENSITIVE_HEADERS.has(key.toLowerCase()) ? '<redacted>' : value;
  }
  return sanitized;
}

function logRequest(req) {
  console.log(`Request: ${req.method} ${req.url}`);
  if (VERBOSE) {
    console.log('  Headers:', redactHeaders(req.headers));
  }
}

function logResponse(proxyRes) {
  console.log(`Response: ${proxyRes.statusCode}`);
  if (VERBOSE) {
    console.log('  Headers:', redactHeaders(proxyRes.headers));
  }
}

const proxy = httpProxy.createProxyServer({
  changeOrigin: true,
  target: TARGET,
});

const server = http.createServer((req, res) => {
  logRequest(req);

  proxy.web(req, res, { target: TARGET }, (e) => {
    console.error('Proxy error:', e);
    res.writeHead(502);
    res.end('There was an error proxying the request.');
  });
});

proxy.on('proxyRes', (proxyRes) => {
  logResponse(proxyRes);
});

proxy.on('error', (error) => {
  console.error('Proxy server error:', error);
});

server.on('clientError', (error, socket) => {
  console.error('Client connection error:', error.message);
  socket.end('HTTP/1.1 400 Bad Request\r\n\r\n');
});

server.listen(PORT, () => {
  console.log(`MITM proxy listening on port ${PORT} -> ${TARGET}`);
});
