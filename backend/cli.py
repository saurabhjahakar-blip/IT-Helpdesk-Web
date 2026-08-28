import argparse
import getpass
import sys

from backend.db.models import Role, User
from backend.db.session import SessionLocal
from backend.security import hash_password


def _read_password(prompt: str) -> str:
    # getpass reads from the console directly and ignores piped/redirected
    # stdin on some platforms (notably Windows), which hangs non-interactive
    # callers (scripts, CI) instead of failing fast. Fall back to a plain
    # stdin read when stdin isn't a real terminal.
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    return sys.stdin.readline().rstrip("\n")


def create_user(args: argparse.Namespace) -> None:
    password = _read_password("Password: ")
    confirm = _read_password("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        raise SystemExit(1)
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        raise SystemExit(1)

    db = SessionLocal()
    try:
        email = args.email.strip().lower()
        if db.query(User).filter(User.email == email).first() is not None:
            print(f"A user with email {email} already exists.", file=sys.stderr)
            raise SystemExit(1)
        user = User(
            email=email,
            display_name=args.display_name,
            password_hash=hash_password(password),
            role=Role(args.role),
        )
        db.add(user)
        db.commit()
        print(f"Created {args.role} user {email}.")
    finally:
        db.close()


def list_users(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.email).all()
        if not users:
            print("No users found.")
            return
        for user in users:
            status = "active" if user.is_active else "deactivated"
            print(f"{user.email}\t{user.display_name}\t{user.role.value}\t{status}")
    finally:
        db.close()


def deactivate_user(args: argparse.Namespace) -> None:
    db = SessionLocal()
    try:
        email = args.email.strip().lower()
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            print(f"No user with email {email}.", file=sys.stderr)
            raise SystemExit(1)
        user.is_active = False
        db.commit()
        print(f"Deactivated {email}.")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="backend.cli", description="IT Helpdesk user management")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create-user", help="Create a new user")
    create_parser.add_argument("--email", required=True)
    create_parser.add_argument("--display-name", required=True)
    create_parser.add_argument("--role", choices=[r.value for r in Role], default=Role.EMPLOYEE.value)
    create_parser.set_defaults(func=create_user)

    list_parser = subparsers.add_parser("list-users", help="List all users")
    list_parser.set_defaults(func=list_users)

    deactivate_parser = subparsers.add_parser("deactivate-user", help="Deactivate a user")
    deactivate_parser.add_argument("--email", required=True)
    deactivate_parser.set_defaults(func=deactivate_user)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
