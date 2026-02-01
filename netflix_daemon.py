#!/usr/bin/env python3
"""
Netflix Auto-Verifier Daemon
Runs continuously, checking every N seconds for new Netflix verification emails.
"""

import imaplib
import email
from email.header import decode_header
import re
import urllib.request
import urllib.error
import json
import os
import ssl
import time
import sys
from datetime import datetime, timezone, timedelta

# Taiwan timezone (UTC+8)
TW_TZ = timezone(timedelta(hours=8))

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'imap_config.json')
PROCESSED_FILE = os.path.join(SCRIPT_DIR, 'processed_emails.json')
LOG_FILE = os.path.join(SCRIPT_DIR, 'daemon.log')

CHECK_INTERVAL = 30  # seconds

def log(msg):
    timestamp = datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def load_processed():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_processed(processed):
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(list(processed), f)

def decode_mime_header(header):
    if header is None:
        return ""
    decoded_parts = decode_header(header)
    result = ""
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result += part.decode(charset or 'utf-8', errors='replace')
        else:
            result += part
    return result

def get_email_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    body += payload.decode(charset, errors='replace')
                except:
                    pass
            elif content_type == "text/html" and not body:
                try:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    body += payload.decode(charset, errors='replace')
                except:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or 'utf-8'
            body = payload.decode(charset, errors='replace')
        except:
            pass
    return body

def extract_verification_links(body):
    patterns = [
        r'https://www\.netflix\.com/account/travel/verify\?[^\s"\'<>\]]+',
        r'https://www\.netflix\.com/account/verify\?[^\s"\'<>\]]+',
    ]
    
    links = []
    for pattern in patterns:
        matches = re.findall(pattern, body)
        links.extend(matches)
    
    cleaned = []
    for link in links:
        link = link.rstrip(']').rstrip('>')
        if link not in cleaned:
            cleaned.append(link)
    
    return cleaned

def verify_link(url):
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        
        response = urllib.request.urlopen(req, timeout=30, context=ctx)
        final_url = response.geturl()
        status = response.status
        
        return {'success': status == 200, 'status': status, 'final_url': final_url}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def check_once(config, processed):
    """Single check iteration"""
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(config['email'], config['app_password'])
        mail.select('INBOX')
        
        # Only check UNREAD Netflix emails
        status, messages = mail.search(None, '(UNSEEN FROM "netflix")')
        
        if status != 'OK' or not messages[0].strip():
            mail.logout()
            return 0
        
        email_ids = messages[0].split()
        verified_count = 0
        
        for email_id in email_ids:
            email_id_str = email_id.decode()
            
            if email_id_str in processed:
                continue
            
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status != 'OK':
                continue
            
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            subject = decode_mime_header(msg['Subject'])
            
            # Only process verification emails
            if '存取碼' not in subject and 'verify' not in subject.lower():
                processed.add(email_id_str)
                continue
            
            log(f"📧 New Netflix verification email: {subject}")
            
            body = get_email_body(msg)
            links = extract_verification_links(body)
            
            if links:
                link = links[0]
                log(f"🔗 Clicking verification link...")
                result = verify_link(link)
                
                if result.get('success'):
                    log(f"✅ Verification link clicked successfully!")
                    verified_count += 1
                else:
                    log(f"❌ Failed: {result.get('error', 'Unknown error')}")
            
            processed.add(email_id_str)
        
        save_processed(processed)
        mail.logout()
        return verified_count
        
    except Exception as e:
        log(f"Error: {e}")
        return 0

def main():
    log("🚀 Netflix Auto-Verifier Daemon started")
    log(f"⏰ Checking every {CHECK_INTERVAL} seconds")
    
    config = load_config()
    processed = load_processed()
    
    while True:
        try:
            count = check_once(config, processed)
            if count > 0:
                log(f"✨ Verified {count} email(s)")
        except KeyboardInterrupt:
            log("👋 Daemon stopped")
            sys.exit(0)
        except Exception as e:
            log(f"Loop error: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()
