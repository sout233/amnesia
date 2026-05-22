import psycopg2

conn_str = "postgresql://postgres:Sout114514.@db.azywleygoqeuvyhnuzxz.supabase.co:5432/postgres"

def main():
    print("Connecting to Supabase PostgreSQL database to init docs table...")
    try:
        conn = psycopg2.connect(conn_str)
        cursor = conn.cursor()
        
        # 1. 创建 amnesia_docs 表
        print("Creating amnesia_docs table if not exists...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS amnesia_docs (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            emoji TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL
        );
        """)
        
        # 2. 禁用 RLS 权限以方便前端 Anon 匿名直连
        print("Disabling RLS on amnesia_docs table...")
        cursor.execute("ALTER TABLE amnesia_docs DISABLE ROW LEVEL SECURITY;")
        
        # 3. 初始四篇文档的数据
        docs = [
            {
                "emoji": "🎨",
                "title": "团队视觉与动效风格指南",
                "category": "团队工作区",
                "content": """<h2>🎨 团队视觉与动效风格指南</h2>
<p>在设计 Amnesia 的视觉体系时，我们追求的是<strong>极致的极简主义</strong>与<strong>极具亲和力的动效</strong>。本指南旨在统一团队在开发过程中的审美标准与交互规范，避免粗糙和拼凑感。</p>
<h3>1. 核心色彩与排版</h3>
<ul>
  <li><strong>字形排版</strong>：优先采用现代、质朴的 Google Fonts（如 <em>Inter</em> 与 <em>Outfit</em>），放弃生硬的浏览器系统默认字体。</li>
  <li><strong>色彩搭配</strong>：以高雅的柔和灰（#fafafa, #f4f4f4）作为背景，以低饱和度的点缀色（如 HSL 微调的品牌深灰与暖灰）作为主调，杜绝高饱和度纯红纯蓝的粗糙设计。</li>
</ul>
<h3>2. 动效原则</h3>
<blockquote>“优秀的动效应当如空气般自然，在感知其存在之前已完成引导。”</blockquote>
<p>我们统一使用 <code>animejs</code> 实现流畅的交互过渡。以下是推荐的缓动参数：</p>
<pre><code>{
  duration: 800,
  ease: 'outExpo'
}</code></pre>
<p>在接下来的开发中，请严格遵守上述规范，保证每一处交互微小动效的呼吸感与高级感。</p>"""
            },
            {
                "emoji": "📝",
                "title": "Amnesia 核心架构与同步方案",
                "category": "团队工作区",
                "content": """<h2>📝 Amnesia 核心架构与同步方案</h2>
<p>Amnesia 是一款基于 <strong>Svelte 5</strong> 与 <strong>Supabase</strong> 构建的轻量级云同步协作知识库。我们的设计核心是确保在离线、单人或多人网络变动时，数据依然能保持绝对的<strong>安全与完整</strong>。</p>
<h3>1. 技术选型</h3>
<ul>
  <li><strong>前端框架</strong>：Svelte 5 响应式系统 (Rune - <code>$state</code>, <code>$derived</code>, <code>$effect</code>)。</li>
  <li><strong>富文本内核</strong>：基于 Tiptap (ProseMirror) 驱动的高扩展性富文本引擎。</li>
  <li><strong>云端存储</strong>：Supabase PostgreSQL。</li>
</ul>
<h3>2. 自动同步与防抖机制</h3>
<p>当用户在富文本编辑器中编辑或修改大标题时，为了避免高频网络请求压垮云端数据库，前端引入了 <strong>1 秒防抖（Debounce）</strong> 机制：</p>
<pre><code>// 每次更新时触发防抖
clearTimeout(saveTimeout);
saveTimeout = setTimeout(() => {
  saveToSupabase();
}, 1000);</code></pre>
<p>每次同步时，编辑器顶部的同步状态指示器会变成“数据自动云同步中...”，并在保存完毕后恢复“云端已同步”，给用户踏实的安全感。</p>"""
            },
            {
                "emoji": "🚀",
                "title": "本地数据持久化扩展规范",
                "category": "个人笔记",
                "content": """<h2>🚀 本地数据持久化扩展规范</h2>
<p>虽然 Amnesia 目前已接入 <strong>Supabase 云端服务</strong> 进行数据的云端实时存储，但对于知识库工具而言，本地离线缓存和持久化存储扩展依旧是未来极致体验的基石。</p>
<h3>1. 离线回退策略</h3>
<p>如果因网络中断导致无法连接到 Supabase 实例，我们需要通过 <code>localStorage</code> 提供无缝的<strong>降级暂存服务</strong>：</p>
<ul>
  <li>当网络离线时，所有编辑器的更新防抖修改直接写入本地 <code>amnesia_offline_docs</code>。</li>
  <li>并在网络检测恢复后，自动发起版本合并，将本地的暂存版本静默同步回 Supabase 数据库中。</li>
</ul>
<h3>2. 离线缓存字段设计</h3>
<p>离线暂存的数据结构设计应与云端表保持完全一致，以减少序列化带来的多余开销：</p>
<pre><code>interface OfflineDoc {
  id: number;
  title: string;
  emoji: string;
  content: string;
  updated_at: string;
}</code></pre>
<p>这项规范是 Amnesia 保持其轻盈感和高可靠性的技术保障。</p>"""
            },
            {
                "emoji": "📅",
                "title": "2026 开发迭代时间表",
                "category": "个人笔记",
                "content": """<h2>📅 2026 开发迭代时间表</h2>
<p>Amnesia 2026 年度的迭代开发计划已经启动。我们将秉承“朴实、高效、极致设计”的路线，分阶段落地各项核心功能。</p>
<h3>1. 核心开发路线图</h3>
<ul>
  <li><strong>第一季度（Q1）</strong>：打通 Svelte 5 基础脚手架，实现 Supabase 用户注册登录与用户权限管理系统（完成 ✅）。</li>
  <li><strong>第二季度（Q2）</strong>：深度实装 Tiptap 富文本编辑器，支持基本的文字排版、格式化、标题同步与云端自动防抖存盘（正在进行 🚀）。</li>
  <li><strong>第三季度（Q3）</strong>：开发块级（Block-based）编辑引擎，并逐步推进多人实时协同与光标位置跟踪。</li>
</ul>
<h3>2. 当前优先级（Q2 核心目标）</h3>
<blockquote>“细节决定成败。富文本工具条的交互手感与存盘时的静默无感，是我们需要攻克的头等大事。”</blockquote>
<p>让我们齐心协力，将 Amnesia 打造得更加精致优秀！</p>"""
            }
        ]
        
        # 清除原有记录，防止重复运行脚本时无限累加
        print("Clearing existing docs from amnesia_docs table...")
        cursor.execute("TRUNCATE TABLE amnesia_docs;")
        
        print("Inserting 4 high-fidelity default docs...")
        for doc in docs:
            cursor.execute("""
            INSERT INTO amnesia_docs (emoji, title, category, content)
            VALUES (%s, %s, %s, %s);
            """, (doc["emoji"], doc["title"], doc["category"], doc["content"]))
            
        conn.commit()
        print("\namnesia_docs table initialized successfully with 4 default docs!")
        
    except Exception as e:
        print("\nFailed to initialize amnesia_docs table:", e)
    finally:
        if 'conn' in locals() and conn:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    main()
