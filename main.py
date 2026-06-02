import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.dependency_checker import check_and_install

if __name__ == "__main__":
    if not check_and_install():
        print("❌ تعذر تثبيت المكتبات المطلوبة. تأكد من اتصال الإنترنت وحاول مجدداً.")
        input("اضغط Enter للخروج...")
        sys.exit(1)

    from app.gui import App
    app = App()
    app.run()
