"""Главный экран SkyVault."""
from kivy.uix.screenmanager import Screen

class HomeScreen(Screen):
    def go(self, screen_name):
        self.manager.current = screen_name

    def open_settings(self):
        self.manager.current = "settings"
