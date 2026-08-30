import argparse
from .agent import RepoAgent
from .config import settings

def main():
    parser = argparse.ArgumentParser(description="Analyze a code repository with RepoPilot")
    parser.add_argument("repository")
    parser.add_argument("question", nargs="+")
    args = parser.parse_args()
    if not settings.api_key:
        parser.error("未配置 REPILOT_API_KEY，请先配置 DeepSeek API Key")
    print(RepoAgent(args.repository).run(" ".join(args.question)).answer)

if __name__ == "__main__": main()
