"""
Слой доступа к данным SkyVault: SQLite + шифрование полей.
"""
import os
import sqlite3
import uuid
import zipfile
from typing import Optional
from cryptography.fernet import Fernet
from encryption import encrypt_text, decrypt_text, encrypt_file, decrypt_file

class Database:
    def __init__(self, db_path: str, files_dir: str):
        self.db_path = db_path
        self.files_dir = files_dir
        self.conn = None
        self.fernet = None
        os.makedirs(files_dir, exist_ok=True)

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, phone TEXT NOT NULL,
                category TEXT NOT NULL, note TEXT);
            CREATE TABLE IF NOT EXISTS passwords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service TEXT NOT NULL, login TEXT NOT NULL,
                password TEXT NOT NULL, note TEXT);
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, doc_type TEXT NOT NULL,
                note TEXT, encrypted_file TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS instructions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, body TEXT NOT NULL);
        """)
        self.conn.commit()

    def save_master_credentials(self, salt_hex, password_hash):
        cur = self.conn.cursor()
        cur.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ("salt", salt_hex))
        cur.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", ("password_hash", password_hash))
        self.conn.commit()

    def load_master_credentials(self):
        cur = self.conn.cursor()
        salt = cur.execute("SELECT value FROM meta WHERE key='salt'").fetchone()
        phash = cur.execute("SELECT value FROM meta WHERE key='password_hash'").fetchone()
        if not salt or not phash:
            raise RuntimeError("Мастер-пароль не создан")
        return salt["value"], phash["value"]

    def set_fernet(self, fernet):
        self.fernet = fernet

    # ---- Contacts ----
    def add_contact(self, name, phone, category, note=""):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO contacts (name,phone,category,note) VALUES (?,?,?,?)",
                    (name, phone, category, encrypt_text(self.fernet, note)))
        self.conn.commit()
        return cur.lastrowid

    def update_contact(self, cid, name, phone, category, note):
        cur = self.conn.cursor()
        cur.execute("UPDATE contacts SET name=?,phone=?,category=?,note=? WHERE id=?",
                    (name, phone, category, encrypt_text(self.fernet, note), cid))
        self.conn.commit()

    def delete_contact(self, cid):
        self.conn.execute("DELETE FROM contacts WHERE id=?", (cid,))
        self.conn.commit()

    def get_contacts(self):
        rows = self.conn.execute("SELECT * FROM contacts ORDER BY name").fetchall()
        return [{"id": r["id"], "name": r["name"], "phone": r["phone"],
                 "category": r["category"], "note": decrypt_text(self.fernet, r["note"])}
                for r in rows]

    # ---- Passwords ----
    def add_password(self, service, login, password, note=""):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO passwords (service,login,password,note) VALUES (?,?,?,?)",
                    (service, encrypt_text(self.fernet, login),
                     encrypt_text(self.fernet, password),
                     encrypt_text(self.fernet, note)))
        self.conn.commit()
        return cur.lastrowid

    def update_password(self, pid, service, login, password, note):
        cur = self.conn.cursor()
        cur.execute("UPDATE passwords SET service=?,login=?,password=?,note=? WHERE id=?",
                    (service, encrypt_text(self.fernet, login),
                     encrypt_text(self.fernet, password),
                     encrypt_text(self.fernet, note), pid))
        self.conn.commit()

    def delete_password(self, pid):
        self.conn.execute("DELETE FROM passwords WHERE id=?", (pid,))
        self.conn.commit()

    def get_passwords(self):
        rows = self.conn.execute("SELECT * FROM passwords ORDER BY service").fetchall()
        return [{"id": r["id"], "service": r["service"],
                 "login": decrypt_text(self.fernet, r["login"]),
                 "password": decrypt_text(self.fernet, r["password"]),
                 "note": decrypt_text(self.fernet, r["note"])} for r in rows]

    # ---- Documents ----
    def add_document(self, title, doc_type, note, source_image_path):
        fname = f"{uuid.uuid4().hex}.enc"
        dest = os.path.join(self.files_dir, fname)
        encrypt_file(self.fernet, source_image_path, dest)
        cur = self.conn.cursor()
        cur.execute("INSERT INTO documents (title,doc_type,note,encrypted_file) VALUES (?,?,?,?)",
                    (title, doc_type, encrypt_text(self.fernet, note), fname))
        self.conn.commit()
        return cur.lastrowid

    def update_document(self, did, title, doc_type, note, source_image_path=None):
        cur = self.conn.cursor()
        if source_image_path:
            row = cur.execute("SELECT encrypted_file FROM documents WHERE id=?", (did,)).fetchone()
            if row:
                encrypt_file(self.fernet, source_image_path,
                             os.path.join(self.files_dir, row["encrypted_file"]))
        cur.execute("UPDATE documents SET title=?,doc_type=?,note=? WHERE id=?",
                    (title, doc_type, encrypt_text(self.fernet, note), did))
        self.conn.commit()

    def delete_document(self, did):
        cur = self.conn.cursor()
        row = cur.execute("SELECT encrypted_file FROM documents WHERE id=?", (did,)).fetchone()
        if row:
            p = os.path.join(self.files_dir, row["encrypted_file"])
            if os.path.exists(p):
                os.remove(p)
        cur.execute("DELETE FROM documents WHERE id=?", (did,))
        self.conn.commit()

    def get_documents(self):
        rows = self.conn.execute("SELECT * FROM documents ORDER BY title").fetchall()
        return [{"id": r["id"], "title": r["title"], "doc_type": r["doc_type"],
                 "note": decrypt_text(self.fernet, r["note"]),
                 "encrypted_file": r["encrypted_file"]} for r in rows]

    def decrypt_document_to_temp(self, encrypted_file, temp_path):
        decrypt_file(self.fernet,
                     os.path.join(self.files_dir, encrypted_file), temp_path)
        return temp_path

    # ---- Instructions ----
    def add_instruction(self, title, body):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO instructions (title,body) VALUES (?,?)",
                    (title, encrypt_text(self.fernet, body)))
        self.conn.commit()
        return cur.lastrowid

    def update_instruction(self, iid, title, body):
        self.conn.execute("UPDATE instructions SET title=?,body=? WHERE id=?",
                          (title, encrypt_text(self.fernet, body), iid))
        self.conn.commit()

    def delete_instruction(self, iid):
        self.conn.execute("DELETE FROM instructions WHERE id=?", (iid,))
        self.conn.commit()

    def get_instructions(self):
        rows = self.conn.execute("SELECT * FROM instructions ORDER BY title").fetchall()
        return [{"id": r["id"], "title": r["title"],
                 "body": decrypt_text(self.fernet, r["body"])} for r in rows]

    # ---- Change master password ----
    def reencrypt_all(self, new_fernet):
        old = self.fernet
        cur = self.conn.cursor()
        for r in cur.execute("SELECT id,note FROM contacts").fetchall():
            cur.execute("UPDATE contacts SET note=? WHERE id=?",
                        (encrypt_text(new_fernet, decrypt_text(old, r["note"])), r["id"]))
        for r in cur.execute("SELECT id,login,password,note FROM passwords").fetchall():
            cur.execute("UPDATE passwords SET login=?,password=?,note=? WHERE id=?",
                        (encrypt_text(new_fernet, decrypt_text(old, r["login"])),
                         encrypt_text(new_fernet, decrypt_text(old, r["password"])),
                         encrypt_text(new_fernet, decrypt_text(old, r["note"])), r["id"]))
        for r in cur.execute("SELECT id,note FROM documents").fetchall():
            cur.execute("UPDATE documents SET note=? WHERE id=?",
                        (encrypt_text(new_fernet, decrypt_text(old, r["note"])), r["id"]))
        for r in cur.execute("SELECT id,body FROM instructions").fetchall():
            cur.execute("UPDATE instructions SET body=? WHERE id=?",
                        (encrypt_text(new_fernet, decrypt_text(old, r["body"])), r["id"]))
        for fname in os.listdir(self.files_dir):
            p = os.path.join(self.files_dir, fname)
            tmp = p + ".tmp"
            decrypt_file(old, p, tmp)
            encrypt_file(new_fernet, tmp, p)
            os.remove(tmp)
        self.conn.commit()
        self.fernet = new_fernet

    # ---- Backup ----
    def export_backup(self, dest_path):
        self.conn.commit()
        with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(self.db_path, "skyvault.db")
            for fname in os.listdir(self.files_dir):
                z.write(os.path.join(self.files_dir, fname), f"vault_files/{fname}")

    def import_backup(self, src_path):
        with zipfile.ZipFile(src_path, "r") as z:
            if "skyvault.db" not in z.namelist():
                return False
            self.conn.close()
            for fname in os.listdir(self.files_dir):
                try: os.remove(os.path.join(self.files_dir, fname))
                except OSError: pass
            z.extract("skyvault.db", os.path.dirname(self.db_path))
            for n in z.namelist():
                if n.startswith("vault_files/") and not n.endswith("/"):
                    with z.open(n) as src, \
                         open(os.path.join(self.files_dir, os.path.basename(n)), "wb") as dst:
                        dst.write(src.read())
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return True
