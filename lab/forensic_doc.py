"""Document-aware delta tracer. KEY FIX: World.entities is BTreeMap<i32,Ref>, so
the field's declared element type is 'Ref' (type unknown from schema alone). The
engine resolves the real model type from the DOCUMENT: each created model records
its own type, keyed by (parent_path, field, key). On PushKey/PushField we restore
that recorded type so subsequent AssignField reads use the correct scalar widths.

We model the document as: a dict keyed by a stable path-tuple -> model_type.
For World.entities[id] the key is ('World.entities', id). This lets us decode the
Entity's own fields (master_id, owner, x, y, hp) correctly.
"""
import struct, sys
from collections import Counter
import patch_decode as P
import cade_api_pb2 as pb

SCHEMA=P.SCHEMA; TYPE2NAME=P.TYPE2NAME; NAME2TYPE=P.NAME2TYPE
ENTITY_TYPES={9,10,11,12,13,14}
# Entity stable field indices
F_ID,F_MASTER,F_OWNER,F_X,F_Y,F_Z,F_HP,F_STATE=0,1,2,3,4,5,12,8

class Doc:
    """Holds model_type per object path. Path = tuple of segments; segment is
    (field, key) where key is None for plain field push."""
    def __init__(self):
        self.types={}        # path_tuple -> model_type
        self.entities={}     # entity_key -> {field: value} reconstructed
    def set_type(self, path, mt):
        self.types[path]=mt
    def get_type(self, path):
        return self.types.get(path, -1)

class Tracer:
    def __init__(self, data, doc):
        self.r=P.Reader(data); self.n=len(data); self.doc=doc
        # stack entries: (model_type, path_tuple)
        self.stack=[(0, ())]
        self.resyncs=0
    def mt(self): return self.stack[-1][0]
    def path(self): return self.stack[-1][1]
    def kind(self,mt,f): return SCHEMA.get(mt,{}).get(f)

    def child_decl_type(self,mt,f):
        """declared element/child model type from schema (may be -1 if Ref)."""
        k=self.kind(mt,f)
        if not k: return -1
        if k[0]=="ref": return -1
        if k[0] in ("map","list"):
            return NAME2TYPE.get(k[1].strip(),-1)
        return -1

    def run(self):
        r=self.r
        while r.p<self.n:
            op_pos=r.p; op=r.u8()
            if not (1<=op<=14):
                self.resyncs+=1; continue
            try: self.step(op)
            except Exception:
                r.p=op_pos+1; self.resyncs+=1

    def resolve_child_type(self, mt, f, key):
        """type for PushField(key=None)/PushKey(key): prefer document record,
        fall back to schema declared type."""
        newpath=self.path()+((f,key),)
        t=self.doc.get_type(newpath)
        if t!=-1: return t, newpath
        t=self.child_decl_type(mt,f)
        return t, newpath

    def step(self, op):
        r=self.r; mt=self.mt(); path=self.path()
        if op==1:
            if len(self.stack)>1: self.stack.pop()
        elif op==2:
            f=r.u8(); v=P.read_value(r,self.kind(mt,f)); self.record_field(path,mt,f,v)
        elif op==3:
            f=r.u8(); t,np=self.resolve_child_type(mt,f,None); self.stack.append((t,np))
        elif op==4:
            f=r.u8(); cmt=r.u8(); np=path+((f,None),); self.doc.set_type(np,cmt); self.stack.append((cmt,np))
        elif op==5:
            f=r.u8()
        elif op==6:
            f=r.u8(); k=r.i32(); v=self.read_kv(mt,f); self.record_key(path,mt,f,k,v)
        elif op==7:
            f=r.u8(); k=r.i32(); t,np=self.resolve_child_type(mt,f,k); self.stack.append((t,np))
        elif op==8:
            f=r.u8(); cmt=r.u8(); k=r.i32(); np=path+((f,k),); self.doc.set_type(np,cmt)
            self.stack.append((cmt,np))
            if cmt in ENTITY_TYPES and path==((0,None),):  # under World (Root.0)
                self.doc.entities.setdefault(k,{})["__type__"]=cmt
        elif op==9:
            f=r.u8(); k=r.i32()
            if path==((0,None),) and f==1: self.doc.entities.pop(k,None)
        elif op==10:
            f=r.u8(); k=r.i32(); v=self.read_kv(mt,f)
        elif op==11:
            f=r.u8(); cmt=r.u8(); k=r.i32(); np=path+((f,k),); self.doc.set_type(np,cmt); self.stack.append((cmt,np))
        elif op==12:
            f=r.u8(); k=r.i32()
        elif op==13:
            f=r.u8(); r.i32(); r.i32()
        elif op==14:
            f=r.u8(); r.i32()

    def read_kv(self,mt,f):
        k=self.kind(mt,f)
        if k and k[0] in ("map","list"): return P.read_value(self.r,P.classify(k[1]))
        return P.read_value(self.r,k)

    def record_field(self,path,mt,f,v):
        # entity field assignment: path == (World.entities[id],)
        if len(path)==1 and path[0][0]==1 and path[0][1] is not None:
            # only if parent push was under World? we approximate: path seg (1, id)
            pass
        # entity = pushed under (0,None)>(1,id): path == ((0,None),(1,id))
        if len(path)==2 and path[0]==(0,None) and path[1][0]==1:
            eid=path[1][1]
            self.doc.entities.setdefault(eid,{})[f]=v
    def record_key(self,path,mt,f,k,v):
        pass

def main():
    path=sys.argv[1] if len(sys.argv)>1 else "GAME_munq_vs_ddk220_incas_frames_raw.bin"
    maxn=int(sys.argv[2]) if len(sys.argv)>2 else 3000
    data=open(path,"rb").read()
    pos=0; seqs=[]
    while pos+4<=len(data) and len(seqs)<maxn:
        n=struct.unpack_from("<I",data,pos)[0]; pos+=4
        if pos+n>len(data): break
        seqs.append(data[pos:pos+n]); pos+=n
    print(f"{len(seqs)} seqs")
    doc=Doc()
    small=0; big=0; total_resync=0
    for raw in seqs:
        sq=pb.FrameSequence(); sq.ParseFromString(raw)
        for fr in sq.frame:
            if not fr.patch: continue
            if len(fr.patch)>500_000: big+=1; continue
            small+=1
            t=Tracer(fr.patch,doc); t.run(); total_resync+=t.resyncs
    ents=doc.entities
    real={k:e for k,e in ents.items() if isinstance(e,dict) and (F_MASTER in e or "__type__" in e)}
    print(f"small patches: {small}, big skipped: {big}, total resyncs: {total_resync}")
    print(f"entities tracked: {len(ents)}, with master_id or type: {len(real)}")
    withmaster={k:e for k,e in ents.items() if F_MASTER in e}
    print(f"entities with master_id (F1): {len(withmaster)}")
    # how many have x,y,hp
    havexy=sum(1 for e in ents.values() if F_X in e and F_Y in e)
    havehp=sum(1 for e in ents.values() if F_HP in e)
    haveowner=sum(1 for e in ents.values() if F_OWNER in e)
    print(f"have x&y: {havexy}, have hp: {havehp}, have owner: {haveowner}")
    by=Counter((e.get(F_OWNER),e.get(F_MASTER)) for e in withmaster.values())
    print("\ntop (owner,master_id) counts:")
    for (o,m),n in by.most_common(20):
        print(f"  owner={o} master_id={m} count={n}")
    print("\nsample entities (id,type,master,owner,x,y,hp):")
    for k,e in list(withmaster.items())[:15]:
        print(f"  id={k} mtype={e.get('__type__')} master={e.get(F_MASTER)} owner={e.get(F_OWNER)} x={e.get(F_X)} y={e.get(F_Y)} hp={e.get(F_HP)}")

if __name__=="__main__":
    main()
