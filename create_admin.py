from werkzeug.security import generate_password_hash
from database import execute

username = "admin"
new_password = "admin123"

password_hash = generate_password_hash(new_password)

execute(
    "UPDATE admins SET password_hash=%s WHERE username=%s",
    (password_hash, username)
)

print("✅ Admin password reset successfully!")
print("Username:", username)
print("Password:", new_password)