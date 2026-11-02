// Cost-independent rejection only. Positive routes still use the original A*.
// The caller supplies exactly the same directed entry predicate and goal set.
export function gridReachability(cols, rows, startIndex, goals, canEnterFrom) {
  const size=cols*rows,visited=new Uint8Array(size),queue=new Uint32Array(size);
  visited[startIndex]=1;queue[0]=startIndex;let head=0,tail=1;
  while(head<tail){
    const index=queue[head++];
    if(goals[index])return {reachable:true,expanded:head};
    const cx=index%cols,cy=Math.floor(index/cols);
    for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){
      if(dx===0&&dy===0)continue;
      const nx=cx+dx,ny=cy+dy;
      if(nx<0||nx>=cols||ny<0||ny>=rows)continue;
      const next=ny*cols+nx;
      if(visited[next]||!canEnterFrom(index,next))continue;
      if(dx!==0&&dy!==0&&(!canEnterFrom(index,cy*cols+nx)||!canEnterFrom(index,ny*cols+cx)))continue;
      visited[next]=1;queue[tail++]=next;
    }
  }
  return {reachable:false,expanded:head};
}
