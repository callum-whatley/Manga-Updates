"""
Run once after initial migration to import existing manga from the old manga.json.
Usage: flask shell < seed_manga.py  OR  python seed_manga.py
"""
from dotenv import load_dotenv
load_dotenv()

import re
import json
from app import create_app
from app.extensions import db
from app.models import Manga
from app.scrapers import fetch_manga_info

LEGACY_JSON = 'MangaUpdates/manga.json'


def slugify(title: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')


app = create_app()

with app.app_context():
    with open(LEGACY_JSON, encoding='utf-8') as f:
        legacy = json.load(f)

    added = 0
    for item in legacy:
        title = item['name']
        slug = slugify(title)
        if Manga.query.filter_by(slug=slug).first():
            print(f'  skip (exists): {title}')
            continue

        print(f'  fetching info: {title}')
        info = fetch_manga_info(title)

        manga = Manga(
            title=info.get('title', title),
            slug=slug,
            cover_url=info.get('cover_url'),
            mangadex_id=info.get('mangadex_id'),
            asura_url=info.get('asura_url'),
            latest_chapter=info.get('latest_chapter', float(str(item['chapter']).replace(',', ''))),
            latest_chapter_url=info.get('latest_chapter_url'),
        )
        db.session.add(manga)
        added += 1

    db.session.commit()
    print(f'\nDone — {added} manga imported.')
