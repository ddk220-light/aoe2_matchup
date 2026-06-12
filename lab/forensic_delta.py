"""Empirical delta forensics: instrument the decode of the first N FrameSequences
of the raw capture. Trace the exact op patterns used to CREATE and UPDATE entities,
the navigation path from Root, and verify what fields entities carry in deltas.
"""
import struct, sys
from collections import Counter, defaultdict
import patch_decode as P
import cade_api_pb2 as pb

SCHEMA = P.SCHEMA
TYPE2NAME = P.TYPE2NAME
ENTITY_TYPES = {9, 10, 11, 12, 13, 14}

OPNAME = {1:"Pop",2:"AssignField",3:"PushField",4:"PushCreateAssignField",5:"ResetField",
 6:"AssignKey",7:"PushKey",8:"PushCreateAssignKey",9:"ResetKey",10:"Insert",
 11:"PushCreateInsert",12:"Remove",13:"Swap",14:"Resize"}

def read_seqs(path, maxn):
    data = open(path,"rb").read()
    pos=0; out=[]
    while pos+4<=len(data) and len(out)<maxn:
        n=struct.unpack_from("<I",data,pos)[0]; pos+=4
        if pos+n>len(data): break
        out.append(data[pos:pos+n]); pos+=n
    return out

class Tracer:
    """Decode a patch, tracking the model-type stack so we read value widths
    correctly and can log what path each op touches."""
    def __init__(self, data):
        self.r = P.Reader(data)
        self.n = len(data)
        # stack of (model_type, label). Root is type 0.
        self.stack = [(0, "Root")]
        self.events = []   # list of (op, detail)
        self.resyncs = 0

    def field_kind(self, mt, f):
        return SCHEMA.get(mt, {}).get(f)

    def run(self, log=False):
        r=self.r
        while r.p < self.n:
            op_pos=r.p
            op=r.u8()
            if not (1<=op<=14):
                self.resyncs+=1
                continue
            try:
                self.step(op, log)
            except Exception as e:
                r.p=op_pos+1
                self.resyncs+=1
        return self.events

    def cur_type(self):
        return self.stack[-1][0]

    def step(self, op, log):
        r=self.r
        mt=self.cur_type()
        if op==1:
            if len(self.stack)>1: self.stack.pop()
            if log: self.events.append(("Pop", self.path()))
        elif op==2:
            f=r.u8(); kind=self.field_kind(mt,f); v=P.read_value(r,kind)
            if log: self.events.append(("AssignField", f"{TYPE2NAME.get(mt,mt)}.{f}={v} ({kind})"))
        elif op==3:
            f=r.u8()
            child=self.field_child_type(mt,f)
            self.stack.append((child, f"{TYPE2NAME.get(mt,mt)}.{f}"))
            if log: self.events.append(("PushField", self.path()))
        elif op==4:
            f=r.u8(); cmt=r.u8()
            self.stack.append((cmt, f"{TYPE2NAME.get(mt,mt)}.{f}"))
            if log: self.events.append(("PushCreateAssignField", f"{TYPE2NAME.get(mt,mt)}.{f} -> create {TYPE2NAME.get(cmt,cmt)}"))
        elif op==5:
            f=r.u8()
            if log: self.events.append(("ResetField", f"{TYPE2NAME.get(mt,mt)}.{f}"))
        elif op==6:
            f=r.u8(); k=r.i32(); kind=self.field_kind(mt,f); v=self.read_map_value(kind)
            if log: self.events.append(("AssignKey", f"{TYPE2NAME.get(mt,mt)}.{f}[{k}]={v} ({kind})"))
        elif op==7:
            f=r.u8(); k=r.i32()
            child=self.field_child_type(mt,f)
            self.stack.append((child, f"{TYPE2NAME.get(mt,mt)}.{f}[{k}]"))
            if log: self.events.append(("PushKey", self.path()))
        elif op==8:
            f=r.u8(); cmt=r.u8(); k=r.i32()
            self.stack.append((cmt, f"{TYPE2NAME.get(mt,mt)}.{f}[{k}]"))
            self.events.append(("PushCreateAssignKey", f"{TYPE2NAME.get(mt,mt)}.{f}[{k}] -> create {TYPE2NAME.get(cmt,cmt)}({cmt})", k, cmt, mt, f))
        elif op==9:
            f=r.u8(); k=r.i32()
            self.events.append(("ResetKey", f"{TYPE2NAME.get(mt,mt)}.{f}[{k}]", k, mt, f))
        elif op==10:
            f=r.u8(); k=r.i32(); kind=self.field_kind(mt,f); v=self.read_map_value(kind)
            if log: self.events.append(("Insert", f"{TYPE2NAME.get(mt,mt)}.{f}[{k}]={v}"))
        elif op==11:
            f=r.u8(); cmt=r.u8(); k=r.i32()
            self.stack.append((cmt, f"{TYPE2NAME.get(mt,mt)}.{f}[{k}]"))
            if log: self.events.append(("PushCreateInsert", f"{TYPE2NAME.get(mt,mt)}.{f}[{k}] -> create {TYPE2NAME.get(cmt,cmt)}"))
        elif op==12:
            f=r.u8(); k=r.i32()
            if log: self.events.append(("Remove", f"{TYPE2NAME.get(mt,mt)}.{f}[{k}]"))
        elif op==13:
            f=r.u8(); r.i32(); r.i32()
        elif op==14:
            f=r.u8(); r.i32()

    def read_map_value(self, kind):
        # value element of a map/list. For BTreeMap<i32,Ref> kind=('map','Ref')
        if kind and kind[0]=="map":
            return P.read_value(self.r, P.classify(kind[1]))
        if kind and kind[0]=="list":
            return P.read_value(self.r, P.classify(kind[1]))
        return P.read_value(self.r, kind)

    def field_child_type(self, mt, f):
        """For PushField/PushKey, what model type is the child? Look at the
        field's declared type."""
        kind=self.field_kind(mt,f)
        if not kind: return -1
        if kind[0]=="ref": return -1   # a Ref into the document; type unknown here
        if kind[0]=="map":
            nm=kind[1].strip()
            return P.NAME2TYPE.get(nm,-1)
        if kind[0]=="list":
            nm=kind[1].strip()
            return P.NAME2TYPE.get(nm,-1)
        return -1

    def path(self):
        return " > ".join(l for _,l in self.stack)

def main():
    path=sys.argv[1] if len(sys.argv)>1 else "GAME_munq_vs_ddk220_incas_frames_raw.bin"
    maxn=int(sys.argv[2]) if len(sys.argv)>2 else 3000
    seqs=read_seqs(path,maxn)
    print(f"read {len(seqs)} FrameSequences from {path}")

    op8_creates=Counter()       # (parent_type, field, child_type)
    op8_under_field=Counter()
    create_keys_sample=[]
    resetkey=Counter()
    field_after_create=Counter()  # what fields get assigned right after an entity create
    patch_sizes=[]
    frames=0; big=0; small=0
    first_entity_trace=None
    entity_create_count=0
    sample_full_traces=[]

    for raw in seqs:
        sq=pb.FrameSequence(); sq.ParseFromString(raw)
        for fr in sq.frame:
            if not fr.patch: continue
            patch_sizes.append(len(fr.patch))
            frames+=1
            if len(fr.patch)>500_000:
                big+=1; continue
            small+=1
            t=Tracer(fr.patch)
            evs=t.run(log=(small<=40))   # full log for first 40 small patches
            # scan events for entity-create patterns
            for i,ev in enumerate(evs):
                if ev[0]=="PushCreateAssignKey":
                    _,desc,k,cmt,pmt,f=ev
                    op8_creates[(TYPE2NAME.get(pmt,pmt),f,TYPE2NAME.get(cmt,cmt))]+=1
                    if cmt in ENTITY_TYPES:
                        entity_create_count+=1
                        if len(create_keys_sample)<20:
                            create_keys_sample.append((pmt,f,cmt,k))
                        # look at subsequent AssignField ops before Pop
                        for ev2 in evs[i+1:i+12]:
                            if ev2[0]=="Pop": break
                            if ev2[0]=="AssignField":
                                field_after_create[ev2[1].split("=")[0]]+=1
                elif ev[0]=="ResetKey":
                    _,desc,k,pmt,f=ev
                    resetkey[(TYPE2NAME.get(pmt,pmt),f)]+=1
            if small<=8 and any(e[0]=="PushCreateAssignKey" for e in evs):
                sample_full_traces.append((small,len(fr.patch),evs))

    import statistics
    print(f"\nframes with patch: {frames}  (big>500KB: {big}, small: {small})")
    if patch_sizes:
        sp=sorted(patch_sizes)
        print(f"patch size: min={sp[0]} median={sp[len(sp)//2]} max={sp[-1]}")

    print(f"\n=== op8 PushCreateAssignKey targets (parent.field -> child_type): count ===")
    for (pt,f,ct),n in op8_creates.most_common(30):
        print(f"  {pt}.field{f} -> {ct}   x{n}")

    print(f"\nentity creates (child type in 9..14): {entity_create_count}")
    print("sample create (parent_type, field, child_type, key=entity_id):")
    for s in create_keys_sample:
        print("  ", s)

    print(f"\n=== fields assigned right after an entity create ===")
    for fname,n in field_after_create.most_common(30):
        print(f"  {fname}  x{n}")

    print(f"\n=== ResetKey targets (parent.field): count ===")
    for (pt,f),n in resetkey.most_common(15):
        print(f"  {pt}.field{f}  x{n}")

    print(f"\n=== FULL TRACE of first small patches containing an entity create ===")
    for (idx,sz,evs) in sample_full_traces[:3]:
        print(f"\n--- patch #{idx} ({sz} bytes), {len(evs)} ops ---")
        for ev in evs[:60]:
            print("   ", ev[0], ev[1])

if __name__=="__main__":
    main()
