"""
SkyVault — офлайн-хранилище важной личной информации.
Точка входа.
"""
import os
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivymd.app import MDApp

from database import Database
from screens.login import LoginScreen, CreatePasswordScreen
from screens.home import HomeScreen
from screens.contacts import ContactsScreen
from screens.passwords import PasswordsScreen
from screens.documents import DocumentsScreen
from screens.instructions import InstructionsScreen
from screens.settings import SettingsScreen

class SkyVaultApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Indigo"
        self.theme_cls.theme_style = "Dark"
        self.title = "SkyVault"

        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = self.user_data_dir
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "skyvault.db")
        files_dir = os.path.join(data_dir, "vault_files")

        self.db = Database(db_path, files_dir)
        self.db.connect()

        Builder.load_file(os.path.join(base_dir, "skyvault.kv"))

        sm = ScreenManager(transition=FadeTransition())
        sm.add_widget(CreatePasswordScreen(name="create_password"))
        sm.add_widget(LoginScreen(name="login"))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(ContactsScreen(name="contacts"))
        sm.add_widget(PasswordsScreen(name="passwords"))
        sm.add_widget(DocumentsScreen(name="documents"))
        sm.add_widget(InstructionsScreen(name="instructions"))
        sm.add_widget(SettingsScreen(name="settings"))

        try:
            self.db.load_master_credentials()
            sm.current = "login"
        except RuntimeError:
            sm.current = "create_password"

        self.sm = sm
        return sm

    def on_stop(self):
        try:
            self.db.close()
        except Exception:
            pass

if __name__ == "__main__":
    SkyVaultApp().run()
