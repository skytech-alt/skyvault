"""Экран контактов."""
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.menu import MDDropdownMenu

CATEGORIES = ["Экстренные", "Банк", "ЖКХ", "Личное", "Другое"]

class ContactsScreen(Screen):
    editing_id = None
    dialog = None
    _chosen_category = "Личное"

    def on_enter(self):
        self.refresh()

    def refresh(self):
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        container = self.ids.list_container
        container.clear_widgets()
        for item in app.db.get_contacts():
            card = MDCard(orientation="vertical", padding=dp(8), spacing=dp(4),
                          size_hint_y=None, height=dp(120), elevation=2)
            row = BoxLayout(orientation="horizontal")
            info = BoxLayout(orientation="vertical")
            info.add_widget(MDLabel(text=f"{item['name']}  ·  {item['category']}",
                                    bold=True, size_hint_y=None, height=dp(28)))
            info.add_widget(MDLabel(text=item["phone"],
                                    size_hint_y=None, height=dp(24)))
            if item["note"]:
                info.add_widget(MDLabel(text=item["note"], font_style="Caption",
                                        size_hint_y=None, height=dp(24)))
            row.add_widget(info)
            row.add_widget(MDIconButton(icon="pencil",
                on_release=lambda *_, i=item: self.edit(i)))
            row.add_widget(MDIconButton(icon="delete",
                on_release=lambda *_, i=item: self.delete(i)))
            card.add_widget(row)
            container.add_widget(card)

    def _build_dialog(self, item=None):
        self._chosen_category = item["category"] if item else "Личное"
        box = BoxLayout(orientation="vertical", spacing=dp(8),
                        size_hint_y=None, height=dp(320))
        self._f_name = MDTextField(hint_text="Имя")
        self._f_phone = MDTextField(hint_text="Телефон", input_filter="phone")
        self._f_note = MDTextField(hint_text="Заметка")
        cat_btn = MDRaisedButton(text=f"Категория: {self._chosen_category}",
                                 size_hint_x=None, width=dp(220))
        self._cat_btn = cat_btn
        menu_items = [{"viewclass": "OneLineListItem", "text": c,
                       "on_release": lambda x=c: self._pick_cat(x)}
                      for c in CATEGORIES]
        cat_btn.bind(on_release=lambda *_: MDDropdownMenu(
            caller=cat_btn, items=menu_items, width_mult=4).open())
        if item:
            self._f_name.text = item["name"]
            self._f_phone.text = item["phone"]
            self._f_note.text = item["note"]
        box.add_widget(self._f_name)
        box.add_widget(self._f_phone)
        box.add_widget(cat_btn)
        box.add_widget(self._f_note)

        self.dialog = MDDialog(
            title="Контакт" if not item else "Редактировать контакт",
            type="custom", content_cls=box,
            buttons=[
                MDFlatButton(text="Отмена",
                             on_release=lambda *_: self.dialog.dismiss()),
                MDRaisedButton(text="Сохранить",
                               on_release=lambda *_: self._save()),
            ])
        self.dialog.open()

    def _pick_cat(self, cat):
        self._chosen_category = cat
        self._cat_btn.text = f"Категория: {cat}"

    def open_add(self):
        self.editing_id = None
        self._build_dialog()

    def edit(self, item):
        self.editing_id = item["id"]
        self._build_dialog(item)

    def _save(self):
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        name = self._f_name.text.strip()
        phone = self._f_phone.text.strip()
        note = self._f_note.text.strip()
        if not name or not phone:
            return
        if self.editing_id is None:
            app.db.add_contact(name, phone, self._chosen_category, note)
        else:
            app.db.update_contact(self.editing_id, name, phone,
                                  self._chosen_category, note)
        self.dialog.dismiss()
        self.refresh()

    def delete(self, item):
        from kivymd.app import MDApp
        MDApp.get_running_app().db.delete_contact(item["id"])
        self.refresh()

    def go_back(self):
        self.manager.current = "home"
