"""Экран паролей."""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard

class PasswordsScreen(Screen):
    editing_id = None
    dialog = None

    def on_enter(self):
        self.refresh()

    def refresh(self):
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        container = self.ids.list_container
        container.clear_widgets()
        for item in app.db.get_passwords():
            card = MDCard(orientation="vertical", padding=dp(8), spacing=dp(4),
                          size_hint_y=None, height=dp(150), elevation=2)
            card.add_widget(MDLabel(text=item["service"], bold=True,
                                    size_hint_y=None, height=dp(26)))
            row_l = BoxLayout(size_hint_y=None, height=dp(30))
            row_l.add_widget(MDLabel(text=f"Логин: {item['login']}"))
            row_l.add_widget(MDIconButton(icon="content-copy",
                on_release=lambda *_, v=item["login"]: self._copy(v, "Логин скопирован")))
            card.add_widget(row_l)
            row_p = BoxLayout(size_hint_y=None, height=dp(30))
            shown = {"v": False}
            pwd_lbl = MDLabel(text="Пароль: " + "*" * len(item["password"]))
            def toggle(_lbl=pwd_lbl, _item=item, _st=shown):
                _st["v"] = not _st["v"]
                _lbl.text = "Пароль: " + (_item["password"] if _st["v"]
                                          else "*" * len(_item["password"]))
            row_p.add_widget(pwd_lbl)
            row_p.add_widget(MDIconButton(icon="eye", on_release=toggle))
            row_p.add_widget(MDIconButton(icon="content-copy",
                on_release=lambda *_, v=item["password"]: self._copy(v, "Пароль скопирован")))
            card.add_widget(row_p)
            if item["note"]:
                card.add_widget(MDLabel(text=item["note"], font_style="Caption",
                                        size_hint_y=None, height=dp(22)))
            actions = BoxLayout(size_hint_y=None, height=dp(36))
            actions.add_widget(MDIconButton(icon="pencil",
                on_release=lambda *_, i=item: self.edit(i)))
            actions.add_widget(MDIconButton(icon="delete",
                on_release=lambda *_, i=item: self.delete(i)))
            card.add_widget(actions)
            container.add_widget(card)

    def _copy(self, value, msg):
        Clipboard.copy(value)
        d = MDDialog(title="Готово", text=msg, buttons=[MDFlatButton(
            text="OK", on_release=lambda *_: d.dismiss())])
        d.open()

    def _build_dialog(self, item=None):
        box = BoxLayout(orientation="vertical", spacing=dp(8),
                        size_hint_y=None, height=dp(300))
        self._f_service = MDTextField(hint_text="Сервис")
        self._f_login = MDTextField(hint_text="Логин")
        self._f_password = MDTextField(hint_text="Пароль", password=True)
        self._f_note = MDTextField(hint_text="Заметка")
        if item:
            self._f_service.text = item["service"]
            self._f_login.text = item["login"]
            self._f_password.text = item["password"]
            self._f_note.text = item["note"]
        for w in (self._f_service, self._f_login, self._f_password, self._f_note):
            box.add_widget(w)

        self.dialog = MDDialog(
            title="Пароль" if not item else "Редактировать пароль",
            type="custom", content_cls=box,
            buttons=[
                MDFlatButton(text="Отмена",
                             on_release=lambda *_: self.dialog.dismiss()),
                MDRaisedButton(text="Сохранить",
                               on_release=lambda *_: self._save()),
            ])
        self.dialog.open()

    def open_add(self):
        self.editing_id = None
        self._build_dialog()

    def edit(self, item):
        self.editing_id = item["id"]
        self._build_dialog(item)

    def _save(self):
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        s = self._f_service.text.strip()
        l = self._f_login.text.strip()
        p = self._f_password.text
        n = self._f_note.text.strip()
        if not s or not l or not p:
            return
        if self.editing_id is None:
            app.db.add_password(s, l, p, n)
        else:
            app.db.update_password(self.editing_id, s, l, p, n)
        self.dialog.dismiss()
        self.refresh()

    def delete(self, item):
        from kivymd.app import MDApp
        MDApp.get_running_app().db.delete_password(item["id"])
        self.refresh()

    def go_back(self):
        self.manager.current = "home"
