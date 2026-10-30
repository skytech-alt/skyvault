"""
Экраны: создание мастер-пароля и вход.
"""
from kivy.uix.screenmanager import Screen
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from cryptography.fernet import Fernet

from encryption import generate_salt, hash_password, derive_key, verify_password

def _err(msg):
    d = MDDialog(title="Ошибка", text=msg,
                 buttons=[MDFlatButton(text="OK",
                         on_release=lambda *_: d.dismiss())])
    d.open()

class CreatePasswordScreen(Screen):
    def create_password(self):
        pwd = self.ids.pwd.text
        confirm = self.ids.pwd_confirm.text
        if len(pwd) < 6:
            return _err("Пароль должен содержать минимум 6 символов")
        if pwd != confirm:
            return _err("Пароли не совпадают")
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        salt = generate_salt()
        app.db.save_master_credentials(salt.hex(), hash_password(pwd, salt))
        app.db.set_fernet(Fernet(derive_key(pwd, salt)))
        self.ids.pwd.text = ""
        self.ids.pwd_confirm.text = ""
        self.manager.current = "home"

class LoginScreen(Screen):
    def login(self):
        pwd = self.ids.pwd.text
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        try:
            salt_hex, h = app.db.load_master_credentials()
        except RuntimeError:
            self.manager.current = "create_password"
            return
        salt = bytes.fromhex(salt_hex)
        if not verify_password(pwd, salt, h):
            return _err("Неверный мастер-пароль")
        app.db.set_fernet(Fernet(derive_key(pwd, salt)))
        self.ids.pwd.text = ""
        self.manager.current = "home"
