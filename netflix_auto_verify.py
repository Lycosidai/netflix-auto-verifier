#!/usr/bin/env python3
"""
Netflix Auto-Verifier
Checks Gmail via IMAP for Netflix verification emails and auto-verifies them.
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
from datetime import datetime

# Configuration
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'imap_config.json')
PROCESSED_FILE = os.path.join(os.path.dirname(__file__), 'processed_emails.json')

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
    """Extract email body text"""
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
    """Extract Netflix verification links from email body"""
    # Look for travel/verify links (temporary access code verification)
    patterns = [
        r'https://www\.netflix\.com/account/travel/verify\?[^\s"\'<>\]]+',
        r'https://www\.netflix\.com/account/verify\?[^\s"\'<>\]]+',
    ]
    
    links = []
    for pattern in patterns:
        matches = re.findall(pattern, body)
        links.extend(matches)
    
    # Clean up links (remove trailing brackets, etc.)
    cleaned = []
    for link in links:
        link = link.rstrip(']').rstrip('>')
        if link not in cleaned:
            cleaned.append(link)
    
    return cleaned

def verify_link(url):
    """Visit the verification link to complete verification"""
    try:
        # Create SSL context
        ctx = ssl.create_default_context()
        
        # Create request with browser-like headers
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        
        # Follow redirects and get final response
        response = urllib.request.urlopen(req, timeout=30, context=ctx)
        final_url = response.geturl()
        status = response.status
        content = response.read().decode('utf-8', errors='replace')[:2000]
        
        # Check if verification was successful
        success_indicators = [
            'verified', 'success', '驗證成功', '已驗證',
            'thank you', '謝謝', 'confirmed', '確認'
        ]
        
        is_success = any(ind.lower() in content.lower() for ind in success_indicators)
        
        return {
            'success': is_success or status == 200,
            'status': status,
            'final_url': final_url,
            'content_preview': content[:500]
        }
    except urllib.error.HTTPError as e:
        return {'success': False, 'error': f'HTTP {e.code}: {e.reason}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def check_and_verify():
    """Main function: check Gmail and verify Netflix emails"""
    config = load_config()
    processed = load_processed()
    
    print(f"[{datetime.now().isoformat()}] Checking Gmail for Netflix emails...")
    
    try:
        # Connect to Gmail IMAP
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(config['email'], config['app_password'])
        mail.select('INBOX')
        
        # Search for Netflix emails (unread first, or recent if testing)
        # Try unread first
        status, messages = mail.search(None, '(UNSEEN FROM "netflix")')
        
        # If no unread, check recent ones for testing (remove this in production)
        if status == 'OK' and not messages[0].strip():
            print("No unread emails, checking recent Netflix emails...")
            status, messages = mail.search(None, '(FROM "netflix")')
        
        if status != 'OK':
            print("Failed to search emails")
            return
        
        email_ids = messages[0].split()
        
        if not email_ids:
            print("No new Netflix emails")
            mail.logout()
            return
        
        print(f"Found {len(email_ids)} new Netflix email(s)")
        
        for email_id in email_ids:
            email_id_str = email_id.decode()
            
            if email_id_str in processed:
                continue
            
            # Fetch email
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status != 'OK':
                continue
            
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            subject = decode_mime_header(msg['Subject'])
            from_addr = decode_mime_header(msg['From'])
            date = msg['Date']
            
            print(f"\n=== Processing Email ===")
            print(f"From: {from_addr}")
            print(f"Date: {date}")
            print(f"Subject: {subject}")
            
            # Get body and extract verification links
            body = get_email_body(msg)
            links = extract_verification_links(body)
            
            if links:
                print(f"Found {len(links)} verification link(s)")
                
                for link in links:
                    print(f"\nVerifying: {link[:80]}...")
                    result = verify_link(link)
                    
                    if result.get('success'):
                        print(f"✓ Verification SUCCESS!")
                        print(f"  Final URL: {result.get('final_url', 'N/A')}")
                    else:
                        print(f"✗ Verification may have failed: {result.get('error', 'Unknown')}")
                    
                    # Only try first link
                    break
            else:
                # Look for verification codes
                codes = re.findall(r'\b\d{4,6}\b', body)
                if codes:
                    print(f"Verification codes found: {', '.join(codes[:3])}")
                else:
                    print("No verification links or codes found")
            
            # Mark as processed
            processed.add(email_id_str)
        
        save_processed(processed)
        mail.logout()
        print(f"\nDone!")
        
    except imaplib.IMAP4.error as e:
        print(f"IMAP Error: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_and_verify()
