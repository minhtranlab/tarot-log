"""Playwright test against a mock Google Sheet (Apps Script) server: immediate save, offline outbox, Sync now, note autosave.
Needs: pip install playwright. Edit the file:// path to your checkout. Run: python3 src/test_sync.py"""
import json,re
from playwright.sync_api import sync_playwright
TOK='test-token'
rows={}
for i in range(45):
    rows['seed%02d'%i]={'id':'seed%02d'%i,'ts':1790000000000+i*1000,'spread':'one','q':'seed %d'%i,'note':'','manual':False,'groups':[{'name':'','cards':[{'k':'m00','rev':False,'jp':False,'x':False,'n':1}]}]}
log=[]
import time
state={'offline':False}
def handle(route):
    req=route.request; u=req.url
    if 'script.google.com' in u and state['offline']: return route.abort()
    if 'script.google.com' in u: time.sleep(0.8)
    if 'script.google.com' not in u: return route.continue_()
    h={'Access-Control-Allow-Origin':'*','Content-Type':'application/json'}
    if req.method=='OPTIONS': return route.fulfill(status=204,headers=h)
    if req.method=='GET':
        from urllib.parse import urlparse,parse_qs
        q={k:v[0] for k,v in parse_qs(urlparse(u).query).items()}
        if q.get('token')!=TOK: return route.fulfill(headers=h,body=json.dumps({'ok':False,'error':'auth'}))
        items=sorted(rows.values(),key=lambda r:-r['ts']); o=int(q['offset']); l=int(q['limit'])
        log.append(('list',o,l))
        return route.fulfill(headers=h,body=json.dumps({'ok':True,'items':items[o:o+l],'total':len(items)}))
    b=json.loads(req.post_data)
    if b['token']!=TOK: return route.fulfill(headers=h,body=json.dumps({'ok':False,'error':'auth'}))
    log.append((b['action'],))
    if b['action']=='put': rows[b['entry']['id']]=b['entry']
    elif b['action']=='patch': rows[b['id']].update({k:v for k,v in b['p'].items() if k!='text'})
    elif b['action']=='del': rows.pop(b['id'],None)
    route.fulfill(headers=h,body=json.dumps({'ok':True}))
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(viewport={'width':390,'height':844}); pg=ctx.new_page()
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('console',lambda m:errs.append('C:'+m.text)); pg.on('requestfailed',lambda r:errs.append('F:'+r.url[:60]+str(r.failure))); ctx.route('**/*',handle)
    rows.clear()
    pg.goto('file:///home/claude/tarot-log/index.html#u=https%3A%2F%2Fscript.google.com%2Fmacros%2Fs%2FX%2Fexec&t='+TOK)
    pg.wait_for_timeout(1500)
    print('log',log[:5]); print(pg.evaluate('JSON.stringify(store.cfg)'))
    pg.select_option('#spread','one'); pg.fill('#q','first')
    for i in range(3):
        pg.fill('#q','draw %d'%i); pg.click('#draw')
        pg.wait_for_timeout(300)   # draw saved before the deal finishes
        print('after click, server rows:',len(rows))
        pg.wait_for_function("!document.getElementById('draw').disabled",timeout=30000)
    pg.wait_for_timeout(4000)
    print('server rows after 3 draws:',len(rows),sorted(r['q'] for r in rows.values()))
    state['offline']=True
    pg.fill('#q','offline one'); pg.click('#draw'); pg.wait_for_function("!document.getElementById('draw').disabled",timeout=30000); pg.wait_for_timeout(1500)
    print('offline, server rows:',len(rows),'pending:',pg.evaluate('store.pending()'))
    state['offline']=False
    pg.click('#histBtn'); pg.wait_for_timeout(300); print(pg.inner_text('#hmode')); pg.click('#hs'); pg.wait_for_timeout(5000)
    print('after Sync now rows:',len(rows),'pending:',pg.evaluate('store.pending()'))
    pg.locator('.hi').first.locator('.hn').type('reflection typed',delay=30); pg.wait_for_timeout(3500)
    print('note on server:',[r['note'] for r in rows.values() if r['note']])
    print(errs[:6],log[:6]); print(pg.evaluate("store.api(null,{action:'del',id:'x'}).then(j=>JSON.stringify(j),e=>'ERR '+e.message)")); b.close()
