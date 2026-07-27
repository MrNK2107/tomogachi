import sys
import traceback

try:
    print("Importing main...")
    import main
    print("Running main.main()...")
    main.main()
except Exception as e:
    print(f"Exception caught: {e}")
    with open("crash_log.txt", "w") as f:
        traceback.print_exc(file=f)
except BaseException as e:
    print(f"BaseException caught: {e}")
    with open("crash_log.txt", "w") as f:
        traceback.print_exc(file=f)
