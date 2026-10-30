"""Экран документов (изображения)."""
import os
import tempfile
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp
from kivy.uix.image import Image
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton, MDIconButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.menu import MDDropdownMenu

DOC_TYPES = ["Паспорт", "ИНН", "СНИЛС", "Медполис", "Другое"]

def _choose_file(callback):
    try:
        from plyer import filechooser
        filechooser.open_file(on_selection=lambda s: callback(s[0] if s else None))
    except Exception:
        callback(None)

def _take_photo(callback):
    try:
        from plyer import camera
        path = os.path.join(tempfile.gettempdir(), "sv_photo.jpg")
        camera.take_picture(filename=path, on_complete=lambda p: callback(p))
    except Exception:
        callback(None)

class DocumentsScreen(Screen):
    editing_id = None
    dialog = None
    _chosen_type = "Паспорт"
    _pending_image = None

    def on_enter(self):
        self.refresh()

    def refresh(self):
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        container = self.ids.list_container
        container.clear_widgets()
        for item in app.db.get_documents():
            card = MDCard(orientation="horizontal", padding=dp(8), spacing=dp(8),
                          size_hint_y=None, height=dp(100), elevation=2)
            info = BoxLayout(orientation="vertical")
            info.add_widget(MDLabel(text=item["title"], bold=True,
                                    size_hint_y=None, height=dp(28)))
            info.add_widget(MDLabel(text=item["doc_type"],
                                    size_hint_y=None, height=dp(24)))
            if item["note"]:
                info.add_widget(MDLabel(text=item["note"], font_style="Caption",
                                        size_hint_y=None, height=dp(24)))
            card.add_widget(info)
            card.add_widget(MDIconButton(icon="eye",
                on_release=lambda *_, i=item: self.view(i)))
            card.add_widget(MDIconButton(icon="pencil",
                on_release=lambda *_, i=item: self.edit(i)))
            card.add_widget(MDIconButton(icon="delete",
                on_release=lambda *_, i=item: self.delete(i)))
            container.add_widget(card)

    def _build_dialog(self, item=None):
        self._chosen_type = item["doc_type"] if item else "Паспорт"
        self._pending_image = None
        box = BoxLayout(orientation="vertical", spacing=dp(8),
                        size_hint_y=None, height=dp(300))
        self._f_title = MDTextField(hint_text="Название")
        self._f_note = MDTextField(hint_text="Заметка")
        type_btn = MDRaisedButton(text=f"Тип: {self._chosen_type}",
                                  size_hint_x=None, width=dp(220))
        self._type_btn = type_btn
        menu_items = [{"viewclass": "OneLineListItem", "text": t,
                       "on_release": lambda x=t: self._pick_type(x)}
                      for t in DOC_TYPES]
        type_btn.bind(on_release=lambda *_: MDDropdownMenu(
            caller=type_btn, items=menu_items, width_mult=4).open())

        pick_box = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        pick_box.add_widget(MDRaisedButton(text="Галерея",
                            on_release=lambda *_: _choose_file(self._set_image)))
        pick_box.add_widget(MDRaisedButton(text="Камера",
                            on_release=lambda *_: _take_photo(self._set_image)))
        self._img_label = MDLabel(text="Изображение не выбрано",
                                  size_hint_y=None, height=dp(24))

        if item:
            self._f_title.text = item["title"]
            self._f_note.text = item["note"]
            self._img_label.text = "(текущее изображение сохранено)"

        box.add_widget(self._f_title)
        box.add_widget(type_btn)
        box.add_widget(pick_box)
        box.add_widget(self._img_label)
        box.add_widget(self._f_note)

        self.dialog = MDDialog(
            title="Документ" if not item else "Редактировать документ",
            type="custom", content_cls=box,
            buttons=[
                MDFlatButton(text="Отмена",
                             on_release=lambda *_: self.dialog.dismiss()),
                MDRaisedButton(text="Сохранить",
                               on_release=lambda *_: self._save()),
            ])
        self.dialog.open()

    def _pick_type(self, t):
        self._chosen_type = t
        self._type_btn.text = f"Тип: {t}"

    def _set_image(self, path):
        if path:
            self._pending_image = path
            self._img_label.text = "Выбрано: " + os.path.basename(path)

    def open_add(self):
        self.editing_id = None
        self._build_dialog()

    def edit(self, item):
        self.editing_id = item["id"]
        self._build_dialog(item)

    def _save(self):
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        title = self._f_title.text.strip()
        note = self._f_note.text.strip()
        if not title:
            return
        if self.editing_id is None:
            if not self._pending_image:
                return
            app.db.add_document(title, self._chosen_type, note, self._pending_image)
        else:
            app.db.update_document(self.editing_id, title, self._chosen_type,
                                   note, self._pending_image)
        self.dialog.dismiss()
        self.refresh()

    def view(self, item):
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        tmp = os.path.join(tempfile.gettempdir(), "sv_preview_" + item["encrypted_file"] + ".jpg")
        try:
            app.db.decrypt_document_to_temp(item["encrypted_file"], tmp)
        except Exception:
            return
        img = Image(source=tmp)
        content = BoxLayout(size_hint_y=None, height=dp(400))
        content.add_widget(img)
        d = MDDialog(title=item["title"], type="custom", content_cls=content,
                     buttons=[MDFlatButton(text="Закрыть",
                             on_release=lambda *_: d.dismiss())])
        d.open()

    def delete(self, item):
        from kivymd.app import MDApp
        MDApp.get_running_app().db.delete_document(item["id"])
        self.refresh()

    def go_back(self):
        self.manager.current = "home"
