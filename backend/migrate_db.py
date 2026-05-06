import sqlite3

conn = sqlite3.connect('fticrms.db')
cursor = conn.cursor()

# Check if task_type column exists
cursor.execute('PRAGMA table_info(tasks)')
columns = [col[1] for col in cursor.fetchall()]
print('Current columns:', columns)

if 'task_type' not in columns:
    cursor.execute("ALTER TABLE tasks ADD COLUMN task_type TEXT DEFAULT 'analysis'")
    conn.commit()
    print('Added task_type column')
else:
    print('task_type column already exists')

# Verify
cursor.execute('PRAGMA table_info(tasks)')
columns = [col[1] for col in cursor.fetchall()]
print('Updated columns:', columns)

conn.close()
