"""Pull full AiOrder records out of a raw .frames.bin stream."""
import struct,sys,json,collections
sys.path.insert(0,r"D:\AI\aoe2_matchup\aoe2x\grpc")
from google.protobuf import runtime_version as _rtv
_rtv.ValidateProtobufRuntimeVersion=lambda *a,**k:None
import cade_api_pb2 as pb

def orders(path):
    out=[]; kinds=collections.Counter()
    with open(path,'rb') as fh:
        while True:
            hdr=fh.read(4)
            if len(hdr)<4: break
            (ln,)=struct.unpack("<I",hdr)
            buf=fh.read(ln)
            if len(buf)<ln: break
            sq=pb.FrameSequence(); sq.ParseFromString(buf)
            for fr in sq.frame:
                for cmd in fr.command:
                    which=cmd.WhichOneof('command') if cmd.DESCRIPTOR.oneofs else None
                    for f,_ in cmd.ListFields(): kinds[f.name]+=1
                    if cmd.HasField('aiOrder'):
                        o=cmd.aiOrder
                        out.append({'t':round(fr.time,3),'playerId':o.playerId,'issuer':o.issuer,
                            'recipient':o.recipient,'orderType':o.orderType,
                            'priority':o.orderPriority,'targetOwner':o.targetOwner,
                            'range':round(o.range,2),'immediate':o.immediate,'inFront':o.inFront,
                            'unitIds':list(o.unitIds),
                            'loc':[round(o.location.x,2),round(o.location.y,2)] if o.HasField('location') else None})
    return out,kinds

if __name__=='__main__':
    o,k=orders(sys.argv[1])
    print('command kinds seen:',dict(k))
    print(f'{len(o)} AiOrder records\n')
    for r in o[:14]: print(' ',json.dumps(r))
