"""Simple file logging for LocalWriter."""
import os


def log_to_file(message):
    try:
        import datetime
        home = os.path.expanduser("~")
        log_path = os.path.join(home, "log.txt")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("%s - %s\n" % (now, message))
    except Exception:
        pass
