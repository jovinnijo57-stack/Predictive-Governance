import sqlite3
import os

DATABASE_NAME = 'governance.db'

def setup_database():
    print(f"Initializing {DATABASE_NAME}...")
    
    # Connect to SQLite database (creates it if it doesn't exist)
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Create Users Table
    print("Creating 'users' table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')

    # Data to seed
    default_users = [
        ('admin', 'admin123', 'admin'),
        ('user', 'user123', 'user'),
        ('officer_health', 'health123', 'admin'), # Adding department specific admins as an example
        ('officer_road', 'road123', 'admin')
    ]

    # Insert Users
    print("Seeding default users...")
    for username, password, role in default_users:
        try:
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
            print(f" [+] Added user: {username} (Role: {role})")
        except sqlite3.IntegrityError:
            print(f" [!] User '{username}' already exists. Skipping.")

    # Commit changes and close
    conn.commit()
    conn.close()
    print("\nDatabase setup completed successfully!")
    print(f"Database file located at: {os.path.abspath(DATABASE_NAME)}")

if __name__ == "__main__":
    setup_database()
