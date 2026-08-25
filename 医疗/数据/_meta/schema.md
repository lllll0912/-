# 医疗档案元数据规范（v1）

## catalog.json

顶层对象：

- `version`: 规范版本号
- `person_self`: 本人标识（本地用，不上线可脱敏）
- `generated_at`: 生成时间
- `records`: 档案条目数组

## records[] 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 稳定 ID，建议 `lab-YYYYMMDD-标签` |
| person | string | `self` / `zhangyue` |
| category | string | `lab` / `herb` / `checkup` / `history` / `other` |
| exam_date | string | `YYYY-MM-DD`，优先采样日 |
| exam_name | string | 检查/材料短名 |
| hospital | string | 可空 |
| specimen | string | 尿/血/其他/空 |
| file_name | string | 档案内规范文件名 |
| file_relpath | string | 相对 `档案/` 的路径 |
| source_original | string | 原路径（相对 `医疗/`） |
| notes | string | 可选备注 |
| indicators_status | string | `pending` / `extracted` / `manual` |
| indicators_file | string | 可选，指向 indicators 下 JSON |

## indicators/*.json（下一步 OCR 用）

`json
{
  "record_id": "lab-20240307-生化21",
  "exam_date": "2024-03-07",
  "exam_name": "生化21",
  "items": [
    {
      "name": "总胆红素",
      "code": "TBIL",
      "value": "29.5",
      "unit": "umol/L",
      "ref_range": "3.0-21.0",
      "flag": "H"
    }
  ]
}
`

`flag`: `H` 偏高 / `L` 偏低 / `""` 正常或未标。

## v2 增补字段

| 字段 | 说明 |
|------|------|
| purpose | 看病目的短标签，可空 |
| purpose_note | 目的补充说明 |
| event_id | 同人同日就诊事件 ID，如 evt-self-2024-03-07 |

另见 purposes.json（标签库）、watchlist.json（关注指标）。
