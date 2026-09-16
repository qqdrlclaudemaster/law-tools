# -*- coding: utf-8 -*-
"""kanji.json + strokes.json + (선택) tr/out*.jsonl 한국어 뜻 → 저장소의 kanji.html, kanji-strokes.js, sw.js 생성"""
import json, glob, os, hashlib, sys
B=os.path.dirname(os.path.abspath(__file__)); R='/home/user/law-tools'
data=json.load(open(f'{B}/kanji.json',encoding='utf-8'))
# 한국어 뜻 병합: 키 = 단어|읽기
ko={}
items=json.load(open(f'{B}/../tr/all.json',encoding='utf-8')) if os.path.exists(f'{B}/../tr/all.json') else []
byid={it['id']:it for it in items}
for f in sorted(glob.glob(f'{B}/../tr/out*.jsonl')):
    for line in open(f,encoding='utf-8'):
        line=line.strip()
        if not line: continue
        try: o=json.loads(line)
        except Exception: continue
        it=byid.get(o.get('id'))
        if it and o.get('ko'): ko[it['w']+'|'+it['y']]=o['ko'].strip()
n=0; tot=0
for e in data:
    for kind in ('on','kun'):
        for r in e[kind]:
            for i,x in enumerate(r['ex']):
                flag=x[4] if len(x)>4 else ''
                g=ko.get(x[0]+'|'+x[1],'')
                tot+=1; n+= bool(g)
                r['ex'][i]=[x[0],x[1],x[2],x[3],flag,g]
print(f'ko glosses merged: {n}/{tot}')
js=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
t=open(f'{B}/kanji.template.html',encoding='utf-8').read()
assert t.count('__DATA__')==1
html=t.replace('__DATA__',js)
open(f'{R}/kanji.html','w',encoding='utf-8').write(html)
strokes=open(f'{B}/strokes.json',encoding='utf-8').read()
open(f'{R}/kanji-strokes.js','w',encoding='utf-8').write('/* KanjiVG (CC BY-SA 3.0, Ulrich Apel) stroke paths for the 2,136 常用漢字. viewBox 0 0 109 109 */\nwindow.KANJI_STROKES='+strokes+';\n')
ver=hashlib.sha1((html+strokes).encode('utf-8')).hexdigest()[:10]
sw=open(f'{R}/sw.js',encoding='utf-8').read()
import re
sw=re.sub(r"const VERSION = '[^']*';", f"const VERSION = '{ver}';", sw)
open(f'{R}/sw.js','w',encoding='utf-8').write(sw)
print('sizes', os.path.getsize(f'{R}/kanji.html'), os.path.getsize(f'{R}/kanji-strokes.js'), 'sw version', ver)
