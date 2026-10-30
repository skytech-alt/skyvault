"""Экран инструкций (текстовые заметки)."""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard

class InstructionsScreen(Screen):
    editing_id = None
    dialog = None

    def on_enter(self):
        self.refresh()

    def refresh(self):
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        container = self.ids.list_container
        container.clear_widgets()
        for item in app.db.get_instructions():
            card = MDCard(orientation="vertical", padding=dp(8), spacing=dp(4),
                          size_hint_y=None, height=dp(140), elevation=2)
            card.add_widget(MDLabel(text=item["title"], bold=True,
                                    size_hint_y=None, height=dp(28)))
            body_preview = item["body"][:120] + ("…" if len(item["body"]) > 120 else "")
            card.add_widget(MDLabel(text=body_preview, font_style="Caption"))
            row = BoxLayout(size_hint_y=None, height=dp(36))
            row.add_widget(MDIconButton(icon="eye",
                on_release=lambda *_, i=item: self.view(i)))
            row.add_widget(MDIconButton(icon="pencil",
                on_release=lambda *_, i=item: self.edit(i)))
            row.add_widget(MDIconButton(icon="delete",
                on_release=lambda *_, i=item: self.delete(i)))
            card.add_widget(row)
            container.add_widget(card)

    def _build_dialog(self, item=None):
        box = BoxLayout(orientation="vertical", spacing=dp(8),
                        size_hint_y=None, height=dp(420))
        self._f_title = MDTextField(hint_text="Заголовок")
        self._f_body = MDTextField(hint_text="Текст инструкции",
                                   multiline=True, mode="rectangle",
                                   size_hint_y=None, height=dp(320))
        if item:
            self._f_title.text = item["title"]
            self._f_body.text = item["body"]
        box.add_widget(self._f_title)
        box.add_widget(self._f_body)
        self.dialog = MDDialog(
            title="Инструкция" if not item else "Редактировать",
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
        t = self._f_title.text.strip()
        b = self._f_body.text.strip()
        if not t or not b:
            return
        if self.editing_id is None:
            app.db.add_instruction(t, b)
        else:
            app.db.update_instruction(self.editing_id, t, b)
        self.dialog.dismiss()
        self.refresh()

    def view(self, item):
        content = BoxLayout(orientation="vertical", spacing=dp(8),
                            size_hint_y=None, height=dp(400))
        from kivy.uix.scrollview import ScrollView
        scroll = ScrollView()
        lbl = MDLabel(text=item["body"], size_hint_y=None)
        lbl.bind(texture_size=lambda w, v: setattr(w, "height", v[1]))
        scroll.add_widget(lbl)
        content.add_widget(scroll)
        d = MDDialog(title=item["title"], type="custom", content_cls=content,
                     buttons=[MDFlatButton(text="Закрыть",
                             on_release=lambda *_: d.dismiss())])
        d.open()

    def delete(self, item):
        from kivymd.app import MDApp
        MDApp.get_running_app().db.delete_instruction(item["id"])
        self.refresh()

    def go_back(self):
        self.manager.current = "home"
