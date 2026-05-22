import psycopg2
from psycopg2.extras import Json

conn_str = "postgresql://postgres:Sout114514.@db.azywleygoqeuvyhnuzxz.supabase.co:5432/postgres"


DEFAULT_DOC_SETTINGS = {
    "theme": "cupcake",
    "pagePaddingX": 48,
    "docFontSize": 16,
    "docFontFamily": "Outfit",
    "lockPage": False,
}


def ensure_schema(cursor):
    print("Creating amnesia_docs table if not exists...")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS amnesia_docs (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            emoji TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            author TEXT DEFAULT 'sout',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            settings JSONB NOT NULL DEFAULT '{}'::jsonb
        );
        """
    )

    print("Adding missing columns for production schema...")
    cursor.execute("ALTER TABLE amnesia_docs ADD COLUMN IF NOT EXISTS author TEXT DEFAULT 'sout';")
    cursor.execute(
        "ALTER TABLE amnesia_docs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();"
    )
    cursor.execute(
        "ALTER TABLE amnesia_docs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();"
    )
    cursor.execute(
        "ALTER TABLE amnesia_docs ADD COLUMN IF NOT EXISTS settings JSONB NOT NULL DEFAULT '{}'::jsonb;"
    )

    print("Backfilling missing settings and timestamps...")
    cursor.execute(
        """
        UPDATE amnesia_docs
        SET
            author = COALESCE(NULLIF(author, ''), 'sout'),
            created_at = COALESCE(created_at, NOW()),
            updated_at = COALESCE(updated_at, NOW()),
            settings = CASE
                WHEN settings IS NULL OR settings = '{}'::jsonb
                THEN %s::jsonb
                ELSE settings
            END;
        """,
        (Json(DEFAULT_DOC_SETTINGS),),
    )

    print("Creating auto-update trigger for updated_at...")
    cursor.execute(
        """
        CREATE OR REPLACE FUNCTION amnesia_set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    cursor.execute(
        """
        DROP TRIGGER IF EXISTS amnesia_docs_set_updated_at ON amnesia_docs;
        CREATE TRIGGER amnesia_docs_set_updated_at
        BEFORE UPDATE ON amnesia_docs
        FOR EACH ROW
        EXECUTE FUNCTION amnesia_set_updated_at();
        """
    )

    print("Disabling RLS on amnesia_docs table...")
    cursor.execute("ALTER TABLE amnesia_docs DISABLE ROW LEVEL SECURITY;")


def seed_docs(cursor):
    docs = [
        {
            "emoji": "🎨",
            "title": "团队视觉与动效风格指南",
            "category": "团队工作区",
            "author": "sout",
            "content": """<h2>🎨 团队视觉与动效风格指南</h2>
<p>在设计 Amnesia 的视觉体系时，我们追求的是<strong>极致的极简主义</strong>与<strong>极具亲和力的动效</strong>。本指南旨在统一团队在开发过程中的审美标准与交互规范，避免粗糙和拼凑感。</p>
<h3>1. 核心色彩与排版</h3>
<ul>
  <li><strong>字形排版</strong>：优先采用现代、质朴的 Google Fonts（如 <em>Inter</em> 与 <em>Outfit</em>），放弃生硬的浏览器系统默认字体。</li>
  <li><strong>色彩搭配</strong>：以高雅的柔和灰（#fafafa, #f4f4f4）作为背景，以低饱和度的点缀色作为主调，杜绝粗糙设计。</li>
</ul>
<h3>2. 动效原则</h3>
<blockquote>“优秀的动效应当如空气般自然，在感知其存在之前已完成引导。”</blockquote>
<p>我们统一使用 <code>animejs</code> 实现流畅的交互过渡。</p>""",
        },
        {
            "emoji": "📝",
            "title": "Amnesia 核心架构与同步方案",
            "category": "团队工作区",
            "author": "sout",
            "content": """<h2>📝 Amnesia 核心架构与同步方案</h2>
<p>Amnesia 是一款基于 <strong>Svelte 5</strong> 与 <strong>Supabase</strong> 构建的轻量级云同步协作知识库。</p>
<h3>1. 技术选型</h3>
<ul>
  <li><strong>前端框架</strong>：Svelte 5。</li>
  <li><strong>富文本内核</strong>：Tiptap。</li>
  <li><strong>云端存储</strong>：Supabase PostgreSQL。</li>
</ul>""",
        },
        {
            "emoji": "🚀",
            "title": "本地数据持久化扩展规范",
            "category": "个人笔记",
            "author": "sout",
            "content": """<h2>🚀 本地数据持久化扩展规范</h2>
<p>离线缓存和持久化存储扩展依旧是未来极致体验的基石。</p>
<pre><code>interface OfflineDoc {
  id: number;
  title: string;
  emoji: string;
  content: string;
  updated_at: string;
}</code></pre>""",
        },
        {
            "emoji": "📅",
            "title": "2026 开发迭代时间表",
            "category": "个人笔记",
            "author": "sout",
            "content": """<h2>📅 2026 开发迭代时间表</h2>
<p>Amnesia 2026 年度的迭代开发计划已经启动。</p>
<blockquote>“细节决定成败。富文本工具条的交互手感与存盘时的静默无感，是我们需要攻克的头等大事。”</blockquote>""",
        },
    ]

    print("Seeding default docs only when table is empty...")
    cursor.execute("SELECT COUNT(*) FROM amnesia_docs;")
    count = cursor.fetchone()[0]
    if count > 0:
        print(f"Skipping seed because table already has {count} docs.")
        return

    for doc in docs:
        cursor.execute(
            """
            INSERT INTO amnesia_docs (emoji, title, category, content, author, settings)
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            (
                doc["emoji"],
                doc["title"],
                doc["category"],
                doc["content"],
                doc["author"],
                Json(DEFAULT_DOC_SETTINGS),
            ),
        )


def main():
    print("Connecting to Supabase PostgreSQL database to init/migrate docs table...")
    try:
        conn = psycopg2.connect(conn_str)
        cursor = conn.cursor()

        ensure_schema(cursor)
        seed_docs(cursor)

        conn.commit()
        print("\namnesia_docs table is ready for production use.")
    except Exception as e:
        print("\nFailed to initialize/migrate amnesia_docs table:", e)
    finally:
        if 'conn' in locals() and conn:
            cursor.close()
            conn.close()


if __name__ == "__main__":
    main()
