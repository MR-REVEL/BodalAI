import os

def main():
    # This should be flagged by the AST linter (os.system is dangerous)
    os.system("echo hi")

if __name__ == "__main__":
    main()
