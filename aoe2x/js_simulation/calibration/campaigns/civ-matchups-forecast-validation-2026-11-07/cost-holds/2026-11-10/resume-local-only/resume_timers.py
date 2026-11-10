"""Resume the same stopped Node process without charging suspension to JS timers.
Operational libuv/Node event-loop clock bookkeeping only; no battle state access.
Offsets are derived from this exact Node 24.19.0 executable's disassembly.
"""
import os,struct,time,pathlib,json,signal,hashlib
NODE=pathlib.Path('/opt/codex/runtimes/codex-primary-runtime/dependencies/node/bin/node')
DEFAULT_LOOP_PTR=0x6b0da88
RUN_TIMERS=0x882910

def recover(pid):
 p=pathlib.Path('/proc')/str(pid)
 assert p.joinpath('exe').resolve()==NODE
 assert '\nState:\tT' in p.joinpath('status').read_text()
 assert all('\nState:\tT' in t.joinpath('status').read_text() for t in p.joinpath('task').iterdir())
 assert NODE.read_bytes()[16:18]==b'\x02\x00', 'exact non-PIE binary required'
 fd=os.open(str(p/'mem'),os.O_RDWR)
 def u64(a):return struct.unpack('<Q',os.pread(fd,8,a))[0]
 def u32(a):return struct.unpack('<I',os.pread(fd,4,a))[0]
 loop=u64(DEFAULT_LOOP_PTR);assert loop==0x6b0daa0
 cached=u64(loop+0x220);root=u64(loop+0x208);count=u32(loop+0x210);assert 1<=count<=8
 timers=[];seen=set()
 def walk(ptr):
  if not ptr:return
  assert ptr not in seen;seen.add(ptr);h=ptr-0x68
  assert u32(h+0x10)==13 and u64(h+8)==loop
  assert u64(h+0x60)==RUN_TIMERS
  env=h-0xe8;iso=u64(env+0xd8);assert u64(iso+0x1240)==loop
  deadline=u64(h+0x80);assert deadline>=cached
  timers.append((h,env,deadline,u64(env+0x618)))
  walk(u64(ptr));walk(u64(ptr+8))
 walk(root);assert len(timers)==count
 assert len({env for h,env,d,b in timers})==1
 current=time.monotonic_ns()//1000000;delta=current-cached;assert delta>0
 changes={loop+0x220:(cached,current)}
 for h,env,d,base in timers:
  assert base<=cached
  changes[h+0x80]=(d,d+delta);changes[env+0x618]=(base,base+delta)
 record={'pid':pid,'suspendedLoopMonotonicMs':cached,'resumedLoopMonotonicMs':current,'excludedSuspensionAndUnobservedIdleMs':delta,'timerCount':count,'preservedTimers':[{'deadlineRemainingMs':d-cached,'timerAddress':hex(h),'callback':'node::Environment::RunTimers','logicalClockBefore':cached-base,'logicalClockAfter':current-(base+delta)} for h,e,d,base in timers],'memoryChanges':[{'address':hex(a),'before':x,'after':y} for a,(x,y) in changes.items()],'battleStateAccessedOrChanged':False,'physicsOrSeedSourceFilesChanged':False,'newSimulationExecutionStartedForRecovery':False}
 # All threads remain stopped for this complete verified transaction.
 for a,(x,y) in changes.items():assert u64(a)==x
 for a,(x,y) in changes.items():assert os.pwrite(fd,struct.pack('<Q',y),a)==8
 for a,(x,y) in changes.items():assert u64(a)==y
 os.close(fd)
 os.kill(pid,signal.SIGCONT)
 record['resumedAtUnixNs']=time.time_ns()
 return record
