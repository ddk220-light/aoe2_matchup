"""Faithful flat-document + id-stack decoder, mirroring uncage-model's Patcher
exactly. Validates the document/ref model against the REAL snapshot bytes and
early deltas. Prints an op trace and the recovered entities.
"""
import re, struct, sys
from collections import Counter

# ---- schema parse (reuse logic, but keep value_type Map/List/Value + is_model) ----
SCALARS = {"u8":("<B",1),"i8":("<b",1),"u16":("<H",2),"i16":("<h",2),
           "u32":("<I",4),"i32":("<i",4),"u64":("<Q",8),"i64":("<q",8),
           "f32":("<f",4),"f64":("<d",8),"bool":("<?",1),
           "u128":("16s",16),"i128":("16s",16)}

def parse_schema(path):
    txt = open(path).read()
    structs = {}
    name_to_type = {}
    for m in re.finditer(r"#\[uncage\(type = (\d+)\)\]\s*pub struct (\w+)\s*\{(.*?)\n\}", txt, re.S):
        ty, name, body = int(m.group(1)), m.group(2), m.group(3)
        name_to_type[name] = ty
        fields, parent = {}, None
        for fm in re.finditer(r"#\[uncage\(([^\]]*)\)\]\s*pub (\w+):\s*([^,\n]+)", body):
            attrs, fname, ftype = fm.group(1), fm.group(2), fm.group(3).strip().rstrip(",")
            if "extends" in attrs:
                parent = ftype; continue
            idxm = re.search(r"index = (\d+)", attrs)
            if idxm:
                fields[int(idxm.group(1))] = ftype
        structs[name] = {"type": ty, "fields": fields, "extends": parent, "name": name}
    return structs, name_to_type

STRUCTS, NAME2TYPE = parse_schema("reference_model.rs")
TYPE2STRUCT = {s["type"]: s for s in STRUCTS.values()}

def flat_fields(ty, seen=None):
    seen = seen or set()
    if ty not in TYPE2STRUCT or ty in seen: return {}
    seen.add(ty)
    s = TYPE2STRUCT[ty]
    merged = {}
    if s["extends"] and s["extends"] in NAME2TYPE:
        merged.update(flat_fields(NAME2TYPE[s["extends"]], seen))
    merged.update(s["fields"])
    return merged

# value-type / field-type classification mirroring the proc-macro
def field_info(ty):
    """returns (value_type, is_model, scalar_rust_or_None)
    value_type in {'value','map','list'}."""
    ty = ty.strip()
    # Map
    m = re.match(r"(?:Model)?(?:BTreeMap|HashMap)<\s*([^,]+),\s*(.+)>$", ty)
    if m:
        val = m.group(2).strip()
        is_model = ty.startswith("Model") or val == "Ref" or val.startswith("ModelRef") or (val not in SCALARS and val != "String")
        scal = val if val in SCALARS else ("String" if val=="String" else None)
        return ("map", is_model, scal)
    # Vec
    m = re.match(r"(?:Model)?Vec<(.+)>$", ty)
    if m:
        val = m.group(1).strip()
        is_model = ty.startswith("ModelVec") or val=="Ref" or val.startswith("ModelRef") or (val not in SCALARS and val!="String")
        scal = val if val in SCALARS else ("String" if val=="String" else None)
        return ("list", is_model, scal)
    # Ref / ModelRef / bare model name
    if ty == "Ref" or ty.startswith("ModelRef"):
        return ("value", True, None)
    if ty in SCALARS:
        return ("value", False, ty)
    if ty == "String":
        return ("value", False, "String")
    # bare model name -> model ref
    if ty in NAME2TYPE:
        return ("value", True, None)
    return ("value", False, None)  # unknown -> needs guess

class Reader:
    def __init__(s,d): s.d=d; s.p=0
    def u8(s): v=s.d[s.p]; s.p+=1; return v
    def i32(s): v=struct.unpack_from("<i",s.d,s.p)[0]; s.p+=4; return v
    def scalar(s,rust): fmt,n=SCALARS[rust]; v=struct.unpack_from(fmt,s.d,s.p)[0]; s.p+=n; return v
    def string(s): n=s.i32(); v=s.d[s.p:s.p+n].decode("utf-8","replace"); s.p+=n; return v

# guess for unknown-typed fields (model drift)
_STRUCT_ARGS = {1:0,3:1,4:2,5:1,7:5,8:6,9:5,11:6,12:5,13:9,14:5}
def _op_ok(d,p,depth=2):
    if p>=len(d): return False
    op=d[p]
    if not (1<=op<=14): return False
    if depth<=1: return True
    if op in _STRUCT_ARGS: return _op_ok(d,p+1+_STRUCT_ARGS[op],depth-1)
    return True
def guess_value(r):
    for w in (1,2,4,8):
        if _op_ok(r.d,r.p+w,2):
            v=r.d[r.p:r.p+w]; r.p+=w; return v.hex()
    r.p+=4; return None

def read_scalar_value(r, scal):
    if scal is None: return guess_value(r)
    if scal=="String": return r.string()
    return r.scalar(scal)

class Doc:
    """flat document: id -> model dict. model = {'__type__':t, fields...}.
    Map/List ref fields store CHILD IDS (ints), not nested dicts."""
    def __init__(s):
        s.models = {}
        s.next = 0
        s.root = s.register(0)  # Root type 0 at id 0
    def register(s, mtype):
        i = s.next; s.next += 1
        s.models[i] = {"__type__": mtype}
        return i

def decode(data, doc=None, trace=False, trace_limit=60):
    r = Reader(data)
    if doc is None: doc = Doc()
    stack = [doc.root]   # stack of document ids
    tr = 0
    nops = 0
    while r.p < len(data):
        op_pos = r.p
        op = r.u8()
        if not (1<=op<=14):
            continue
        try:
            top_id = stack[-1]
            top = doc.models[top_id]
            tty = top["__type__"]
            fields = flat_fields(tty)
            def finfo(f):
                t = fields.get(f)
                return field_info(t) if t else ("value", False, None)
            if op==1:
                if len(stack)>1: stack.pop()
            elif op==2:   # AssignField
                f=r.u8(); vt,ism,scal=finfo(f)
                if ism: top[f]=read_scalar_value(r, None)  # shouldn't happen; ref field assigned scalar
                else: top[f]=read_scalar_value(r, scal)
            elif op==3:   # PushField (existing model ref)
                f=r.u8(); cid=top.get(f)
                if isinstance(cid,int): stack.append(cid)
                else: stack.append(top_id)  # missing -> stay (lenient)
            elif op==4:   # PushCreateAndAssignField
                f=r.u8(); mt=r.u8(); cid=doc.register(mt); top[f]=cid; stack.append(cid)
            elif op==5:   # ResetField
                f=r.u8(); top.pop(f,None)
            elif op==6:   # AssignKey
                f=r.u8(); k=r.i32(); vt,ism,scal=finfo(f)
                top.setdefault(f,{})[k]=read_scalar_value(r, scal)
            elif op==7:   # PushKey (existing)
                f=r.u8(); k=r.i32(); cid=top.get(f,{}).get(k)
                if isinstance(cid,int): stack.append(cid)
                else: stack.append(top_id)
            elif op==8:   # PushCreateAndAssignKey  <-- ENTITY CREATE
                f=r.u8(); mt=r.u8(); k=r.i32(); cid=doc.register(mt)
                top.setdefault(f,{})[k]=cid; stack.append(cid)
            elif op==9:   # ResetKey
                f=r.u8(); k=r.i32(); m=top.get(f)
                if isinstance(m,dict): m.pop(k,None)
            elif op==10:  # Insert
                f=r.u8(); k=r.i32(); vt,ism,scal=finfo(f); top.setdefault(f,{})[k]=read_scalar_value(r,scal)
            elif op==11:  # PushCreateAndInsert
                f=r.u8(); mt=r.u8(); k=r.i32(); cid=doc.register(mt); top.setdefault(f,{})[k]=cid; stack.append(cid)
            elif op==12:  # Remove
                f=r.u8(); k=r.i32(); m=top.get(f)
                if isinstance(m,dict): m.pop(k,None)
            elif op==13:  # Swap
                f=r.u8(); r.i32(); r.i32()
            elif op==14:  # Resize
                f=r.u8(); r.i32()
            nops+=1
            if trace and nops<=trace_limit:
                sname = TYPE2STRUCT.get(tty,{}).get("name","?")
                print(f"  [{op_pos}] op{op} on top_id={top_id}({sname}) stack_depth={len(stack)}")
            # report first creation of World (type 1) and first entities-field touch
            if op==4 and top.get(f)==len(doc.models)-1 and mt==1 and trace:
                print(f"  >>> World created at pos {op_pos}, id={doc.models[doc.root].get(0)}")
        except Exception as e:
            if tr==0 and trace:
                sname = TYPE2STRUCT.get(top["__type__"],{}).get("name","?")
                print(f"  !!! FIRST DESYNC at pos {op_pos} op{op} on {sname}(id={top_id}): {e}")
            r.p = op_pos+1; tr+=1; continue
    return doc, nops, tr, r.p

if __name__=="__main__":
    path = sys.argv[1] if len(sys.argv)>1 else "first_patch_seg2.bin"
    data = open(path,"rb").read()
    print(f"decoding {path} ({len(data)} bytes)")
    doc,nops,tr,pos = decode(data, trace=True)
    print(f"ops={nops} resyncs={tr} consumed {pos}/{len(data)} ({100*pos/len(data):.1f}%)")
    # resolve World.entities: root.field0 -> world id; world.field1 -> {key: entity_id}
    root = doc.models[doc.root]
    wid = root.get(0)
    print(f"Root fields: {sorted(k for k in root if isinstance(k,int))}  world_id={wid}")
    if isinstance(wid,int):
        world = doc.models[wid]
        print(f"World fields: {sorted(k for k in world if isinstance(k,int))}")
        ents = world.get(1, {})
        print(f"entities map size: {len(ents)}")
        cnt = Counter()
        sample=[]
        for k,eid in ents.items():
            if not isinstance(eid,int): continue
            e=doc.models.get(eid,{})
            master=e.get(1); owner=e.get(2); x=e.get(3); y=e.get(4); hp=e.get(12)
            cnt[(owner,master)]+=1
            if len(sample)<10: sample.append((k,eid,e.get("__type__"),master,owner,x,y,hp))
        print("sample (key,docid,mtype,master,owner,x,y,hp):")
        for s in sample: print("   ",s)
        print("by (owner,master) top:")
        for (o,m),n in cnt.most_common(20): print(f"   owner={o} master={m} count={n}")
    print(f"total document models: {len(doc.models)}")
