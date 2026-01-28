# config.py
import pyodbc

# Настройте под своё окружение
DB_CONFIG = {
    'server': 'DESKTOP-7KN37DO\SQLEXPRESS',
    'database': 'QueueSystem',
}

# Строка подключения
def get_db_connection():
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)