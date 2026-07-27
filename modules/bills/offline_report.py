import json
from datetime import datetime
from typing import Dict, Any, List

from db.connector import get_cursor
from db.repository import (
    list_available_years,
    daily_heatmap_data,
    summary_by_category_month,
    list_categories,
    travel_summary,
    travel_tagged_dates,
    list_bill_dates,
)
from rule_manager import load_rules


def _query_all_records() -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, bill_date, amount, detail, note, direction, category_l1, category,
                   is_travel, travel_tag, source_batch_id, inserted_at, created_at, updated_at
            FROM records
            ORDER BY bill_date DESC, id DESC
            """
        )
        return cur.fetchall()


def collect_payload() -> Dict[str, Any]:
    years = list_available_years()
    if not years:
        years = [datetime.now().year]

    heatmap = {}
    for y in years:
        rows = daily_heatmap_data(int(y))
        m_exp = {}
        m_inc = {}
        annual_exp = 0.0
        annual_inc = 0.0
        month_tot_exp: Dict[str, float] = {}
        month_tot_inc: Dict[str, float] = {}
        max_exp = 0.0
        max_inc = 0.0
        for r in rows:
            day = str(r.get("bill_date"))
            exp = float(r.get("expense", 0.0))
            inc = float(r.get("income", 0.0))
            m_exp[day] = exp
            m_inc[day] = inc
            annual_exp += exp
            annual_inc += inc
            mk = day[:7] if len(day) >= 7 else ""
            if mk:
                month_tot_exp[mk] = month_tot_exp.get(mk, 0.0) + exp
                month_tot_inc[mk] = month_tot_inc.get(mk, 0.0) + inc
            if exp > max_exp:
                max_exp = exp
            if inc > max_inc:
                max_inc = inc
        heatmap[str(y)] = {
            "expense": {"map": m_exp, "max": max_exp, "annual_total": round(annual_exp, 2), "month_totals": month_tot_exp},
            "income": {"map": m_inc, "max": max_inc, "annual_total": round(annual_inc, 2), "month_totals": month_tot_inc},
        }

    travel = travel_summary()
    tagged = travel_tagged_dates(limit=10000)
    rules = load_rules()
    records = _query_all_records()
    bill_dates = list_bill_dates()

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "years": years,
        "heatmap": heatmap,
        "travel": {"summary": travel, "tagged_dates": tagged},
        "types": rules,
        "records": records,
        "bill_dates": bill_dates,
    }


def render_report_html(payload: Dict[str, Any]) -> str:
    data_json = json.dumps(payload, ensure_ascii=False, default=str)
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>个人账单离线报告</title>
  <style>
    :root{--bg:#f3f6fb;--card:#fff;--line:#d9e2f2;--text:#1f2a44;--muted:#5f6b85;--pri:#2f6df6;--pri2:#2458ca;}
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft Yahei",Arial,sans-serif;margin:0;background:linear-gradient(180deg,#f8faff 0%,var(--bg) 100%);color:var(--text);}
    .nav{position:sticky;top:0;z-index:50;background:linear-gradient(90deg,#2c64df 0%,#2f6df6 55%,#4688ff 100%);color:#fff;padding:12px 20px;display:flex;gap:10px;align-items:center;box-shadow:0 6px 20px rgba(30,70,150,.24);}
    .nav a{color:#fff;text-decoration:none;font-weight:700;padding:6px 10px;border-radius:10px;}
    .nav a.active,.nav a:hover{background:rgba(255,255,255,.18);}
    .ver{margin-left:auto;font-size:12px;opacity:.95;background:rgba(255,255,255,.15);padding:4px 8px;border-radius:999px;}
    .wrap{padding:18px 22px 34px;max-width:1600px;margin:0 auto;}
    .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:14px;box-shadow:0 4px 14px rgba(23,53,107,.05);}
    h2{margin:0 0 10px;font-size:18px;} h3{margin:16px 0 8px;font-size:15px;}
    .row{display:flex;gap:10px;flex-wrap:wrap;align-items:end;}
    input,select,button{font-size:14px;}
    input,select{border:1px solid #c8d3ea;border-radius:10px;padding:7px 9px;background:#fff;}
    button{border:0;border-radius:10px;padding:8px 12px;background:var(--pri);color:#fff;cursor:pointer;transition:.15s ease;}
    button:hover{background:var(--pri2);transform:translateY(-1px);}
    .btn2{background:#6b7280;} .btn2:hover{background:#535b69;}
    .muted{color:var(--muted);font-size:12px;}
    .metric{min-width:180px;background:#fbfcff;border:1px solid #e2e8f8;border-radius:12px;padding:10px;}
    .tabs{display:none;}
    table{width:100%;border-collapse:separate;border-spacing:0;font-size:13px;}
    th,td{border-right:1px solid #e5ebf7;border-bottom:1px solid #e5ebf7;padding:7px 8px;vertical-align:top;}
    th:first-child,td:first-child{border-left:1px solid #e5ebf7;}
    thead th{position:sticky;top:0;z-index:2;background:#f3f7ff;}
    tbody tr:hover{background:#f9fbff;}
    .table-wrap{max-height:560px;overflow:auto;}
    .chip{display:inline-flex;align-items:center;gap:6px;border:1px solid #d9e2f2;background:#f6f9ff;padding:4px 8px;border-radius:999px;font-size:12px;color:#35415c;}
  </style>
</head>
<body>
  <div class="nav">
    <a href="#analysis" id="tabbtn-analysis">分析看板</a>
    <a href="#travel" id="tabbtn-travel">旅游管理</a>
    <a href="#records" id="tabbtn-records">数据库记录</a>
    <span class="ver" id="ver"></span>
  </div>
  <div class="wrap">
    <div class="tabs" id="tab-analysis">
      <div class="card">
        <h2>年度日历热力图</h2>
        <div class="row" style="margin-bottom:8px;">
          <div><div>年份</div><select id="hm-year"></select></div>
          <div><div>金额方向</div>
            <select id="hm-metric">
              <option value="expense">支出</option>
              <option value="income">收入</option>
            </select>
          </div>
          <div class="metric">年度总额：<b id="hm-annual">0.00</b></div>
        </div>
        <div class="muted">灰色表示无记录；点击某天可在"数据库记录"里定位到该日。</div>
        <div id="hm-wrap" style="margin-top:10px;"></div>
      </div>

      <div class="card">
        <h2>类型 - 方向 - 日期（月）汇总</h2>
        <div class="row" style="margin-bottom:8px;">
          <div><div>年份</div><select id="sum-year"></select></div>
          <div><div>交易方向</div>
            <select id="sum-dir">
              <option value="">全部</option><option value="支出">支出</option><option value="收入">收入</option>
            </select>
          </div>
          <div style="min-width:320px;">
            <div>类型（可多选）</div>
            <select id="sum-cats" multiple style="min-width:320px;min-height:120px;"></select>
          </div>
          <div><button type="button" onclick="renderSummary()">应用</button></div>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>月份</th><th>方向</th><th>类型</th><th>金额</th></tr></thead>
            <tbody id="sum-body"></tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="tabs" id="tab-travel">
      <div class="card">
        <h2>旅游专题分析（只读）</h2>
        <h3>按行程标签统计</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>行程标签</th><th>开始日期</th><th>结束日期</th><th>持续天数</th><th>旅游支出</th><th>旅游收入</th><th>记录数</th></tr></thead>
            <tbody id="travel-trip"></tbody>
          </table>
        </div>
        <h3>每月旅游/非旅游支出对比</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>月份</th><th>旅游支出</th><th>非旅游支出</th></tr></thead>
            <tbody id="travel-month"></tbody>
          </table>
        </div>
        <h3>旅游支出类型Top12</h3>
        <div class="table-wrap">
          <table>
            <thead><tr><th>类型</th><th>旅游支出</th></tr></thead>
            <tbody id="travel-cat"></tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="tabs" id="tab-records">
      <div class="card">
        <h2>数据库记录（只读）</h2>
        <div class="row" style="margin-bottom:8px;">
          <div style="min-width:360px;">
            <div>关键词（明细/日记）</div>
            <input id="rec-kw" type="text" style="width:100%;" placeholder="输入后自动筛选" />
          </div>
          <div class="chip">日期：<b id="rec-date">全部</b></div>
          <div><button type="button" class="btn2" onclick="clearRecFilter()">清空筛选</button></div>
          <div class="metric" style="min-width:140px;text-align:center;">展示：<b id="rec-count">0</b> 条</div>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>日期</th><th>金额</th><th>方向</th><th>类型</th><th>明细</th><th>旅游</th><th>旅游标签</th><th>日记</th></tr></thead>
            <tbody id="rec-body"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <script id="data" type="application/json">__DATA__</script>
  <script>
    const DATA = JSON.parse(document.getElementById('data').textContent);
    document.getElementById('ver').textContent = '离线生成：' + (DATA.generated_at || '');

    function qs(name){ return new URLSearchParams(location.search).get(name) || ''; }
    function setHash(h){ location.hash = h; }
    function showTab(name){
      ['analysis','travel','records'].forEach(t=>{
        document.getElementById('tab-'+t).style.display = (t===name)?'block':'none';
        document.getElementById('tabbtn-'+t).classList.toggle('active', t===name);
      });
    }
    function bootTabs(){
      const h = (location.hash||'#analysis').slice(1);
      showTab(['analysis','travel','records'].includes(h)?h:'analysis');
      window.addEventListener('hashchange', ()=>bootTabs());
      document.getElementById('tabbtn-analysis').onclick = ()=>{setHash('analysis'); return false;};
      document.getElementById('tabbtn-travel').onclick = ()=>{setHash('travel'); return false;};
      document.getElementById('tabbtn-records').onclick = ()=>{setHash('records'); return false;};
    }

    function renderHeatmap(){
      const wrap = document.getElementById('hm-wrap');
      wrap.innerHTML = '';
      const year = document.getElementById('hm-year').value;
      const metric = document.getElementById('hm-metric').value;
      const hm = (DATA.heatmap && DATA.heatmap[String(year)] && DATA.heatmap[String(year)][metric]) || {map:{},max:1,annual_total:0,month_totals:{}};
      document.getElementById('hm-annual').textContent = (hm.annual_total||0).toFixed(2);
      const data = hm.map || {};
      const monthTotals = hm.month_totals || {};
      const maxVal = Number(hm.max || 1) || 1;
      const isExpense = metric === 'expense';
      const metricLabel = isExpense ? '支出' : '收入';
      function daysInMonth(y, m){ return new Date(y, m, 0).getDate(); }
      function color(v){
        if (!v || v <= 0) return '#e0e0e0';
        const r = Math.min(1, v / maxVal);
        const alpha = 0.2 + r * 0.8;
        return isExpense ? `rgba(47,109,246,${alpha.toFixed(3)})` : `rgba(42,161,112,${alpha.toFixed(3)})`;
      }
      for (let month=1; month<=12; month++){
        const box=document.createElement('div'); box.style.marginBottom='12px';
        const title=document.createElement('div');
        const mk=`${year}-${String(month).padStart(2,'0')}`;
        const monthSum=Number(monthTotals[mk]||0).toFixed(2);
        title.textContent = `${month}月  |  当月${metricLabel}: ${monthSum}`;
        title.style.fontWeight='700'; title.style.marginBottom='4px';
        box.appendChild(title);
        const grid=document.createElement('div');
        grid.style.display='grid'; grid.style.gridTemplateColumns='repeat(31, minmax(22px, 1fr))'; grid.style.gap='3px';
        const dm=daysInMonth(Number(year), month);
        for (let d=1; d<=31; d++){
          const el=document.createElement('div');
          el.style.height='26px'; el.style.borderRadius='6px'; el.style.fontSize='10px';
          el.style.lineHeight='12px'; el.style.padding='1px'; el.style.overflow='hidden'; el.style.textAlign='center';
          el.style.border='1px solid rgba(0,0,0,0.04)';
          if (d>dm){ el.style.background='#f3f3f3'; el.style.cursor='default'; }
          else{
            const ds=`${year}-${String(month).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
            const v=Number(data[ds]||0);
            el.style.background=color(v); el.style.cursor='pointer';
            el.title = `${ds} ${metricLabel}: ${v.toFixed(2)}（点击查看记录）`;
            el.textContent = v>0 ? v.toFixed(0) : '';
            el.onclick = ()=>{ filterRecordsByDate(ds); setHash('records'); };
          }
          grid.appendChild(el);
        }
        box.appendChild(grid);
        wrap.appendChild(box);
      }
    }

    function getSelectedOptions(sel){
      return Array.from(sel.selectedOptions || []).map(o=>o.value).filter(Boolean);
    }
    function renderSummary(){
      const y = document.getElementById('sum-year').value;
      const dir = document.getElementById('sum-dir').value;
      const cats = new Set(getSelectedOptions(document.getElementById('sum-cats')));
      const rows = DATA.records || [];
      const agg = {};
      rows.forEach(r=>{
        const bd = String(r.bill_date||'');
        if (!bd.startsWith(String(y)+'-')) return;
        if (dir && String(r.direction)!==dir) return;
        if (cats.size && !cats.has(String(r.category||''))) return;
        const m = bd.slice(0,7);
        const cat = String(r.category||r.category_l1||'');
        const k = [m, String(r.direction||''), cat].join('|');
        agg[k] = (agg[k]||0) + Number(r.amount||0);
      });
      const out = Object.keys(agg).sort().reverse().map(k=>{
        const [m, d, c] = k.split('|');
        return {month:m, direction:d, category:c, total_amount: Math.round(agg[k]*100)/100};
      });
      const body = document.getElementById('sum-body');
      body.innerHTML = out.length ? out.map(x=>`<tr><td>${x.month}</td><td>${x.direction}</td><td>${x.category}</td><td>${x.total_amount.toFixed(2)}</td></tr>`).join('') : '<tr><td colspan="4" class="muted">无匹配数据</td></tr>';
    }

    function renderTravel(){
      const s = (DATA.travel && DATA.travel.summary) || {};
      const byTrip = (s.by_trip||[]);
      const byMonth = (s.by_month||[]);
      const byCat = (s.by_category||[]);
      document.getElementById('travel-trip').innerHTML = byTrip.map(r=>`<tr><td>${r.travel_tag||''}</td><td>${r.start_date||''}</td><td>${r.end_date||''}</td><td>${r.duration_days||''}</td><td>${r.expense||''}</td><td>${r.income||''}</td><td>${r.record_count||''}</td></tr>`).join('');
      document.getElementById('travel-month').innerHTML = byMonth.map(r=>`<tr><td>${r.month||''}</td><td>${r.travel_expense||''}</td><td>${r.normal_expense||''}</td></tr>`).join('');
      document.getElementById('travel-cat').innerHTML = byCat.map(r=>`<tr><td>${r.category||''}</td><td>${r.expense||''}</td></tr>`).join('');
    }

    let recFilterDate = '';
    function filterRecordsByDate(ds){
      recFilterDate = ds || '';
      document.getElementById('rec-date').textContent = recFilterDate || '全部';
      renderRecords();
    }
    function clearRecFilter(){
      recFilterDate = '';
      document.getElementById('rec-date').textContent = '全部';
      document.getElementById('rec-kw').value = '';
      renderRecords();
    }
    function renderRecords(){
      const kw = (document.getElementById('rec-kw').value||'').trim();
      const rows = (DATA.records||[]).filter(r=>{
        if (recFilterDate && String(r.bill_date)!==recFilterDate) return false;
        if (!kw) return true;
        const d = (String(r.detail||'') + ' ' + String(r.note||'')).toLowerCase();
        return d.includes(kw.toLowerCase());
      });
      document.getElementById('rec-count').textContent = String(rows.length);
      document.getElementById('rec-body').innerHTML = rows.slice(0, 2000).map(r=>`<tr>
        <td>${r.id||''}</td><td>${r.bill_date||''}</td><td>${Number(r.amount||0).toFixed(2)}</td>
        <td>${r.direction||''}</td><td>${r.category||r.category_l1||''}</td><td>${r.detail||''}</td>
        <td>${Number(r.is_travel||0)?'是':'否'}</td><td>${r.travel_tag||''}</td><td>${r.note||''}</td>
      </tr>`).join('') + (rows.length>2000?'<tr><td colspan="9" class="muted">离线版最多渲染前2000条。</td></tr>':'');
    }

    function boot(){
      bootTabs();
      const years = (DATA.years||[]).map(String);
      const yearSel = document.getElementById('hm-year');
      const yearSel2 = document.getElementById('sum-year');
      yearSel.innerHTML = years.map(y=>`<option value="${y}">${y}</option>`).join('');
      yearSel2.innerHTML = years.map(y=>`<option value="${y}">${y}</option>`).join('');
      const catsAll = Array.from(new Set((DATA.records||[]).map(r=>String(r.category||'')).filter(Boolean))).sort();
      document.getElementById('sum-cats').innerHTML = catsAll.map(c=>`<option value="${c}">${c}</option>`).join('');
      document.getElementById('hm-year').onchange = ()=>renderHeatmap();
      document.getElementById('hm-metric').onchange = ()=>renderHeatmap();
      document.getElementById('sum-year').onchange = ()=>renderSummary();
      document.getElementById('sum-dir').onchange = ()=>renderSummary();
      document.getElementById('sum-cats').onchange = ()=>renderSummary();
      document.getElementById('rec-kw').addEventListener('input', ()=>renderRecords());

      renderHeatmap();
      renderSummary();
      renderTravel();
      renderRecords();
      const qd = qs('date');
      if (qd) { filterRecordsByDate(qd); setHash('records'); }
    }
    boot();
  </script>
</body>
</html>
""".replace("__DATA__", data_json)
