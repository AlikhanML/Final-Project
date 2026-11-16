"""Private two-party chat, persisted in SQLite on the Streamlit server."""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import os
import re
import secrets
import sqlite3
import time

DB_PATH = Path(os.getenv('QADAM_CHAT_DB', str(Path(__file__).resolve().parents[1] / 'data' / 'qadam_chat.sqlite3')))
ROOM_LIFETIME = 24 * 60 * 60


@contextmanager
def database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.executescript('''
            CREATE TABLE IF NOT EXISTS contact_rooms (
                id TEXT PRIMARY KEY, dispatcher TEXT UNIQUE NOT NULL,
                caller TEXT UNIQUE NOT NULL, phone TEXT NOT NULL DEFAULT '',
                expires REAL NOT NULL, closed INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS contact_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room TEXT NOT NULL REFERENCES contact_rooms(id),
                role TEXT NOT NULL, body TEXT NOT NULL, sent REAL NOT NULL,
                request_id TEXT NOT NULL, UNIQUE(room, role, request_id)
            );
            CREATE INDEX IF NOT EXISTS messages_by_room ON contact_messages(room, id);
        ''')
        with connection:
            yield connection
    finally:
        connection.close()


def token_hash(token):
    if not isinstance(token, str) or not 20 <= len(token) <= 100:
        raise ValueError('Чат сілтемесі жарамсыз немесе мерзімі аяқталған.')
    return sha256(token.encode()).hexdigest()


def authorize(connection, token):
    digest = token_hash(token)
    room = connection.execute(
        'SELECT * FROM contact_rooms WHERE (dispatcher=? OR caller=?) AND closed=0 AND expires>?',
        (digest, digest, time.time()),
    ).fetchone()
    if room is None:
        raise ValueError('Чат сілтемесі жарамсыз немесе мерзімі аяқталған.')
    role = 'dispatcher' if room['dispatcher'] == digest else 'caller'
    return room, role


def create_room():
    dispatcher, caller = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with database() as connection:
        connection.execute(
            'INSERT INTO contact_rooms(id, dispatcher, caller, expires) VALUES(?,?,?,?)',
            (secrets.token_hex(16), token_hash(dispatcher), token_hash(caller), time.time() + ROOM_LIFETIME),
        )
    return {'dispatcher': dispatcher, 'caller': caller}


def snapshot(token):
    with database() as connection:
        room, role = authorize(connection, token)
        messages = connection.execute(
            'SELECT id, role, body, sent FROM contact_messages WHERE room=? ORDER BY id DESC LIMIT 200',
            (room['id'],),
        ).fetchall()
        return {'role': role, 'phone': room['phone'],
                'messages': [dict(row) for row in reversed(messages)]}


def phone_number(token):
    with database() as connection:
        room, _ = authorize(connection, token)
        return room['phone']


def normalize_phone(value):
    if not isinstance(value, str):
        raise ValueError('Телефон нөмірін енгізіңіз.')
    phone = re.sub(r'[\s()\-]', '', value.strip())
    if not re.fullmatch(r'\+7[0-9]{10}', phone):
        raise ValueError('Нөмірді +7 775 713 0751 форматында енгізіңіз.')
    return phone


def save_phone(token, value):
    phone = normalize_phone(value)
    with database() as connection:
        connection.execute('BEGIN IMMEDIATE')
        room, _ = authorize(connection, token)
        connection.execute('UPDATE contact_rooms SET phone=? WHERE id=?', (phone, room['id']))
    return phone


def send_message(token, body, request_id):
    body = body.strip()
    if not body or len(body) > 2000:
        raise ValueError('Хабарлама 1–2000 таңбадан тұруы керек.')
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 100:
        raise ValueError('Хабарлама идентификаторы жарамсыз.')
    with database() as connection:
        # Serialize authorization and insert with closing the room.
        connection.execute('BEGIN IMMEDIATE')
        room, role = authorize(connection, token)
        connection.execute(
            'INSERT OR IGNORE INTO contact_messages(room, role, body, sent, request_id) VALUES(?,?,?,?,?)',
            (room['id'], role, body, time.time(), request_id),
        )


def close_room(token):
    with database() as connection:
        connection.execute('BEGIN IMMEDIATE')
        room, role = authorize(connection, token)
        if role != 'dispatcher':
            raise ValueError('Чатты тек диспетчер жаба алады.')
        connection.execute('UPDATE contact_rooms SET closed=1 WHERE id=?', (room['id'],))
