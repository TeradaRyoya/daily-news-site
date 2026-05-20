/**
 * Cloudflare Worker — Notion API CORS proxy
 * 環境変数: NOTION_TOKEN (Cloudflare Worker の Secrets に設定)
 */

const ALLOWED_ORIGIN = 'https://teradaryoya.github.io';

const corsHeaders = {
  'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
  'Access-Control-Allow-Methods': 'PATCH, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

export default {
  async fetch(request, env) {
    // プリフライトリクエスト
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    if (request.method !== 'PATCH') {
      return new Response('Method Not Allowed', { status: 405 });
    }

    // URL: /{block_id}
    const blockId = new URL(request.url).pathname.slice(1);
    if (!blockId) {
      return new Response('Block ID required', { status: 400 });
    }

    const body = await request.text();

    const notionRes = await fetch(`https://api.notion.com/v1/blocks/${blockId}`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${env.NOTION_TOKEN}`,
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json',
      },
      body,
    });

    const data = await notionRes.text();
    return new Response(data, {
      status: notionRes.status,
      headers: {
        'Content-Type': 'application/json',
        ...corsHeaders,
      },
    });
  },
};
