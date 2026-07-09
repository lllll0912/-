const express = require('express');
const cors = require('cors');
const mysql = require('mysql2/promise');
const cron = require('node-cron');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// 根据你本机 MySQL 配置修改这些环境变量或硬编码
const DB_CONFIG = {
  host: process.env.DB_HOST || 'localhost',
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || '',
  database: process.env.DB_NAME || 'poems'
};

let pool;

async function initDb() {
  pool = await mysql.createPool({
    ...DB_CONFIG,
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
  });
}

// 每日 22:00 自动选择一条未推送过的诗句
async function selectDailyPoem() {
  const conn = await pool.getConnection();
  try {
    // 是否已经为今天选过
    const [todayRows] = await conn.query(
      'SELECT * FROM poems_table WHERE done = 1 AND done_data = CURDATE() ORDER BY id LIMIT 1'
    );
    if (todayRows.length > 0) {
      return todayRows[0];
    }

    // 选取一条还没推送过的（简单起见按 id 排序取第一条）
    const [rows] = await conn.query(
      'SELECT * FROM poems_table WHERE done = 0 ORDER BY id LIMIT 1'
    );
    if (rows.length === 0) {
      // 所有都推送完了，退化为取最新的一条
      const [fallback] = await conn.query(
        'SELECT * FROM poems_table ORDER BY done_data DESC, id DESC LIMIT 1'
      );
      return fallback[0] || null;
    }
    const poem = rows[0];

    // 标记为今日已推送
    await conn.query(
      'UPDATE poems_table SET done = 1, done_data = CURDATE() WHERE id = ?',
      [poem.id]
    );

    poem.done = 1;
    poem.done_data = new Date();
    return poem;
  } finally {
    conn.release();
  }
}

// 定时任务：每天 22:00 触发
cron.schedule('0 22 * * *', async () => {
  try {
    console.log('[CRON] selecting daily poem at 22:00');
    await selectDailyPoem();
  } catch (e) {
    console.error('[CRON] failed to select daily poem', e);
  }
});

// 获取今日推荐（如果今天还没生成，则自动选择一条）
app.get('/api/today', async (req, res) => {
  try {
    const conn = await pool.getConnection();
    try {
      const [todayRows] = await conn.query(
        'SELECT * FROM poems_table WHERE done = 1 AND done_data = CURDATE() ORDER BY id LIMIT 1'
      );
      if (todayRows.length > 0) {
        return res.json(todayRows[0]);
      }
    } finally {
      conn.release();
    }

    const poem = await selectDailyPoem();
    if (!poem) {
      return res.status(404).json({ message: '暂无诗句数据' });
    }
    res.json(poem);
  } catch (e) {
    console.error(e);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 历史推送（全局），按日期倒序
app.get('/api/history', async (req, res) => {
  const page = Number(req.query.page || 1);
  const pageSize = Number(req.query.pageSize || 20);
  const offset = (page - 1) * pageSize;

  try {
    const conn = await pool.getConnection();
    try {
      const [rows] = await conn.query(
        'SELECT * FROM poems_table WHERE done = 1 ORDER BY done_data DESC, id DESC LIMIT ? OFFSET ?',
        [pageSize, offset]
      );
      res.json(rows);
    } finally {
      conn.release();
    }
  } catch (e) {
    console.error(e);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 收藏相关：需要一个 favorites 表
// CREATE TABLE favorites (
//   id INT AUTO_INCREMENT PRIMARY KEY,
//   user_id VARCHAR(64), -- 小程序 openid 或 Web 端生成的 uuid
//   poem_id INT,
//   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
// );

// 标记收藏
app.post('/api/favorites', async (req, res) => {
  const { userId, poemId } = req.body || {};
  if (!userId || !poemId) {
    return res.status(400).json({ message: 'userId 和 poemId 必填' });
  }

  try {
    const conn = await pool.getConnection();
    try {
      await conn.query(
        'INSERT IGNORE INTO favorites(user_id, poem_id) VALUES(?, ?)',
        [userId, poemId]
      );
      res.json({ success: true });
    } finally {
      conn.release();
    }
  } catch (e) {
    console.error(e);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 取消收藏
app.delete('/api/favorites', async (req, res) => {
  const { userId, poemId } = req.body || {};
  if (!userId || !poemId) {
    return res.status(400).json({ message: 'userId 和 poemId 必填' });
  }
  try {
    const conn = await pool.getConnection();
    try {
      await conn.query(
        'DELETE FROM favorites WHERE user_id = ? AND poem_id = ?',
        [userId, poemId]
      );
      res.json({ success: true });
    } finally {
      conn.release();
    }
  } catch (e) {
    console.error(e);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 获取用户收藏列表
app.get('/api/favorites', async (req, res) => {
  const userId = req.query.userId;
  if (!userId) {
    return res.status(400).json({ message: 'userId 必填' });
  }
  try {
    const conn = await pool.getConnection();
    try {
      const [rows] = await conn.query(
        `SELECT p.*
         FROM favorites f
         JOIN poems_table p ON f.poem_id = p.id
         WHERE f.user_id = ?
         ORDER BY f.created_at DESC`,
        [userId]
      );
      res.json(rows);
    } finally {
      conn.release();
    }
  } catch (e) {
    console.error(e);
    res.status(500).json({ message: '服务器错误' });
  }
});

// 启动服务
initDb()
  .then(() => {
    app.listen(PORT, () => {
      console.log(`Server is running at http://localhost:${PORT}`);
    });
  })
  .catch((err) => {
    console.error('Failed to init DB pool', err);
    process.exit(1);
  });

