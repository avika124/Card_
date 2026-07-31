// Cloudflare Worker — ComplyLine API Proxy
// Deploy at workers.cloudflare.com (free tier, no credit card)
// 
// After deploying, you get a URL like:
//   https://complyline-proxy.yourname.workers.dev
//
// Then edit ComplyLine_v4.html:
//   Replace: https://api.anthropic.com/v1/messages
//   With:    https://complyline-proxy.yourname.workers.dev/api/claude

export default {
  async fetch(request) {
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type, x-api-key, anthropic-version',
        }
      });
    }

    // Only allow POST to /api/claude
    const url = new URL(request.url);
    if (request.method !== 'POST' || url.pathname !== '/api/claude') {
      return new Response('ComplyLine Proxy — send POST to /api/claude', { status: 200 });
    }

    // Forward to Anthropic
    const body = await request.text();
    const apiKey = request.headers.get('x-api-key');

    const resp = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
      body,
    });

    const data = await resp.text();
    return new Response(data, {
      status: resp.status,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      }
    });
  }
};
