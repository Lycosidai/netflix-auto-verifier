const https = require('https');
const fs = require('fs');
const path = require('path');

const CREDS_PATH = path.join(__dirname, 'credentials.json');
const creds = JSON.parse(fs.readFileSync(CREDS_PATH, 'utf8'));

function httpsRequest(options, postData = null) {
  return new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          resolve(data);
        }
      });
    });
    req.on('error', reject);
    if (postData) req.write(postData);
    req.end();
  });
}

async function getAccessToken() {
  const params = new URLSearchParams({
    client_id: creds.client_id,
    client_secret: creds.client_secret,
    refresh_token: creds.refresh_token,
    grant_type: 'refresh_token'
  });

  const result = await httpsRequest({
    hostname: 'oauth2.googleapis.com',
    path: '/token',
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  }, params.toString());

  return result.access_token;
}

async function searchEmails(accessToken, query) {
  const encodedQuery = encodeURIComponent(query);
  return await httpsRequest({
    hostname: 'gmail.googleapis.com',
    path: `/gmail/v1/users/me/messages?q=${encodedQuery}&maxResults=5`,
    method: 'GET',
    headers: { 'Authorization': `Bearer ${accessToken}` }
  });
}

async function getMessage(accessToken, messageId) {
  return await httpsRequest({
    hostname: 'gmail.googleapis.com',
    path: `/gmail/v1/users/me/messages/${messageId}?format=full`,
    method: 'GET',
    headers: { 'Authorization': `Bearer ${accessToken}` }
  });
}

function decodeBase64Url(data) {
  if (!data) return '';
  const base64 = data.replace(/-/g, '+').replace(/_/g, '/');
  return Buffer.from(base64, 'base64').toString('utf8');
}

function extractBody(payload) {
  // Try to get text/plain part
  if (payload.parts) {
    for (const part of payload.parts) {
      if (part.mimeType === 'text/plain' && part.body?.data) {
        return decodeBase64Url(part.body.data);
      }
      if (part.parts) {
        const nested = extractBody(part);
        if (nested) return nested;
      }
    }
    // Fallback to text/html
    for (const part of payload.parts) {
      if (part.mimeType === 'text/html' && part.body?.data) {
        return decodeBase64Url(part.body.data);
      }
    }
  }
  // Direct body
  if (payload.body?.data) {
    return decodeBase64Url(payload.body.data);
  }
  return '';
}

function extractVerificationInfo(body, subject) {
  const result = { codes: [], links: [] };
  
  // Extract 4-8 digit codes (common for verification)
  const codeMatches = body.match(/\b\d{4,8}\b/g) || [];
  result.codes = [...new Set(codeMatches)].slice(0, 5);
  
  // Extract Netflix links
  const linkMatches = body.match(/https:\/\/[^\s"'<>]+netflix[^\s"'<>]*/gi) || [];
  result.links = [...new Set(linkMatches)].slice(0, 5);
  
  return result;
}

async function main() {
  try {
    const accessToken = await getAccessToken();
    if (!accessToken) {
      console.log('ERROR: Failed to get access token');
      process.exit(1);
    }

    // Search for Netflix emails from last 24h
    const query = 'from:netflix is:unread newer_than:1d';
    const searchResult = await searchEmails(accessToken, query);

    if (!searchResult.messages || searchResult.messages.length === 0) {
      console.log('NO_NEW_NETFLIX_EMAILS');
      return;
    }

    console.log(`Found ${searchResult.messages.length} Netflix email(s)\n`);

    for (const msg of searchResult.messages) {
      const fullMsg = await getMessage(accessToken, msg.id);
      
      const subject = fullMsg.payload.headers.find(h => h.name.toLowerCase() === 'subject')?.value || '(no subject)';
      const from = fullMsg.payload.headers.find(h => h.name.toLowerCase() === 'from')?.value || '';
      const date = fullMsg.payload.headers.find(h => h.name.toLowerCase() === 'date')?.value || '';
      
      console.log(`=== Email ID: ${msg.id} ===`);
      console.log(`From: ${from}`);
      console.log(`Date: ${date}`);
      console.log(`Subject: ${subject}`);
      
      const body = extractBody(fullMsg.payload);
      const info = extractVerificationInfo(body, subject);
      
      if (info.codes.length > 0) {
        console.log(`Verification codes: ${info.codes.join(', ')}`);
      }
      if (info.links.length > 0) {
        console.log('Netflix links:');
        info.links.forEach(link => console.log(`  ${link}`));
      }
      console.log('');
    }

  } catch (err) {
    console.error('Error:', err.message);
    process.exit(1);
  }
}

main();
