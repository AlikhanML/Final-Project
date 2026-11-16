import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from services import contact_store as store


class ContactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = patch.object(store, 'DB_PATH', Path(self.temp.name) / 'chat.sqlite3')
        self.db.start()
        self.addCleanup(self.db.stop)
        self.room = store.create_room()

    def test_two_parties_and_isolation(self):
        store.send_message(self.room['dispatcher'], 'Жолдамыз', 'd1')
        store.send_message(self.room['caller'], 'Күтіп тұрмын', 'c1')
        data = store.snapshot(self.room['caller'])
        self.assertEqual([m['role'] for m in data['messages']], ['dispatcher', 'caller'])
        self.assertEqual(data['messages'][1]['body'], 'Күтіп тұрмын')
        other = store.create_room()
        self.assertEqual(store.snapshot(other['dispatcher'])['messages'], [])
        with self.assertRaises(ValueError):
            store.snapshot('unknown-token-that-is-long-enough')

    def test_retry_and_concurrent_writes(self):
        def send(_):
            store.send_message(self.room['caller'], 'Сәлем', 'same-request')
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(send, range(8)))
        self.assertEqual(len(store.snapshot(self.room['dispatcher'])['messages']), 1)
        store.send_message(self.room['dispatcher'], 'Сәлем', 'same-request')
        self.assertEqual(len(store.snapshot(self.room['caller'])['messages']), 2)

    def test_phone_and_invalid_messages(self):
        self.assertEqual(store.save_phone(self.room['caller'], '+7 (701) 123-45-67'), '+77011234567')
        self.assertEqual(store.snapshot(self.room['dispatcher'])['phone'], '+77011234567')
        for number in ['javascript:alert(1)', '103', '+77abc12345']:
            with self.assertRaises(ValueError):
                store.save_phone(self.room['caller'], number)
        for body in [' ', 'a' * 2001]:
            with self.assertRaises(ValueError):
                store.send_message(self.room['caller'], body, 'bad')

    def test_closed_and_expired_rooms(self):
        with self.assertRaises(ValueError):
            store.close_room(self.room['caller'])
        store.close_room(self.room['dispatcher'])
        with self.assertRaises(ValueError):
            store.send_message(self.room['caller'], 'test', 'closed')
        another = store.create_room()
        with patch('services.contact_store.time.time', return_value=10**12):
            with self.assertRaises(ValueError):
                store.snapshot(another['caller'])
