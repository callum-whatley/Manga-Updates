import requests
import json
import re
import time
import os
from cachetools import cached, TTLCache
from bs4 import BeautifulSoup
from flask import Flask, abort, render_template, url_for, request
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ['FLASK_SECRET_KEY']
csrf = CSRFProtect(app)

# Constants
JSON_FILE = 'manga.json'
REQUEST_TIMEOUT = 10
CACHE_DURATION = 3600 # 1 hour


def safe_file_operation(filename, mode='r', default=None, encoder=None):
    """Safe file handling with context manager and error handling"""
    try:
        with open(filename, mode, encoding='utf-8') as f:
            return json.load(f) if 'r' in mode else encoder(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"File error: {str(e)}")
        return default if default is not None else []

def parse_chapter(chapter_str):
    """Extract numerical value from chapter string"""
    match = re.search(r'(\d+\.?\d*)', str(chapter_str))
    return float(match.group(1)) if match else 0.0

@cached(cache=TTLCache(maxsize=32, ttl=3600))
def fetch_updates(url):
    """Cached and rate-limited web requests"""
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {str(e)}")
        return None

def process_taad_updates(content):
    """Parse Taadd website updates"""
    results = []
    soup = BeautifulSoup(content, 'html.parser')
    
    for item in soup.select('div.intro'):
        links = item.find_all('a')
        if len(links) < 2:
            continue
            
        full_text = links[1].get_text(strip=True)
        
        # Enhanced chapter detection using regex
        chapter_match = re.search(
            r'(.*?)((?:Ch\.?\s*)?\d+\.?\d*)(?:\s*-\s*.*)?$', 
            full_text, 
            re.IGNORECASE
        )
        
        if chapter_match:
            name_part = chapter_match.group(1).strip()
            chapter_part = chapter_match.group(2).strip()
            
            # Clean any remaining "Ch" text in name
            name_part = re.sub(r'\s+Ch\.?\s*$', '', name_part, flags=re.IGNORECASE)
        else:
            # Fallback if no chapter found
            name_part = full_text
            chapter_part = "0"
        
        if name_part and chapter_part:
            results.append({
                'name': name_part,
                'chapter': chapter_part,
                'source': 'taadd'
            })
    return results

def process_asura_updates(content):
    """Parse AsuraScans website updates"""
    results = []
    soup = BeautifulSoup(content, 'html.parser')
    
    for item in soup.select(r'div.block.w-\[100\%\].h-auto.items-center'):
        spans = item.find_all('span')
        if len(spans) < 3:
            continue
            
        name_part = spans[0].get_text(strip=True)
        try:
            # Remove commas and convert to float (handles whole numbers and decimals)
            chapter_part = float(re.search(r'(?i)Chapter\s+(\d+\.?\d*)', spans[1].get_text()).group(1).replace(',', ''))
        except ValueError:
            chapter_part = 0.0
        
        if name_part and chapter_part:
            results.append({
                'name': name_part,
                'chapter': chapter_part,
                'source': 'asura'
            })
    return results

# Deprecated
""" def process_readmng_updates(content):
    results = []
    soup = BeautifulSoup(content, 'html.parser')
    
    for item in soup.select('div.manga_updates a'):
        text = item.get_text(strip=True)
        if ' - ' in text:
            name, chapter = text.split(' - ', 1)
            results.append({
                'name': name.strip(),
                'chapter': chapter.strip(),
                'source': 'readmng'
            })
    return results """

@app.route('/')
def root():
    """Main dashboard view"""
    manga_list = safe_file_operation(JSON_FILE, default=[])
    return render_template('index.html', data=manga_list)

@app.route('/updates')
def updates():
    """Update checking and processing"""
    manga_data = safe_file_operation(JSON_FILE, default=[])
    
    # Fetch updates from available sources
    taad_content = fetch_updates("https://www.taadd.com/list/New-Update")
    asura_content = fetch_updates("https://asuracomic.net/series")
    #readmng_content = fetch_updates("https://readmng.com/latest-releases")
    
    taad_updates = process_taad_updates(taad_content) if taad_content else []
    asura_updates = process_asura_updates(asura_content) if asura_content else []
    #readmng_updates = process_readmng_updates(readmng_content) if readmng_content else []
    
    # Merge updates using dictionary for O(1) lookups
    merged_updates = {}
    for update in asura_updates + taad_updates:
        key = update['name'].lower()
        existing = merged_updates.get(key)
        
        if not existing or parse_chapter(update['chapter']) > parse_chapter(existing['chapter']):
            merged_updates[key] = update
    
    # Find updates and prepare response
    changes = []
    for manga in manga_data:
        manga_key = manga['name'].lower()
        remote = merged_updates.get(manga_key)
        
        if remote and parse_chapter(remote['chapter']) > parse_chapter(manga['chapter']):
            changes.append({
                'name': manga['name'],
                'oldchapter': manga['chapter'],
                'newchapter': remote['chapter'],
                'source': remote['source']
            })
            manga['chapter'] = remote['chapter']
    
    # Save updated data
    if changes:
        safe_file_operation(JSON_FILE, 'w', encoder=lambda f: json.dump(manga_data, f, indent=4))
    
    return render_template('index.html', data=manga_data, updates=changes)

@app.route('/remove', methods=['POST'])
def remove():
    """Handle manga removal"""
    manga_data = safe_file_operation(JSON_FILE, default=[])
    names = request.form.getlist('manga_name')
    
    # Validation
    if not names or len(names) > 1:
        abort(400, "Invalid removal request")
        
    target = names[0].lower()
    original_count = len(manga_data)
    
    # Filter instead of modifying during iteration
    manga_data = [m for m in manga_data if m['name'].lower() != target]
    
    if len(manga_data) == original_count:
        abort(404, "Manga not found")
    
    safe_file_operation(JSON_FILE, 'w', encoder=lambda f: json.dump(manga_data, f, indent=4))
    return render_template('index.html', data=manga_data)

@app.route('/add', methods=['POST'])
def add():
    """Handle new manga additions"""
    manga_data = safe_file_operation(JSON_FILE, default=[])
    new_name = request.form.get('manga-name', '').strip()
    print(new_name)
    print(request.form)
    
    if not new_name:
        abort(400, "Invalid manga name")
    
    # Check for duplicates
    normalized_new = new_name.lower()
    if any(m['name'].lower() == normalized_new for m in manga_data):
        abort(409, "Manga already exists")
    
    manga_data.append({
        'name': new_name,
        'chapter': "0",
    })
    
    safe_file_operation(JSON_FILE, 'w', encoder=lambda f: json.dump(manga_data, f, indent=4))
    return render_template('index.html', data=manga_data)

@app.errorhandler(404)
def handle_404(e):
    return render_template('error.html', message=str(e)), 404

@app.errorhandler(400)
def handle_400(e):
    return render_template('error.html', message=str(e)), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)