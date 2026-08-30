import argparse
from .agent import RepoAgent

def main():
    parser = argparse.ArgumentParser(description="Analyze a code repository with RepoPilot")
    parser.add_argument("repository")
    parser.add_argument("question", nargs="+")
    args = parser.parse_args()
    print(RepoAgent(args.repository).run(" ".join(args.question)).answer)

if __name__ == "__main__": main()
