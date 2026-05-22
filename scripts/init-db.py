from __future__ import annotations

import psycopg2
from psycopg2.extras import Json

from db_config import get_database_url


DEFAULT_DOC_SETTINGS = {
    "theme": "cupcake",
    "pagePaddingX": 48,
    "docFontSize": 16,
    "docFontFamily": "Noto Sans SC",
    "lockPage": False,
}


def ensure_extensions(cursor):
    cursor.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')


def ensure_updated_at_function(cursor):
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


def recreate_identities_as_bigint(cursor):
    cursor.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_name = 'amnesia_users' AND column_name = 'id';
        """
    )
    row = cursor.fetchone()
    if row and row[0] != 'bigint':
        raise RuntimeError("amnesia_users.id 当前不是 bigint，本迁移版本暂不自动转换现有主键类型。")

    cursor.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_name = 'amnesia_teams' AND column_name = 'id';
        """
    )
    row = cursor.fetchone()
    if row and row[0] != 'bigint':
        raise RuntimeError("amnesia_teams.id 当前不是 bigint，本迁移版本暂不自动转换现有主键类型。")


def ensure_users(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS amnesia_users (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NULL,
            role TEXT NULL,
            password_hash TEXT NULL,
            system_role TEXT NOT NULL DEFAULT '用户',
            encryption_key_hint TEXT NULL,
            encryption_notice_accepted BOOLEAN NOT NULL DEFAULT FALSE,
            avatar_seed TEXT NULL,
            avatar_url TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    cursor.execute("ALTER TABLE amnesia_users ADD COLUMN IF NOT EXISTS password TEXT NULL;")
    cursor.execute("ALTER TABLE amnesia_users ADD COLUMN IF NOT EXISTS role TEXT NULL;")
    cursor.execute("ALTER TABLE amnesia_users ADD COLUMN IF NOT EXISTS password_hash TEXT NULL;")
    cursor.execute("ALTER TABLE amnesia_users ADD COLUMN IF NOT EXISTS system_role TEXT NOT NULL DEFAULT '用户';")
    cursor.execute("ALTER TABLE amnesia_users ADD COLUMN IF NOT EXISTS encryption_key_hint TEXT NULL;")
    cursor.execute("ALTER TABLE amnesia_users ADD COLUMN IF NOT EXISTS encryption_notice_accepted BOOLEAN NOT NULL DEFAULT FALSE;")
    cursor.execute("ALTER TABLE amnesia_users ADD COLUMN IF NOT EXISTS avatar_seed TEXT NULL;")
    cursor.execute("ALTER TABLE amnesia_users ADD COLUMN IF NOT EXISTS avatar_url TEXT NULL;")
    cursor.execute("ALTER TABLE amnesia_users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();")
    cursor.execute("ALTER TABLE amnesia_users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();")
    cursor.execute(
        """
        UPDATE amnesia_users
        SET system_role = CASE
            WHEN role IN ('root', '管理员', '用户') THEN role
            WHEN system_role IS NULL OR system_role = '' THEN '用户'
            ELSE system_role
        END,
            avatar_seed = COALESCE(NULLIF(avatar_seed, ''), username),
            created_at = COALESCE(created_at, NOW()),
            updated_at = COALESCE(updated_at, NOW());
        """
    )
    cursor.execute("ALTER TABLE amnesia_users DISABLE ROW LEVEL SECURITY;")
    cursor.execute("DROP TRIGGER IF EXISTS amnesia_users_set_updated_at ON amnesia_users;")
    cursor.execute(
        """
        CREATE TRIGGER amnesia_users_set_updated_at
        BEFORE UPDATE ON amnesia_users
        FOR EACH ROW
        EXECUTE FUNCTION amnesia_set_updated_at();
        """
    )


def ensure_teams(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS amnesia_teams (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            owner_user_id BIGINT NOT NULL REFERENCES amnesia_users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS amnesia_team_members (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            team_id BIGINT NOT NULL REFERENCES amnesia_teams(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL REFERENCES amnesia_users(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'member')),
            joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(team_id, user_id)
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS amnesia_team_invites (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            team_id BIGINT NOT NULL REFERENCES amnesia_teams(id) ON DELETE CASCADE,
            token TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
            created_by_user_id BIGINT NOT NULL REFERENCES amnesia_users(id) ON DELETE CASCADE,
            expires_at TIMESTAMPTZ NULL,
            used_at TIMESTAMPTZ NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    cursor.execute("ALTER TABLE amnesia_teams ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();")
    cursor.execute("ALTER TABLE amnesia_team_members ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();")
    cursor.execute("ALTER TABLE amnesia_team_members ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();")
    cursor.execute("ALTER TABLE amnesia_team_invites ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'member';")
    cursor.execute("ALTER TABLE amnesia_teams DISABLE ROW LEVEL SECURITY;")
    cursor.execute("ALTER TABLE amnesia_team_members DISABLE ROW LEVEL SECURITY;")
    cursor.execute("ALTER TABLE amnesia_team_invites DISABLE ROW LEVEL SECURITY;")
    cursor.execute("DROP TRIGGER IF EXISTS amnesia_teams_set_updated_at ON amnesia_teams;")
    cursor.execute("DROP TRIGGER IF EXISTS amnesia_team_members_set_updated_at ON amnesia_team_members;")
    cursor.execute(
        """
        CREATE TRIGGER amnesia_teams_set_updated_at
        BEFORE UPDATE ON amnesia_teams
        FOR EACH ROW
        EXECUTE FUNCTION amnesia_set_updated_at();
        """
    )
    cursor.execute(
        """
        CREATE TRIGGER amnesia_team_members_set_updated_at
        BEFORE UPDATE ON amnesia_team_members
        FOR EACH ROW
        EXECUTE FUNCTION amnesia_set_updated_at();
        """
    )


def ensure_docs(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS amnesia_docs (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            emoji TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            author TEXT DEFAULT 'sout',
            owner_user_id BIGINT NULL REFERENCES amnesia_users(id) ON DELETE SET NULL,
            team_id BIGINT NULL REFERENCES amnesia_teams(id) ON DELETE SET NULL,
            space_type TEXT NOT NULL DEFAULT 'global' CHECK (space_type IN ('global', 'team', 'private')),
            is_encrypted BOOLEAN NOT NULL DEFAULT FALSE,
            encryption_version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            settings JSONB NOT NULL DEFAULT '{}'::jsonb
        );
        """
    )
    cursor.execute("ALTER TABLE amnesia_docs ADD COLUMN IF NOT EXISTS author TEXT DEFAULT 'sout';")
    cursor.execute("ALTER TABLE amnesia_docs ADD COLUMN IF NOT EXISTS owner_user_id BIGINT NULL REFERENCES amnesia_users(id) ON DELETE SET NULL;")
    cursor.execute("ALTER TABLE amnesia_docs ADD COLUMN IF NOT EXISTS team_id BIGINT NULL REFERENCES amnesia_teams(id) ON DELETE SET NULL;")
    cursor.execute("ALTER TABLE amnesia_docs ADD COLUMN IF NOT EXISTS space_type TEXT NOT NULL DEFAULT 'global';")
    cursor.execute("ALTER TABLE amnesia_docs ADD COLUMN IF NOT EXISTS is_encrypted BOOLEAN NOT NULL DEFAULT FALSE;")
    cursor.execute("ALTER TABLE amnesia_docs ADD COLUMN IF NOT EXISTS encryption_version INTEGER NOT NULL DEFAULT 1;")
    cursor.execute("ALTER TABLE amnesia_docs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();")
    cursor.execute("ALTER TABLE amnesia_docs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();")
    cursor.execute("ALTER TABLE amnesia_docs ADD COLUMN IF NOT EXISTS settings JSONB NOT NULL DEFAULT '{}'::jsonb;")
    cursor.execute(
        """
        UPDATE amnesia_docs
        SET author = COALESCE(NULLIF(author, ''), 'sout'),
            space_type = CASE
                WHEN space_type IN ('global', 'team', 'private') THEN space_type
                WHEN category = '团队工作区' THEN 'team'
                WHEN category = 'Amnesia 共享文章' THEN 'global'
                ELSE 'private'
            END,
            is_encrypted = COALESCE(is_encrypted, FALSE),
            encryption_version = COALESCE(encryption_version, 1),
            created_at = COALESCE(created_at, NOW()),
            updated_at = COALESCE(updated_at, NOW()),
            settings = CASE
                WHEN settings IS NULL OR settings = '{}'::jsonb THEN %s::jsonb
                ELSE settings
            END;
        """,
        (Json(DEFAULT_DOC_SETTINGS),),
    )
    cursor.execute("ALTER TABLE amnesia_docs DISABLE ROW LEVEL SECURITY;")
    cursor.execute("DROP TRIGGER IF EXISTS amnesia_docs_set_updated_at ON amnesia_docs;")
    cursor.execute(
        """
        CREATE TRIGGER amnesia_docs_set_updated_at
        BEFORE UPDATE ON amnesia_docs
        FOR EACH ROW
        EXECUTE FUNCTION amnesia_set_updated_at();
        """
    )


def seed_root(cursor):
    cursor.execute(
        """
        INSERT INTO amnesia_users (username, password_hash, system_role, encryption_notice_accepted)
        VALUES ('sout', 'legacy-bootstrap-root', 'root', TRUE)
        ON CONFLICT (username) DO UPDATE
        SET system_role = EXCLUDED.system_role,
            encryption_notice_accepted = TRUE;
        """
    )


def seed_docs(cursor):
    docs = [
        {
            "emoji": "🎨",
            "title": "团队视觉与动效风格指南",
            "category": "团队工作区",
            "author": "sout",
            "space_type": "team",
            "content": """<h2>🎨 团队视觉与动效风格指南</h2>
<p>在设计 Amnesia 的视觉体系时，我们追求的是<strong>极致的极简主义</strong>与<strong>极具亲和力的动效</strong>。本指南旨在统一团队在开发过程中的审美标准与交互规范，避免粗糙和拼凑感。</p>
<h3>1. 核心色彩与排版</h3>
<ul>
  <li><strong>字形排版</strong>：优先采用现代、质朴的 Google Fonts（如 <em>Inter</em> 与 <em>Outfit</em>），放弃生硬的浏览器系统默认字体。</li>
  <li><strong>色彩搭配</strong>：以高雅的柔和灰作为背景，以低饱和度点缀色作为主调。</li>
</ul>""",
        },
        {
            "emoji": "📝",
            "title": "Amnesia 核心架构与同步方案",
            "category": "Amnesia 共享文章",
            "author": "sout",
            "space_type": "global",
            "content": """<h2>📝 Amnesia 核心架构与同步方案</h2>
<p>Amnesia 是一款基于 <strong>Svelte 5</strong> 与 <strong>Supabase</strong> 构建的轻量级云同步协作知识库。</p>""",
        },
        {
            "emoji": "🚀",
            "title": "本地数据持久化扩展规范",
            "category": "个人笔记",
            "author": "sout",
            "space_type": "private",
            "content": """<h2>🚀 本地数据持久化扩展规范</h2>
<p>离线缓存和持久化存储扩展依旧是未来极致体验的基石。</p>""",
        },
    ]

    cursor.execute("SELECT COUNT(*) FROM amnesia_docs;")
    count = cursor.fetchone()[0]
    if count > 0:
        return

    cursor.execute("SELECT id FROM amnesia_users WHERE username = 'sout' LIMIT 1;")
    row = cursor.fetchone()
    owner_user_id = row[0] if row else None

    for doc in docs:
        cursor.execute(
            """
            INSERT INTO amnesia_docs (
                emoji, title, category, content, author, owner_user_id, space_type, settings
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (
                doc["emoji"],
                doc["title"],
                doc["category"],
                doc["content"],
                doc["author"],
                owner_user_id,
                doc["space_type"],
                Json(DEFAULT_DOC_SETTINGS),
            ),
        )


def main():
    print("Connecting to database and applying Amnesia schema migration...")
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(get_database_url())
        cursor = conn.cursor()
        ensure_extensions(cursor)
        ensure_updated_at_function(cursor)
        recreate_identities_as_bigint(cursor)
        ensure_users(cursor)
        ensure_teams(cursor)
        ensure_docs(cursor)
        seed_root(cursor)
        seed_docs(cursor)
        conn.commit()
        print("Amnesia 数据库迁移完成。")
    except Exception as error:
        if conn:
            conn.rollback()
        print("Amnesia 数据库迁移失败:", error)
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
