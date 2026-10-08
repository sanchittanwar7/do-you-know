"""CLI triggers for the approval workflow.

Usage:
    python cli.py daily
    python cli.py ask "Do you know ...?"

The long-running process (python run.py) handles the Telegram approve/reject
callbacks and actually publishes once approved.
"""
import sys

from backend import jobs


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage:")
        print("  python cli.py daily")
        print('  python cli.py ask "Do you know ...?"')
        return 1

    cmd = args[0]
    try:
        if cmd == "daily":
            approval = jobs.create_approval(question=None, source="scheduled")
            print(f"Created draft {approval['id']}: {approval['question']}")
        elif cmd == "ask":
            question = " ".join(args[1:]).strip()
            if not question:
                print("Provide a question after 'ask'.")
                return 1
            approval = jobs.create_approval(question=question, source="manual")
            print(f"Created draft {approval['id']}: {approval['question']}")
        else:
            print(f"Unknown command: {cmd}")
            return 1
    except Exception as exc:
        print(f"Failed: {exc}")
        return 1

    print("Sent to Telegram for approval.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
