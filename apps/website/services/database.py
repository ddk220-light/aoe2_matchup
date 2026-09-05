"""Read-only serving connections; offline generators own database writes."""
from pathlib import Path
import sqlite3

def connect_readonly(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    return connection
