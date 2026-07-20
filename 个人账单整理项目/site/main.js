const DEMO = {
  year: 2025,
  expense: 12860.5,
  income: 32000,
  travel: 2460,
  rows: [
    { date: "2025-01-05", detail: "超市采购", cat: "食品饮料", dir: "支出", amount: 186.3 },
    { date: "2025-01-12", detail: "地铁充值", cat: "交通", dir: "支出", amount: 100 },
    { date: "2025-02-14", detail: "晚餐", cat: "食品饮料", dir: "支出", amount: 268 },
    { date: "2025-03-01", detail: "工资", cat: "工资收入", dir: "收入", amount: 16000 },
    { date: "2025-03-18", detail: "酒店", cat: "交通", dir: "支出", amount: 520 },
    { date: "2025-04-02", detail: "咖啡会员", cat: "会员", dir: "支出", amount: 35 },
    { date: "2025-05-20", detail: "景点门票", cat: "娱乐/运动", dir: "支出", amount: 160 },
    { date: "2025-06-08", detail: "药店", cat: "医药", dir: "支出", amount: 89.5 },
    { date: "2025-07-01", detail: "工资", cat: "工资收入", dir: "收入", amount: 16000 },
    { date: "2025-08-15", detail: "机票", cat: "交通", dir: "支出", amount: 980 },
  ],
};

function money(n) {
  return "¥" + Number(n).toLocaleString("zh-CN", { minimumFractionDigits: 0 });
}

document.getElementById("stats").innerHTML = [
  ["演示年份", DEMO.year],
  ["支出合计", money(DEMO.expense)],
  ["收入合计", money(DEMO.income)],
  ["旅游相关", money(DEMO.travel)],
]
  .map(
    ([k, v]) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`
  )
  .join("");

document.getElementById("rows").innerHTML = DEMO.rows
  .map(
    (r) =>
      `<tr><td>${r.date}</td><td>${r.detail}</td><td>${r.cat}</td><td>${r.dir}</td><td>${money(
        r.amount
      )}</td></tr>`
  )
  .join("");
