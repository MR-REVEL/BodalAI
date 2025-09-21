def main():
    # Dangerous built-in call; should be flagged by AST linter
    eval("1 + 1")

if __name__ == "__main__":
    main()
