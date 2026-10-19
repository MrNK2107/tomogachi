import sys
import os
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

log_path = os.path.join(BASE_DIR, "data", "awaken.log")
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

class SafeLogger:
    def __init__(self, filepath):
        self.filepath = filepath
    def write(self, s):
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(s)
        except Exception:
            pass
    def flush(self):
        pass

if sys.stdout is None:
    sys.stdout = SafeLogger(log_path)
if sys.stderr is None:
    sys.stderr = SafeLogger(log_path)

try:
    print("Importing main...")
    import main
    print("Running main.main()...")
    main.main()
except Exception as e:
    print(f"Exception caught: {e}")
    try:
        with open(os.path.join(BASE_DIR, "crash_log.txt"), "w") as f:
            traceback.print_exc(file=f)
    except Exception:
        pass
except BaseException as e:
    print(f"BaseException caught: {e}")
    try:
        with open(os.path.join(BASE_DIR, "crash_log.txt"), "w") as f:
            traceback.print_exc(file=f)
    except Exception:
        pass
