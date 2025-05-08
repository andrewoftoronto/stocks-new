import subprocess
import shlex
import sys


def main():
    print("Enter shell commands (type 'exit' to quit):")

    while True:
        try:
            command = input("$ ")
            if command.lower() in ["exit", "quit"]:
                break

            process = subprocess.run([
                "bash", "-c",
                f"source /home/runner/workspace/.config/bashrc && {command}"
            ],
                                     capture_output=True,
                                     text=True)

            if process.stdout:
                print(process.stdout)
            if process.stderr:
                print(process.stderr, file=sys.stderr)

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
