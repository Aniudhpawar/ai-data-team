import sys
from src.agents.team import team

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or input("Question: ")
    answer = team(question)
    print("WRITER ->")
    print(answer)
