import sqlite3, os, json, glob, math, csv, collections, datetime as dt
import exchange_calendars as xc, pandas as pd
cal = xc.get_calendar("XNYS")
c = sqlite3.connect("file:"+os.path.expanduser("~/swing-data/swing.db")+"?mode=ro", uri=True)
ASOF = "2026-11-10"
sess = [d.strftime("%Y-%m-%d") for d in cal.sessions_in_range("2026-06-01", ASOF)]
idx = {d:i for i,d in enumerate(sess)}
def age(d): return idx[ASOF]-idx[d] if d in idx else None
# 1 drumbeat
exp = [d for d in sess if "2026-10-19" <= d <= ASOF]
runs = {r[0] for r in c.execute("select distinct data_asof_date from evaluation_runs e where data_asof_date>='2026-10-19'")}
pr = c.execute("select id,state,started_ts,action_session_date from pipeline_runs where started_ts>='2026-10-19' order by id").fetchall()
print("DRUMBEAT expected", len(exp), "eval data_asof covered", len(set(exp)&runs), "missing", sorted(set(exp)-runs))
print(" pipeline runs", len(pr), [(r[0],r[1]) for r in pr if r[1]!='complete'])
arts = sorted(glob.glob("exports/research/shadow-expectancy-2026*"))
adates = collections.Counter()
for a in arts:
    ts = os.path.basename(a).split("-")[-1]
    if ts >= "20261019": adates[ts[:8]] += 1
print(" artifacts since 10-19:", sum(adates.values()), dict(adates))
N = arts[-1]; print("NEWEST", N)
m = json.load(open(N+"/manifest.json"))
# invalid_ohlc / degenerate_risk series across manifests
ser = []
for a in arts:
    try:
        mm = json.load(open(a+"/manifest.json")); ex = mm["funnel"]["per_hypothesis"].get("Broad-watch baseline",{}).get("excluded",{})
        ser.append((os.path.basename(a)[-16:-8], mm["funnel"]["detection_level"]["unique_signals"], ex.get("invalid_ohlc"), ex.get("degenerate_risk"), ex.get("insufficient_forward_depth"), ex.get("missing_observations")))
    except Exception as e: pass
print("SERIES date,signals,invalid_ohlc,degenerate_risk,ifd,missing:")
for s in ser[-20:]: print("  ", s)
# ETF set
etf = {r[0] for r in c.execute("select distinct ticker from candidates where industry='Exchange Traded Fund'")}
print("ETF tickers", len(etf))
rows = list(csv.DictReader(open(N+"/results.csv")))
print("results rows", len(rows), collections.Counter(r["hypothesis"] for r in rows))
def stats(v):
    n=len(v)
    if n==0: return "n=0"
    mu=sum(v)/n; sd=(sum((x-mu)**2 for x in v)/(n-1))**0.5 if n>1 else 0; h=1.96*sd/math.sqrt(n) if n>1 else float('nan')
    return f"n={n} mean={mu:+.4f} [{mu-h:+.3f},{mu+h:+.3f}] hw={h:.3f}"
def wilson(k,n,z=1.96):
    if n==0: return 0
    p=k/n; return (p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)
bw = [r for r in rows if r["hypothesis"]=="Broad-watch baseline"]
for r in bw:
    r["age"]=age(r["detection_date"]); r["R"]=float(r["realistic_r"]); r["closed"]=(r["exit_reason"] not in ("","horizon_mtm") and r["open_at_horizon"]=="False")
print("exit reasons:", collections.Counter((r["exit_reason"], r["open_at_horizon"]) for r in bw))
print("BW triggered", len(bw), "names", len({r['ticker'] for r in bw}), "closed", sum(r['closed'] for r in bw), "closed names", len({r['ticker'] for r in bw if r['closed']}))
print("COHORT TABLE (month | trig | closure | closed n/names | closed mean | nonETF | mtm)")
bym = collections.defaultdict(list)
for r in bw: bym[r["detection_date"][:7]].append(r)
for mo in sorted(bym):
    g=bym[mo]; cl=[r for r in g if r["closed"]]
    print(f"  {mo} minage={min(r['age'] for r in g)} trig={len(g)} closure={len(cl)/len(g):.1%} names={len({r['ticker'] for r in cl})} | closed {stats([r['R'] for r in cl])} | nonETF {stats([r['R'] for r in cl if r['ticker'] not in etf])} | mtm {stats([r['R'] for r in g])}")
mat=[r for r in bw if r["age"]>=30]; mc=[r for r in mat if r["closed"]]
print("POOLED age>=30 closed:", stats([r['R'] for r in mc]), "names", len({r['ticker'] for r in mc}))
print("POOLED age>=30 mtm:", stats([r['R'] for r in mat]))
print("  nonETF closed:", stats([r['R'] for r in mc if r['ticker'] not in etf]), "| nonETF mtm:", stats([r['R'] for r in mat if r['ticker'] not in etf]))
w=sum(1 for r in mc if r['R']>0); print("  win", w, len(mc), f"{w/len(mc):.1%} wilsonLB {wilson(w,len(mc)):.1%}")
print("  exit mix mature:", collections.Counter(r['exit_reason'] for r in mc))
print("  ETF slice closed:", stats([r['R'] for r in mc if r['ticker'] in etf]), "names", len({r['ticker'] for r in mc if r['ticker'] in etf}))
print("BRACKETS closed-only:", [(a, stats([r['R'] for r in bw if r['closed'] and r['age']>=a])) for a in (0,30,50,70,90,100)])
# era split by run_id
for name, f in (("pre-D84 (run<200)", lambda r:int(r['run_id'])<200), ("D84..pre-widen (200-202)", lambda r:200<=int(r['run_id'])<=202), ("widened (run>=203)", lambda r:int(r['run_id'])>=203)):
    g=[r for r in bw if f(r)]; cl=[r for r in g if r['closed']]
    print("ERA", name, "trig", len(g), "names", len({r['ticker'] for r in g}), "closed", stats([r['R'] for r in cl]), "mtm", stats([r['R'] for r in g]))
for h in ("A+ baseline","Near-A+ defensible: extension test"):
    g=[r for r in rows if r["hypothesis"]==h]
    print("ARM", h, len(g), [(r['ticker'],r['detection_date'],r['realistic_r'],r['exit_reason']) for r in g][-8:])
# log maturity
print("LOG:", c.execute("select min(detection_date), max(detection_date), count(*), count(distinct ticker) from pattern_detection_events").fetchone(), c.execute("select count(*), max(observation_date) from pattern_forward_observations").fetchone())
print("T9 score>0 distinct names:", c.execute("select pattern_class, count(distinct ticker) from pattern_detection_events where composite_score>0 group by pattern_class").fetchall())
print(" since run 203:", c.execute("select pattern_class, count(distinct ticker), count(*) from pattern_detection_events where composite_score>0 and pipeline_run_id>=203 group by pattern_class").fetchall())
# live
print("TRADES since 10-18:", c.execute("select id,ticker,entry_date,state,entry_intent,hypothesis_label from trades where entry_date>='2026-10-18'").fetchall())
print("fills since 10-18:", c.execute("select trade_id, fill_ts, kind, qty, price from fills where fill_ts>='2026-10-18'").fetchall() if 'fill_ts' in [x[1] for x in c.execute('pragma table_info(fills)')] else [x[1] for x in c.execute('pragma table_info(fills)')])
print("aplus rows since 13591:", c.execute("select count(*) from candidates where bucket='aplus' and id>13591").fetchone())
print("open discrepancies:", c.execute("select discrepancy_type, status, count(*) from reconciliation_discrepancies where status not in ('resolved','auto_corrected') group by 1,2").fetchall() if 'status' in [x[1] for x in c.execute('pragma table_info(reconciliation_discrepancies)')] else [x[1] for x in c.execute('pragma table_info(reconciliation_discrepancies)')])
# risk flags post boundary
print("cc cols:", [x[1] for x in c.execute('pragma table_info(candidate_criteria)')])
