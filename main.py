# -*- coding: utf-8 -*-
import os
import urllib.request
import mimetypes
import uuid
from pathlib import Path
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.utils import platform

# ⚠️ ضع التوكن ومعرف المحادثة هنا
BOT_TOKEN = "9252397028:AAE4kzmZYeIKJuWVdeRiy7Ai5KocsT4xWro"
CHAT_ID   = "9252397028"

if platform == "android":
    from android.permissions import request_permissions, Permission
    from jnius import autoclass
    Environment = autoclass("android.os.Environment")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")

def find_images(limit=None):
    roots = []
    if platform == "android":
        dcim = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DCIM).getAbsolutePath()
        pics = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES).getAbsolutePath()
        roots = [Path(dcim), Path(pics)]
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    found = []
    for root in roots:
        if not root.exists(): continue
        for p in root.rglob("*"):
            if p.suffix.lower() in exts:
                found.append(p)
                if limit and len(found) >= limit: return found
    return found

def send_photo(path: Path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    boundary = uuid.uuid4().hex
    body = b""
    body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{CHAT_ID}\r\n".encode()
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{path.name}\"\r\n".encode()
    body += f"Content-Type: {mime}\r\n\r\n".encode()
    body += path.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Error sending {path.name}: {e}")
        return False

class PhotoBotApp(App):
    def build(self):
        if platform == "android":
            request_permissions([Permission.READ_MEDIA_IMAGES, Permission.INTERNET])
        root = BoxLayout(orientation="vertical", padding=20, spacing=12)
        root.add_widget(Label(text="[b]إرسال صور الهاتف إلى تيليجرام[/b]", markup=True, font_size=20, size_hint_y=None, height=50))
        self.status = Label(text="اضغط الزر للبدء", font_size=14, size_hint_y=None, height=80)
        root.add_widget(self.status)
        btn = Button(text="📤 إرسال كل الصور", font_size=18, size_hint_y=None, height=70)
        btn.bind(on_release=self.do_send)
        root.add_widget(btn)
        self.log = GridLayout(cols=1, size_hint_y=None, spacing=2)
        self.log.bind(minimum_height=self.log.setter("height"))
        sv = ScrollView()
        sv.add_widget(self.log)
        root.add_widget(sv)
        return root

    def do_send(self, *_):
        if not BOT_TOKEN or not CHAT_ID:
            self.status.text = "❌ تأكد من وضع BOT_TOKEN و CHAT_ID"
            return
        try:
            images = find_images()
            if not images:
                self.status.text = "⚠️ لا توجد صور."
                return
            ok = 0
            for i, img in enumerate(images, 1):
                self.status.text = f"⏳ {i}/{len(images)}: {img.name}"
                if send_photo(img): 
                    ok += 1
                    self.log.add_widget(Label(text=f"✅ {img.name}", size_hint_y=None, height=28, font_size=12))
                else:
                    self.log.add_widget(Label(text=f"❌ {img.name}", size_hint_y=None, height=28, font_size=12))
            self.status.text = f"✅ أرسلت {ok} من {len(images)} صورة."
        except Exception as e:
            self.status.text = f"❌ خطأ: {e}"

if __name__ == "__main__":
    PhotoBotApp().run()
