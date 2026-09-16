# -*- coding: utf-8 -*-
"""Build the 常用漢字 dataset for the learning app.
Sources (all downloaded into ../src or ../pk):
  - mimneko/kanji-data 常用漢字表本表.json, 教育漢字.csv (CC0)  -> readings, examples, old forms, grade
  - kyujipy kyujitai_simplified.cson (MIT)                       -> shinjitai->kyujitai fallback
  - rycont/hanja-grade-dataset hanja.csv (한국어문회 급수 한자)    -> Korean 훈/음, 급수
  - myungcheol/hanja hanjaDic.js                                 -> Korean 훈/음 fallback
  - jamdict-data (JMdict/KANJIDIC2, CC BY-SA)                    -> example readings, English glosses, ko readings fallback
  - davidluzgouveia/kanji-data kanji-jouyou.json (MIT)           -> JLPT, strokes, freq, English meanings
  - pykakasi                                                     -> reading fallback for phrases not in JMdict
"""
import json, csv, re, ast, sqlite3, unicodedata, collections, sys, os
B=os.path.dirname(os.path.abspath(__file__)); R=os.path.join(B,'..'); S=os.path.join(R,'src'); P=os.path.join(R,'pk')
NFC=lambda s: unicodedata.normalize('NFC',s)

jy=json.load(open(f'{S}/kanji-data/常用漢字表本表.json',encoding='utf-8'))
grade={}
for row in csv.DictReader(open(f'{S}/kanji-data/教育漢字.csv',encoding='utf-8-sig')):
    grade[NFC(row['漢字'])]=int(row['学年'])
ky=dict((NFC(a),NFC(b)) for a,b in re.findall(r'\["(.)",\s*"(.)"\]',open(f'{P}/kyujipy/data/kyujitai_simplified.cson',encoding='utf-8').read()))
ry={}
for row in csv.DictReader(open(f'{S}/hanja-grade-dataset/hanja.csv',encoding='utf-8')):
    ry.setdefault(NFC(row['hanja']),[]).append(row)
mc=json.loads(open(f'{S}/hanja/hanjaDic.js',encoding='utf-8').read().split('=',1)[1].strip().rstrip(';'))
mc={NFC(k):v for k,v in mc.items()}
dlg=json.load(open(f'{S}/dlg-kanji-data/kanji-jouyou.json',encoding='utf-8'))
dlg={NFC(k):v for k,v in dlg.items()}
db=sqlite3.connect(f'{P}/jamdict_data-1.5/jamdict_data/jamdict.db')
import pykakasi; kks=pykakasi.kakasi()

ALT={'𠮟':'叱','剝':'剥'}   # display/lookup alternates for glyphs missing in some fonts/datasets
MANUAL_KR={'𠮟':'叱'}
KOKUJI=set('匂込峠働塀畑枠栃腺')          # 일본에서 만든 한자(国字) — 한국 훈음이 없거나 사전마다 다름
MANUAL_HUN={'惧':[['두려워할','구']],'闘':[['싸울','투']]}   # 데이터셋에 훈이 비어 있어 보충한 항목(검증 필요)

def kanjidic_ko(ch):
    r=db.execute("select ID from character where literal=?",(ch,)).fetchone()
    if not r: return []
    return [v for (v,) in db.execute("select value from reading r join rm_group g on r.gid=g.ID where g.cid=? and r_type='korean_h'",(r[0],))]

def parse_ry(rows):
    out=[]
    for row in rows:
        try: v=ast.literal_eval(row['meaning'])
        except Exception: continue
        for pair in v:
            if len(pair)!=2: continue
            hun,eum=pair
            hun=[h.strip() for h in hun if h.strip()]; eum=[e.strip() for e in eum if e.strip()]
            if not eum: continue
            out.append(['/'.join(hun) if hun else '', eum[0]])
    return out

def korean_info(s, olds):
    cands=[]
    if s in MANUAL_KR: cands.append(MANUAL_KR[s])
    cands+=olds
    if s in ky: cands.append(ky[s])
    cands.append(s)
    if s in ALT: cands.append(ALT[s])
    seen=[]; [seen.append(c) for c in cands if c not in seen]
    for c in seen:
        if c in ry:
            return c, parse_ry(ry[c]), ry[c][0]['level'], 'ry'
    for c in seen:
        if c in mc:
            return c, [[x['def'],x['kor']] for x in mc[c]], '', 'mc'
    for c in seen:
        ko=kanjidic_ko(c)
        if ko: return c, [['',k] for k in ko], '', 'kd'
    return s, [], '', ''

# Korean sino reading for a word (only when every char has a single reading)
CHO="ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
def sep(ch):
    u=ord(ch)-0xAC00; return u//588, (u%588)//28, u%28
def bld(a,b,c): return chr(0xAC00+a*588+b*28+c)
def dooeum(syls):
    # word-initial 두음법칙 + (모음/ㄴ 받침 뒤) 렬·률→열·율
    out=[]
    for i,s in enumerate(syls):
        if not ('가'<=s<='힣'): out.append(s); continue
        a,b,c=sep(s)
        if i==0:
            head=bld(a,b,0)
            if head in ('녀','뇨','뉴','니'): a=11
            elif head in ('랴','려','례','료','류','리'): a=11
            elif head in ('라','래','로','뢰','루','르'): a=2
        else:
            prev=out[-1]
            if s in ('렬','률') and '가'<=prev<='힣' and sep(prev)[2] in (0,4): a=11
        out.append(bld(a,b,c))
    return ''.join(out)

kr_reading_of={}  # japanese char -> (korean form, [eum list])
def sino(word):
    syl=[]
    prev=None
    for ch in word:
        if ch=='々' and prev: ch=prev
        if ch not in kr_reading_of: return ''
        _,eums=kr_reading_of[ch]
        if len(set(eums))!=1: return ''
        if len(eums[0])!=1 or not ('가'<=eums[0]<='힣'): return ''
        syl.append(eums[0]); prev=ch
    return dooeum(syl)

def hira(s):
    return ''.join(chr(ord(c)-0x60) if '\u30a1'<=c<='\u30f6' else c for c in s)

def jm_lookup(w, pref=''):
    """(reading, gloss) for word w from JMdict; prefer a kana reading containing `pref` (hiragana stem)."""
    rows=db.execute("select idseq from Kanji where text=?",(w,)).fetchall()
    cands=[]
    for (idseq,) in rows:
        kana=[r[0] for r in db.execute("select text from Kana where idseq=? order by ID",(idseq,))]
        pri=db.execute("select count(*) from Kana k join KNP p on p.kid=k.ID where k.idseq=?",(idseq,)).fetchone()[0]
        sid=db.execute("select ID from Sense where idseq=? order by ID limit 1",(idseq,)).fetchone()
        gl=[r[0] for r in db.execute("select text from SenseGloss where sid=? and lang='eng' limit 3",(sid[0],))] if sid else []
        for j,kn in enumerate(kana):
            match=1 if (pref and pref in kn) else 0
            cands.append((match, pri, -j, kn, gl))
    if not cands: return None
    cands.sort(reverse=True)
    m,pri,j,kn,gl=cands[0]
    return kn, '; '.join(gl)

def kakasi(w):
    w2=''.join(ALT.get(c,c) for c in w)
    return ''.join(x['hira'] for x in kks.convert(w2))

KANA=r'[\u3040-\u30ff\u30fc]'
def stem_of(r, after):
    """kanji portion of kun reading r, given the kana that immediately follows the kanji in the word."""
    for base in (r, r[:-1]):
        for n in range(len(base)-1,0,-1):
            if after.startswith(base[-n:]): return base[:-n]
    return None

def stem_reading(core, k, r):
    # kun example: target kanji read with its kun stem, remaining kanji via kakasi
    if core.count(k)!=1: return None, None
    before,after=core.split(k)
    m=re.match(KANA+'*',after); kana_after=m.group(0)
    if not kana_after:
        stem=r if not after else (r if re.match(r'[^\u3040-\u30ff]',after) else None)
    else:
        stem=stem_of(r,kana_after)
    if stem is None:
        ROWS=['あいうえお','かきくけこ','がぎぐげご','さしすせそ','ざじずぜぞ','たちつてと','だぢづでど','なにぬねの','はひふへほ','ばびぶべぼ','ぱぴぷぺぽ','まみむめも','らりるれろ']
        row=lambda c: next((x for x in ROWS if c in x),None)
        if kana_after and r and row(r[-1]) and row(r[-1])==row(kana_after[0]) and r[-1] in 'うくぐすつぬぶむる': stem=r[:-1]   # conjugated verb (書く→書き)
        elif kana_after and r.endswith('い') and kana_after[0] in 'くさげかき': stem=r[:-1]                                  # adjective stem (軽い→軽さ)
        else: stem=r
    other=re.search(r'[\u4e00-\u9fff\U00020000-\U0002FFFF々]', before+after)
    if other:
        return kakasi(before)+stem+kakasi(after), 'p'
    return before+stem+after, ''

def example(x, k='', r='', is_on=False):
    disp=x
    core=re.sub(r'〔.*?〕','',x).strip()
    core=re.sub(r'（.*?）','',core).strip()
    core=core.replace('……','')
    if not core or '○' in core:
        return [disp,'','','']
    exp=''
    for ch in core: exp+= (exp[-1] if ch=='々' and exp else ch)
    pref=hira(r) if is_on else (stem_of(r, re.match(KANA+'*', exp.split(k,1)[1]).group(0)) if k in exp else None)
    if pref is None: pref=r
    hit=jm_lookup(core, pref)
    if hit and hit[0]:
        y,g=hit; flag=''
    else:
        g=''
        y,flag=(None,None) if is_on else stem_reading(exp,k,r)
        if y is None: y=kakasi(core); flag='p'
    h=sino(core) if (is_on and flag=='' and re.fullmatch(r'[一-鿿\U00020000-\U0002FFFF々]+',core)) else ''
    return [disp,y,g,h+('' if not flag else ''),flag] if flag else [disp,y,g,h]

# first pass: korean info for every kanji (needed for sino())
entries=[]
stats=collections.Counter()
for i,e in enumerate(jy,1):
    s=NFC(e['漢字']['通用字体'])
    oldraw=e['漢字']['康熙字典体'] or ''
    olds=[NFC(o) for o in re.split(r'[）（]',oldraw) if o.strip()]
    olds=[o for o in olds if o!=s]
    krf,hun,lv,src=korean_info(s,olds)
    stats['kr:'+src]+=1
    kr_reading_of[s]=(krf,[h[1] for h in hun])
    entries.append((i,e,s,olds,krf,hun,lv,src))

out=[]
for i,e,s,olds,krf,hun,lv,src in entries:
    d=dlg.get(s) or dlg.get(ALT.get(s,''),{})
    g=grade.get(s,7)
    def readings(kind):
        res=[]
        for r in e['音訓']:
            rd=r['読み']
            is_on=bool(re.search(r'[゠-ヿ]',rd))
            if (kind=='on')!=is_on: continue
            item={'r':rd,'ex':[example(x,s,rd,is_on) for x in r['例']]}
            if r['備考']['異字同訓']: item['same']=r['備考']['異字同訓']
            if r['備考']['留意事項']: item['note']=r['備考']['留意事項']
            res.append(item)
        return res
    ent={'n':i,'k':s,'kr':krf,'hun':hun,'lv':lv,'on':readings('on'),'kun':readings('kun'),
         'g':g,'jl':d.get('jlpt_new') or 0,'st':d.get('strokes') or 0,'fq':d.get('freq') or 0,
         'en':', '.join((d.get('meanings') or [])[:4])}
    if s in ALT: ent['alt']=ALT[s]
    if not ent['hun'] and s in MANUAL_HUN: ent['hun']=MANUAL_HUN[s]; ent['krsrc']='manual'
    if s in KOKUJI: ent['kokuji']=1
    if olds: ent['old']=olds
    if src and src!='ry': ent['krsrc']=src
    notes={}
    if e['備考']['付表']: notes['jukujikun']=e['備考']['付表']
    if e['備考']['都道府県']: notes['pref']=e['備考']['都道府県']
    if e['備考']['参照']: notes['ref']=e['備考']['参照']
    if notes: ent['notes']=notes
    out.append(ent)
    for kind in ('on','kun'):
        for r in ent[kind]:
            for x in r['ex']:
                stats['ex']+=1
                if len(x)==5: stats['ex_kakasi']+=1
                if x[2]: stats['ex_gloss']+=1
                if x[3]: stats['ex_sino']+=1
    stats['krdiff']+= (krf!=s)
    if not hun: stats['no_hun']+=1; print('NO HUN',s)

json.dump(out,open(f'{B}/kanji.json','w',encoding='utf-8'),ensure_ascii=False,separators=(',',':'))
print(len(out),'entries', dict(stats))
print('size',os.path.getsize(f'{B}/kanji.json'))
