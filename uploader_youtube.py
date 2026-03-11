from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import traceback
import time


def subir_youtube(video_path, titulo):

    try:

        print("Subiendo a YouTube REAL")

        options = Options()

        options.add_argument("--user-data-dir=/home/ubuntu/chrome-profile")

        options.add_argument("--no-sandbox")

        options.add_argument("--disable-dev-shm-usage")

        options.binary_location = "/usr/bin/chromium-browser"


        driver = webdriver.Chrome(
            executable_path="/usr/bin/chromedriver",
            options=options
        )


        driver.get("https://studio.youtube.com")

        print("Abriendo YouTube Studio")

        time.sleep(20)


        driver.get("https://studio.youtube.com/channel/upload")

        print("Pantalla upload abierta")

        time.sleep(20)


        print("UPLOAD MANUAL REQUERIDO")

        input("Presiona ENTER cuando termines upload manual")


        driver.quit()


        return True


    except Exception as e:

        print("ERROR REAL YOUTUBE:")
        traceback.print_exc()

        return False