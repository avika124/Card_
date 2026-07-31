// ComplyLine Local Server — Node.js version
// No npm install needed — uses only built-in Node modules
// 
// Usage:
//   node server.js
//   node server.js 8080
//   ANTHROPIC_API_KEY=sk-ant-... node server.js
//
// Then open: http://localhost:8080

const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = parseInt(process.argv[2]) || 8080;
const API_KEY = process.env.ANTHROPIC_API_KEY || '';
const DIR = __dirname;

const MIME = {
  '.html': 'text/html',
  '.css':  'text/css',
  '.js':   'application/javascript',
  '.json': 'application/json',
  '.png':  'image/png',
  '.ico':  'image/x-icon',
};

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, x-api-key, anthropic-version',
};

// Patch HTML file once on startup
function patchHtml() {
  const src = path.join(DIR, 'ComplyLine_v4.html');
  const dst = path.join(DIR, 'ComplyLine_v4_local.html');

  if (!fs.existsSync(src)) {
    console.log('\n  ⚠  ComplyLine_v4.html not found in', DIR);
    console.log('     Put it in the same folder as server.js\n');
    return false;
  }

  let html = fs.readFileSync(src, 'utf8');
  const old = 'https://api.anthropic.com/v1/messages';
  const patch = `http://localhost:${PORT}/api/claude`;

  if (!html.includes(old)) {
    console.log('  ⚠  URL already patched or file is different version — using as-is');
    fs.writeFileSync(dst, html);
    return true;
  }

  html = html.split(old).join(patch);
  fs.writeFileSync(dst, html);
  console.log(`  ✓ Created ComplyLine_v4_local.html`);
  return true;
}

// Proxy request to Anthropic API
function proxyToAnthropic(req, res) {
  let body = '';
  req.on('data', chunk => body += chunk);
  req.on('end', () => {
    const apiKey = req.headers['x-api-key'] || API_KEY;
    if (!apiKey) {
      res.writeHead(400, { 'Content-Type': 'application/json', ...CORS });
      res.end(JSON.stringify({ error: { message: 'No API key. Set ANTHROPIC_API_KEY or enter it in Settings.' } }));
      return;
    }

    const options = {
      hostname: 'api.anthropic.com',
      port: 443,
      path: '/v1/messages',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
    };

    const proxy = https.request(options, (apiRes) => {
      let data = '';
      apiRes.on('data', chunk => data += chunk);
      apiRes.on('end', () => {
        res.writeHead(apiRes.statusCode, { 'Content-Type': 'application/json', ...CORS });
        res.end(data);
        console.log(`  ✓ Claude API → ${data.length} bytes (${apiRes.statusCode})`);
      });
    });

    proxy.on('error', (e) => {
      console.error('  ✗ Proxy error:', e.message);
      res.writeHead(500, { 'Content-Type': 'application/json', ...CORS });
      res.end(JSON.stringify({ error: { message: e.message } }));
    });

    proxy.setTimeout(120000);
    proxy.write(body);
    proxy.end();
  });
}

// Serve static files
function serveFile(req, res) {
  let filePath = path.join(DIR, req.url === '/' ? 'ComplyLine_v4_local.html' : req.url);
  const ext = path.extname(filePath);

  fs.readFile(filePath, (err, data) => {
    if (err) {
      // Try index
      if (req.url === '/') {
        res.writeHead(302, { Location: '/ComplyLine_v4_local.html' });
        res.end();
        return;
      }
      res.writeHead(404);
      res.end('Not found');
      return;
    }
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'text/plain', ...CORS });
    res.end(data);
  });
}

// Create server
const server = http.createServer((req, res) => {
  // CORS preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(200, CORS);
    res.end();
    return;
  }
  // API proxy
  if (req.method === 'POST' && req.url === '/api/claude') {
    proxyToAnthropic(req, res);
    return;
  }
  // Static files
  serveFile(req, res);
});

// Start
if (!patchHtml()) process.exit(1);

server.listen(PORT, 'localhost', () => {
  const appUrl = `http://localhost:${PORT}/ComplyLine_v4_local.html`;
  console.log('\n' + '═'.repeat(52));
  console.log('  ⚖  ComplyLine — Credit Card Compliance Platform');
  console.log('═'.repeat(52));
  console.log(`\n  🌐  Open this in your browser:`);
  console.log(`      ${appUrl}`);
  if (API_KEY) {
    console.log(`  🔑  API key loaded from environment`);
  } else {
    console.log(`  🔑  No API key set — enter it in Settings`);
  }
  console.log('\n  Press Ctrl+C to stop\n');

  // Try to open browser automatically
  const { exec } = require('child_process');
  const cmd = process.platform === 'win32' ? `start ${appUrl}`
             : process.platform === 'darwin' ? `open ${appUrl}`
             : `xdg-open ${appUrl}`;
  exec(cmd);
});
