"""Экран настроек: смена пароля, экспорт/импорт, о программе."""
import os
import time
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.textfield import MDTextField
from cryptography.fernet import Fernet

from encryption import (generate_salt, hash_password, derive_key, verify_password)

class SettingsScreen(Screen):
    dialog = None

    def change_password(self):
        box = BoxLayout(orientation="vertical", spacing=dp(8),
                        size_hint_y=None, height=dp(240))
        self._f_old = MDTextField(hint_text="Текущий пароль", password=True)
        self._f_new = MDTextField(hint_text="Новый пароль (мин. 6 символов)", password=True)
        self._f_new2 = MDTextField(hint_text="Повторите новый пароль", password=True)
        for w in (self._f_old, self._f_new, self._f_new2):
            box.add_widget(w)
        self.dialog = MDDialog(
            title="Смена мастер-пароля", type="custom", content_cls=box,
            buttons=[
                MDFlatButton(text="Отмена",
                             on_release=lambda *_: self.dialog.dismiss()),
                MDRaisedButton(text="Сменить",
                               on_release=lambda *_: self._do_change()),
            ])
        self.dialog.open()

    def _do_change(self):
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        salt_hex, h = app.db.load_master_credentials()
        salt = bytes.fromhex(salt_hex)
        if not verify_password(self._f_old.text, salt, h):
            self._toast("Неверный текущий пароль"); return
        newp = self._f_new.text
        if len(newp) < 6:
            self._toast("Новый пароль слишком короткий"); return
        if newp != self._f_new2.text:
            self._toast("Новые пароли не совпадают"); return
        new_salt = generate_salt()
        new_key = derive_key(newp, new_salt)
        app.db.reencrypt_all(Fernet(new_key))
        app.db.save_master_credentials(new_salt.hex(), hash_password(newp, new_salt))
        self.dialog.dismiss()
        self._toast("Мастер-пароль изменён")

    def export_backup(self):
        try:
            from plyer import filechooser
            default = "skyvault_" + time.strftime("%Y%m%d_%H%M%S") + ".skyvault"
            filechooser.save_file(
                on_selection=lambda paths: self._do_export(paths[0] if paths else None),
                title="Сохранить резервную копию",
                filters=[("SkyVault Backup", "*.skyvault")],
                filename=default)
        except Exception:
            self._toast("Экспорт недоступен на этом устройстве")

    def _do_export(self, path):
        if not path:
            return
        if not path.endswith(".skyvault"):
            path += ".skyvault"
        from kivymd.app import MDApp
        try:
            MDApp.get_running_app().db.export_backup(path)
            self._toast("Резервная копия сохранена")
        except Exception as e:
            self._toast(f"Ошибка экспорта: {e}")

    def import_backup(self):
        try:
            from plyer import filechooser
            filechooser.open_file(
                on_selection=lambda paths: self._do_import(paths[0] if paths else None),
                filters=[("SkyVault Backup", "*.skyvault")])
        except Exception:
            self._toast("Импорт недоступен на этом устройстве")

    def _do_import(self, path):
        if not path:
            return
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        try:
            if app.db.import_backup(path):
                self._toast("Импорт выполнен. Требуется повторный вход.")
                app.db.set_fernet(None)
                self.manager.current = "login"
            else:
                self._toast("Неверный формат файла")
        except Exception as e:
            self._toast(f"Ошибка импорта: {e}")

    def show_about(self):
        d = MDDialog(
            title="SkyVault",
            text=("Версия 1.0\n\n"
                  "Офлайн-хранилище личной информации.\n"
                  "Все данные зашифрованы Fernet (AES) и хранятся только "
                  "на этом устройстве.\n\n"
                  "Мастер-пароль не хранится — только его хеш для проверки."),
            buttons=[MDFlatButton(text="OK",
                     on_release=lambda *_: d.dismiss())])
        d.open()

    def go_back(self):
        self.manager.current = "home"

    def _toast(self, msg):
        d = MDDialog(title="Инфо", text=msg,
                     buttons=[MDFlatButton(text="OK",
                             on_release=lambda *_: d.dismiss())])
        d.open()
