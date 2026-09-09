import psycopg2

try:
    connection = psycopg2.connect(
        dbname="trust_score_ai_db",
        user="postgres",
        password="Bambino.0",
        host="localhost",
        port="5433",
        sslmode="disable"
    )
    
    cursor = connection.cursor()
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public';
    """)
    
    tables = cursor.fetchall()
    
    print("\n--- Tables Found in 'trust_score_ai_db' ---")
    print("-" * 42)
    if tables:
        for table in tables:
            print(f" > {table[0]}")
    else:
        print(" (No tables found in public schema)")
    print("-" * 42)
    
    cursor.close()
    connection.close()
    
except Exception as error:
    print(f"ERROR: Connection failed: {error}")