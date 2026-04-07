from flask import Flask, render_template, request, jsonify, send_from_directory
import sqlite3, os, re, uuid
from datetime import datetime

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'brain.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'data', 'uploads')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS notes (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            done INTEGER DEFAULT 0,
            urgency TEXT DEFAULT 'someday',
            topic TEXT DEFAULT '',
            source_tag TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tags (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS note_tags (
            note_id TEXT NOT NULL,
            tag_id TEXT NOT NULL,
            PRIMARY KEY (note_id, tag_id)
        );
        CREATE TABLE IF NOT EXISTS note_links (
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            PRIMARY KEY (from_id, to_id)
        );
        CREATE TABLE IF NOT EXISTS attachments (
            id TEXT PRIMARY KEY,
            note_id TEXT NOT NULL,
            attach_type TEXT NOT NULL,
            value TEXT NOT NULL,
            thumbnail TEXT DEFAULT '',
            title TEXT DEFAULT ''
        );
    """)
    conn.commit()
    conn.close()

def enrich_note(conn, row):
    note = dict(row)
    tags = conn.execute(
        'SELECT t.id, t.name FROM tags t JOIN note_tags nt ON t.id=nt.tag_id WHERE nt.note_id=?',
        (note['id'],)
    ).fetchall()
    note['tags'] = [dict(t) for t in tags]
    attachments = conn.execute('SELECT * FROM attachments WHERE note_id=?', (note['id'],)).fetchall()
    note['attachments'] = [dict(a) for a in attachments]
    linked = conn.execute("""
        SELECT n.id, n.title, n.type FROM notes n
        JOIN note_links nl ON (nl.to_id=n.id AND nl.from_id=?) OR (nl.from_id=n.id AND nl.to_id=?)
    """, (note['id'], note['id'])).fetchall()
    note['linked_notes'] = [dict(l) for l in linked]
    return note

def upsert_tags(conn, note_id, tag_names):
    conn.execute('DELETE FROM note_tags WHERE note_id=?', (note_id,))
    for name in tag_names:
        name = name.strip()
        if not name:
            continue
        existing = conn.execute('SELECT id FROM tags WHERE name=?', (name,)).fetchone()
        if existing:
            tid = existing['id']
        else:
            tid = str(uuid.uuid4())
            conn.execute('INSERT INTO tags (id, name) VALUES (?,?)', (tid, name))
        conn.execute('INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?,?)', (note_id, tid))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.route('/api/notes', methods=['GET'])
def get_notes():
    ntype = request.args.get('type')
    conn = get_db()
    if ntype:
        rows = conn.execute('SELECT * FROM notes WHERE type=? ORDER BY created_at DESC', (ntype,)).fetchall()
    else:
        rows = conn.execute('SELECT * FROM notes ORDER BY created_at DESC').fetchall()
    result = [enrich_note(conn, r) for r in rows]
    conn.close()
    return jsonify(result)

@app.route('/api/notes/<note_id>', methods=['GET'])
def get_note(note_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM notes WHERE id=?', (note_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'not found'}), 404
    result = enrich_note(conn, row)
    conn.close()
    return jsonify(result)

@app.route('/api/notes', methods=['POST'])
def create_note():
    data = request.json
    now = datetime.now().isoformat()
    nid = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        'INSERT INTO notes (id,type,title,content,done,urgency,topic,source_tag,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
        (nid, data['type'], data['title'], data.get('content',''), 0,
         data.get('urgency','someday'), data.get('topic',''), data.get('source_tag',''), now, now)
    )
    upsert_tags(conn, nid, data.get('tags', []))
    for lid in data.get('linked_notes', []):
        conn.execute('INSERT OR IGNORE INTO note_links (from_id, to_id) VALUES (?,?)', (nid, lid))
    conn.commit()
    conn.close()
    return jsonify({'id': nid, 'created_at': now})

@app.route('/api/notes/<note_id>', methods=['PUT'])
def update_note(note_id):
    data = request.json
    now = datetime.now().isoformat()
    conn = get_db()
    fields = ['title','content','done','urgency','topic','source_tag']
    updates = {f: data[f] for f in fields if f in data}
    updates['updated_at'] = now
    set_clause = ', '.join(f'{k}=?' for k in updates)
    conn.execute(f'UPDATE notes SET {set_clause} WHERE id=?', list(updates.values()) + [note_id])
    if 'tags' in data:
        upsert_tags(conn, note_id, data['tags'])
    if 'linked_notes' in data:
        conn.execute('DELETE FROM note_links WHERE from_id=? OR to_id=?', (note_id, note_id))
        for lid in data['linked_notes']:
            if lid != note_id:
                conn.execute('INSERT OR IGNORE INTO note_links (from_id,to_id) VALUES (?,?)', (note_id, lid))
    conn.commit()
    conn.close()
    return jsonify({'updated': True})

@app.route('/api/notes/<note_id>', methods=['DELETE'])
def delete_note(note_id):
    conn = get_db()
    conn.execute('DELETE FROM note_tags WHERE note_id=?', (note_id,))
    conn.execute('DELETE FROM note_links WHERE from_id=? OR to_id=?', (note_id, note_id))
    conn.execute('DELETE FROM attachments WHERE note_id=?', (note_id,))
    conn.execute('DELETE FROM notes WHERE id=?', (note_id,))
    conn.commit()
    conn.close()
    return jsonify({'deleted': True})

@app.route('/api/notes/<note_id>/toggle', methods=['POST'])
def toggle_todo(note_id):
    conn = get_db()
    row = conn.execute('SELECT done FROM notes WHERE id=?', (note_id,)).fetchone()
    new_done = 0
    if row:
        new_done = 0 if row['done'] else 1
        conn.execute('UPDATE notes SET done=? WHERE id=?', (new_done, note_id))
        conn.commit()
    conn.close()
    return jsonify({'done': new_done})

@app.route('/api/tags', methods=['GET'])
def get_tags():
    conn = get_db()
    tags = conn.execute('SELECT * FROM tags ORDER BY name').fetchall()
    conn.close()
    return jsonify([dict(t) for t in tags])

@app.route('/api/attachments', methods=['POST'])
def add_attachment():
    aid = str(uuid.uuid4())
    if request.content_type and 'multipart' in request.content_type:
        note_id = request.form.get('note_id', '')
        file = request.files.get('file')
        if not file:
            return jsonify({'error': 'no file'}), 400
        ext = os.path.splitext(file.filename)[1].lower()
        filename = f'{aid}{ext}'
        file.save(os.path.join(UPLOAD_DIR, filename))
        value = f'/uploads/{filename}'
        thumbnail = value
        title = file.filename
        attach_type = 'image'
    else:
        data = request.json
        note_id = data.get('note_id', '')
        url = data.get('url', '')
        value = url
        attach_type = 'url'
        thumbnail, title = fetch_url_meta(url)
    conn = get_db()
    conn.execute(
        'INSERT INTO attachments (id,note_id,attach_type,value,thumbnail,title) VALUES (?,?,?,?,?,?)',
        (aid, note_id, attach_type, value, thumbnail, title)
    )
    conn.commit()
    conn.close()
    return jsonify({'id': aid, 'attach_type': attach_type, 'value': value, 'thumbnail': thumbnail, 'title': title})

@app.route('/api/attachments/<aid>', methods=['DELETE'])
def delete_attachment(aid):
    conn = get_db()
    row = conn.execute('SELECT value, attach_type FROM attachments WHERE id=?', (aid,)).fetchone()
    if row and row['attach_type'] == 'image':
        try:
            path = os.path.join(BASE_DIR, row['value'].lstrip('/'))
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
    conn.execute('DELETE FROM attachments WHERE id=?', (aid,))
    conn.commit()
    conn.close()
    return jsonify({'deleted': True})

def fetch_url_meta(url):
    try:
        import requests
        from bs4 import BeautifulSoup
        yt = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
        if yt:
            vid = yt.group(1)
            return f'https://img.youtube.com/vi/{vid}/mqdefault.jpg', 'YouTube 영상'
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        r = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')
        og_img = soup.find('meta', property='og:image')
        thumbnail = og_img['content'] if og_img and og_img.get('content') else ''
        og_title = soup.find('meta', property='og:title')
        title = og_title['content'] if og_title and og_title.get('content') else (soup.title.string if soup.title else url)
        return thumbnail, (title or url)[:120]
    except Exception:
        return '', url[:120]

@app.route('/api/graph', methods=['GET'])
def get_graph():
    conn = get_db()
    notes = conn.execute('SELECT id, type, title, done FROM notes').fetchall()
    visible_tags = conn.execute("""
        SELECT t.id, t.name, COUNT(nt.note_id) as cnt
        FROM tags t JOIN note_tags nt ON t.id=nt.tag_id
        GROUP BY t.id HAVING cnt >= 2
    """).fetchall()
    visible_tag_ids = {t['id'] for t in visible_tags}
    note_tags_rows = conn.execute("""
        SELECT nt.note_id, nt.tag_id FROM note_tags nt
        WHERE nt.tag_id IN (SELECT tag_id FROM note_tags GROUP BY tag_id HAVING COUNT(*) >= 2)
    """).fetchall()
    note_links_rows = conn.execute('SELECT from_id, to_id FROM note_links').fetchall()
    conn.close()

    nodes = []
    edges = []
    eid = 0

    for n in notes:
        nodes.append({
            'id': n['id'], 'group': n['type'],
            'label': n['title'][:22] + ('…' if len(n['title']) > 22 else ''),
            'done': bool(n['done']), 'fullTitle': n['title']
        })
    for t in visible_tags:
        nodes.append({'id': t['id'], 'group': 'tag', 'label': t['name'], 'cnt': t['cnt']})
    for nt in note_tags_rows:
        edges.append({'id': f'e{eid}', 'from': nt['note_id'], 'to': nt['tag_id'], 'etype': 'tag'})
        eid += 1
    seen = set()
    for nl in note_links_rows:
        key = tuple(sorted([nl['from_id'], nl['to_id']]))
        if key not in seen:
            seen.add(key)
            edges.append({'id': f'e{eid}', 'from': nl['from_id'], 'to': nl['to_id'], 'etype': 'link'})
            eid += 1

    return jsonify({'nodes': nodes, 'edges': edges})

if __name__ == '__main__':
    init_db()
    import webbrowser, threading
    def open_browser():
        import time; time.sleep(1.2)
        webbrowser.open('http://localhost:5001')
    threading.Thread(target=open_browser, daemon=True).start()
    print('\n\U0001f9e0 Second Brain \uc2dc\uc791!')
    print('\U0001f449  http://localhost:5001')
    print('\uc885\ub8cc\ud558\ub824\uba74 Ctrl+C \ub97c \ub204\ub974\uc138\uc694\n')
    app.run(debug=False, port=5001)


# standalone URL meta (no DB save)
@app.route('/api/url-meta', methods=['POST'])
def url_meta():
    data = request.json or {}
    thumbnail, title = fetch_url_meta(data.get('url', ''))
    return jsonify({'thumbnail': thumbnail, 'title': title})
