import assert from 'node:assert/strict';
import test from 'node:test';
import {LatestRequest, requestJson} from '../apps/website/static/js/shared/api.js';
import {WorkerSession} from '../apps/website/static/js/battle/worker-session.js';
import {createPageData} from '../apps/website/static/js/shared/page-data.js';

test('selection changes abort the old request and invalidate its response', () => {
    const requests = new LatestRequest();
    const first = requests.begin();
    const second = requests.begin();
    assert.equal(first.signal.aborted, true);
    assert.equal(first.isCurrent(), false);
    assert.equal(second.isCurrent(), true);
    requests.cancel();
    assert.equal(second.isCurrent(), false);
});

test('cancelled workers cannot publish queued events into a restarted battle', () => {
    const workers = [];
    const session = new WorkerSession(() => {
        const worker = {terminate(){this.terminated=true;}, postMessage(data){this.input=data;}};
        workers.push(worker);
        return worker;
    });
    const received=[];
    session.start({seed:1}, message=>received.push(message));
    const oldHandler=workers[0].onmessage;
    session.start({seed:2}, message=>received.push(message));
    oldHandler({data:{type:'complete',runId:workers[0].input.runId}});
    assert.equal(received.length,0);
    const current=workers[1];
    current.onmessage({data:{type:'snapshots',runId:current.input.runId,snapshots:[]}});
    assert.equal(received.length,1);
    current.onerror({message:'test failure'});
    assert.equal(received[1].type,'error');
    assert.equal(current.terminated,true);
    current.onmessage({data:{type:'complete',runId:current.input.runId}});
    assert.equal(received.length,2);
});

test('page data rejects a late old response even when the transport ignores abort', async () => {
    const original=globalThis.fetch;
    const pending=[];
    globalThis.fetch=()=>new Promise(resolve=>pending.push(resolve));
    try {
        const data=createPageData();
        const first=data.select('/first');
        const second=data.select('/second');
        pending[1]({ok:true,json:async()=>({unit:'new'})});
        assert.deepEqual(await second,{unit:'new'});
        pending[0]({ok:true,json:async()=>({unit:'old'})});
        assert.equal(await first,null);
    } finally {globalThis.fetch=original;}
});

test('HTTP failures are actionable and bootstrap data needs no network', async () => {
    const original=globalThis.fetch;
    globalThis.fetch=async()=>({ok:false,status:503,json:async()=>({error:'Unavailable',detail:'Mechanics missing'})});
    try {
        await assert.rejects(requestJson('/bad'),/Mechanics missing/);
        assert.deepEqual(await createPageData().select('/bootstrap',{name:'Spanish'}),{name:'Spanish'});
    } finally {globalThis.fetch=original;}
});
