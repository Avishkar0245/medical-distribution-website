import getpass
import sys
from werkzeug.security import generate_password_hash
from app import app
from models import db, User

username = input("Username: ").strip().lower()
role = input("Role (admin/staff) [staff]: ").strip().lower() or "staff"
pw = getpass.getpass("Password (min 8 chars): ")
pw2 = getpass.getpass("Repeat password: ")

if pw != pw2 or len(pw) < 8:
    print("Passwords do not match or are too short.")
    sys.exit(1)

with app.app_context():
    if User.query.filter_by(username=username).first():
        print("This username already exists.")
        sys.exit(1)
    db.session.add(User(username=username,
                        password_hash=generate_password_hash(pw),
                        role=role))
    db.session.commit()
    print(f"User '{username}' created.")