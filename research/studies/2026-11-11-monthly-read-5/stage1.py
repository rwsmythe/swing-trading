import sqlite3, os, re, json, collections, statistics as st
from swing.data.repos.candidates import fetch_candidates_for_run
from swing.data.repos.hypothesis import list_hypotheses
from swing.recommendations.hypothesis import match_candidate_to_hypotheses
c = sqlite3.connect("file:"+os.path.expanduser("~/swing-data/swing.db")+"?mode=ro", uri=True); c.row_factory = sqlite3.Row
reg = list_hypotheses(c)
print("FETCHES:")
for r in c.execute("select call_id, ts, row_count, status from finviz_api_calls where call_id>=146 order by call_id"): print("  ", tuple(r))
print("PER RUN: run eval asof n a/w/s | evaluate detect observe total(s) | narrow matches H1/H2/H4")
ev = c.execute("select e.id, e.data_asof_date, e.tickers_evaluated, e.aplus_count, e.watch_count, e.skip_count from evaluation_runs e where e.id>=176 order by e.id").fetchall()
pr = {r['action_session_date']:r for r in c.execute("select id, action_session_date, started_ts, finished_ts from pipeline_runs where state='complete' order by id")}
ers = {r['id']:r['action_session_date'] for r in c.execute("select id, action_session_date from evaluation_runs")}
hyp_series = {}
for e in ev:
    p = pr.get(ers[e['id']]); rid = p['id'] if p else None
    t = {r['step_name']:r['duration_ms'] for r in c.execute("select step_name, duration_ms from pipeline_step_timings where run_id=?", (rid,))} if rid else {}
    cands = fetch_candidates_for_run(c, e['id'])
    cnt = collections.Counter(); names = collections.defaultdict(list)
    for cd in cands:
        for m in match_candidate_to_hypotheses(cd, registry=reg):
            k = m.hypothesis_name.split()[0]; cnt[k]+=1; names[k].append(cd.ticker)
    hyp_series[e['id']] = names
    print(f"  {rid} {e['id']} {e['data_asof_date']} {e['tickers_evaluated']:4d} {e['aplus_count']}/{e['watch_count']}/{e['skip_count']} | {t.get('evaluate',0)/1000:6.1f} {t.get('pattern_detect',0)/1000:6.1f} {t.get('pattern_observe',0)/1000:6.1f} {sum(t.values())/1000:6.1f} | {dict(cnt)} {dict(names).get('Near-A+','')}")
# classify widened candidates
def parse(cid):
    d = {r['criterion_name']:(r['result'], r['value']) for r in c.execute("select criterion_name, result, value from candidate_criteria where candidate_id=?", (cid,))}
    return d
num = lambda s: float(re.search(r"[-+]?\d+\.?\d*", s).group()) if s and re.search(r"[-+]?\d+\.?\d*", s) else None
agg = collections.defaultdict(lambda: collections.Counter()); fails = collections.defaultdict(collections.Counter); nfail = collections.defaultdict(collections.Counter)
tick = collections.defaultdict(set); riskflag = collections.Counter(); onemiss = collections.defaultdict(collections.Counter)
VCP = None
for r in c.execute("select id, evaluation_run_id, ticker, bucket, close from candidates where evaluation_run_id between 188 and 197 and bucket in ('aplus','watch','skip')"):
    d = parse(r['id'])
    if not d: continue
    dist = abs(num(d['TT7_within_52w_high_25pct'][1]) or 0) if 'TT7_within_52w_high_25pct' in d else None
    cap = (r['close'] or 0) > 100; far = dist is not None and dist > 10
    cls = "both" if cap and far else "cap>100" if cap else "10-25%off" if far else "old-screen"
    agg[cls][r['bucket']] += 1; tick[(cls, r['bucket'])].add(r['ticker']); tick[(cls,'all')].add(r['ticker'])
    f = sorted(k for k,v in d.items() if v[0] != 'pass' and k != 'risk_feasibility')
    for k in f: fails[cls][k] += 1
    nfail[cls][len(f)] += 1
    if len(f) == 1: onemiss[cls][f[0]] += 1
    if d.get('risk_feasibility',('pass',))[0] != 'pass': riskflag[(cls, r['bucket'])] += 1
print("CLASS x BUCKET rows (evals 188-197):")
for k in agg: 
    tot = sum(agg[k].values())
    print(f"  {k:11s} rows={tot} {dict(agg[k])} watch-rate={agg[k]['watch']/tot:.1%} | distinct tickers all={len(tick[(k,'all')])} watch={len(tick[(k,'watch')])}")
    print("     fail freq:", [(n, f"{v/tot:.0%}") for n,v in fails[k].most_common(7)])
    print("     n-fails dist:", sorted(nfail[k].items()), "| one-miss:", dict(onemiss[k]))
print("RISK FLAG rows by (class,bucket):", dict(riskflag))
print("risk non-pass by eval>=186:", [tuple(r) for r in c.execute("select c.evaluation_run_id, c.bucket, count(*) from candidate_criteria cc join candidates c on c.id=cc.candidate_id where cc.criterion_name='risk_feasibility' and cc.result!='pass' and c.evaluation_run_id>=186 group by 1,2")])
# pre-widening baseline same stats evals 176-187
pre = collections.Counter(); pren = collections.Counter(); pret=set(); prew=set()
for r in c.execute("select id, ticker, bucket from candidates where evaluation_run_id between 176 and 187 and bucket in ('aplus','watch','skip')"):
    pre[r['bucket']] += 1; pret.add(r['ticker']); 
    if r['bucket']=='watch': prew.add(r['ticker'])
print("PRE (176-187):", dict(pre), "watch-rate", f"{pre['watch']/sum(pre.values()):.1%}", "tickers", len(pret), "watch tickers", len(prew))
post = collections.Counter()
for k in agg: post.update(agg[k])
print("POST (188-197):", dict(post), "watch-rate", f"{post['watch']/sum(post.values()):.1%}")
# watch names post that are new-class only
print("watch tickers by class:", {k[0]: sorted(v) for k,v in tick.items() if k[1]=='watch'})
# TT8 margin in pool: excess distribution
ex = []
for r in c.execute("select cc.value from candidate_criteria cc join candidates c on c.id=cc.candidate_id where c.evaluation_run_id=197 and cc.criterion_name='TT8_rs_rank'"):
    m = re.search(r"excess=([-+]?\d+\.?\d*)", r[0] or ""); 
    if m: ex.append(float(m.group(1)))
print("eval 197 TT8 excess: n", len(ex), "min", min(ex), "p10", sorted(ex)[len(ex)//10], "median", st.median(ex), "fails(<20):", sum(1 for x in ex if x<20))
pt = [num(r[0]) for r in c.execute("select cc.value from candidate_criteria cc join candidates c on c.id=cc.candidate_id where c.evaluation_run_id=197 and cc.criterion_name='prior_trend'")]
pt=[x for x in pt if x is not None]; print("eval 197 prior_trend: min", min(pt), "p10", sorted(pt)[len(pt)//10], "median", st.median(pt), "fails(<25):", sum(1 for x in pt if x<25))
print("skip reasons eval 188-197 TT-level:", [tuple(r) for r in c.execute("select cc.criterion_name, count(*) from candidate_criteria cc join candidates c on c.id=cc.candidate_id where c.evaluation_run_id between 188 and 197 and c.bucket='skip' and cc.result!='pass' and cc.layer='trend_template' group by 1 order by 2 desc")])
