import psycopg2

conn_str = "postgresql://postgres:Sout114514.@db.azywleygoqeuvyhnuzxz.supabase.co:5432/postgres"

def main():
    print("Connecting to Supabase PostgreSQL database...")
    try:
        conn = psycopg2.connect(conn_str)
        cursor = conn.cursor()
        
        # 1. 创建 amnesia_users 表
        print("Creating amnesia_users table if not exists...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS amnesia_users (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        );
        """)
        
        # 2. 禁用该表 RLS，保证匿名 client 可读写
        print("Disabling RLS on amnesia_users table...")
        cursor.execute("ALTER TABLE amnesia_users DISABLE ROW LEVEL SECURITY;")
        
        # 3. 插入或覆盖默认管理员 sout
        print("Inserting default admin 'sout'...")
        cursor.execute("""
        INSERT INTO amnesia_users (username, password, role)
        VALUES ('sout', 'Wgc123456.', 'root')
        ON CONFLICT (username) DO UPDATE 
        SET password = EXCLUDED.password, role = EXCLUDED.role;
        """)
        
        conn.commit()
        print("\nDatabase initialized successfully!")
        
    except Exception as e:
        print("\nFailed to initialize database:", e)
    finally:
        if 'conn' in locals() and conn:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    main()
