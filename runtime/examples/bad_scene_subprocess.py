import subprocess

def main():
    # This should be flagged by the AST linter (process spawning disallowed)
    subprocess.run(["echo", "bad"], check=False)

if __name__ == "__main__":
    main()
