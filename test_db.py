import psycopg2

try:
    connection = psycopg2.connect(
        dbname="PostgreSQL 18",
        user="postgres",
        password="Bambino.0",
        host="localhost",
        port="5432",
        sslmode="disable"
    )
    
    cursor = connection.cursor()
    cursor.execute("SELECT version();")
    db_version = cursor.fetchone()
    
    print("SUCCESS: Database is connected!")
    print(f"PostgreSQL Version: {db_version[0]}")
    
    cursor.close()
    connection.close()
    
except Exception as error:
    print(f"ERROR: Connection failed: {error}")

