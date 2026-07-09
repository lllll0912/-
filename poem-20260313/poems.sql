-- 使用 teacher_db 数据库
USE teacher_db;

-- 查看诗句主表结构
DESC poems;

-- 统计总数量、最早/最晚日期，确认导入是否完整
SELECT
  COUNT(*)            AS total_poems,
  MIN(poem_date)      AS earliest_date,
  MAX(poem_date)      AS latest_date,
  SUM(done = 1)       AS pushed_count,
  SUM(done = 0)       AS not_pushed_count
FROM poems;

-- 随机查看几条记录（按日期与 id 排序）
SELECT
  id,
  poem_date,
  content,
  done,
  done_date,
  created_at
FROM poems
ORDER BY poem_date, id
LIMIT 50;

-- 查看某天的诗句（示例：2020-12-23）
SELECT *
FROM poems
WHERE poem_date = '2020-12-23';

-- 查看某条具体内容是否存在
SELECT *
FROM poems
WHERE content LIKE '%竹斋眠听雨，梦里长青苔%';

