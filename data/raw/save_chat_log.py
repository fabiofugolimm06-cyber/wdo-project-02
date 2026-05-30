import pyperclip
import time
from datetime import datetime

LOG_FILE = "chat_log.txt"

last_content = ""
print("Monitorando clipboard... Pressione Ctrl+C para parar.")
try:
    while True:
        current = pyperclip.paste()
        if current != last_content and len(current) > 20:  # evita ruído
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n[{timestamp}]\n{current}\n{'-'*80}\n")
            last_content = current
            print(f"Salvo em {LOG_FILE}")
        time.sleep(1)
except KeyboardInterrupt:
    print("Encerrado.")