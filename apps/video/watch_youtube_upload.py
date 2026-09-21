"""Follow one in-flight upload to processed completion without starting uploads.

Run once beside an existing uploader. Writes its own receipt, so it does not race
the uploader's state file. Preserves visibility and other owner edits in Studio.
"""
import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlencode

from upload_youtube import API, require, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--credentials',type=Path,default=Path('data/local/youtube'))
    parser.add_argument('--timeout-hours',type=float,default=8)
    args = parser.parse_args()
    deadline = time.time()+args.timeout_hours*3600
    api = None
    while time.time()<deadline:
        state = json.loads(args.state.read_text())
        receipt = {k:state.get(k) for k in ('state','videoId','videoUrl','percent','uploadedBytes','totalBytes','thumbnailSet')}
        receipt['checkedAt'] = time.time()
        # Wait for the uploader to finish its thumbnail mutation, then make only
        # read-only requests. Never issue a second videos.insert or alter privacy.
        if state.get('videoId') and state.get('thumbnailSet'):
            api = api or API(args.credentials)
            query = urlencode({'part':'status,processingDetails,contentDetails','id':state['videoId']})
            try:
                code,_,body = api.request('https://www.googleapis.com/youtube/v3/videos?'+query)
                item = require(code,body)['items'][0]
                processing = item.get('processingDetails',{}).get('processingStatus')
                receipt.update(processingStatus=processing,privacyStatus=item['status']['privacyStatus'],
                               duration=item.get('contentDetails',{}).get('duration'))
                receipt['state'] = 'COMPLETE' if processing=='succeeded' else 'PROCESSING'
                if processing in ('failed','terminated'): receipt['state']='NEEDS_ATTENTION'
            except Exception as error:
                receipt.update(state='STATUS_CHECK_RETRY',errorType=type(error).__name__)
        elif state.get('state')=='UPLOADING' and time.time()-state['updatedAt']>600:
            receipt['state']='STALLED_CHECK_UPLOADER'
        write(args.receipt,receipt)
        if receipt['state'] in ('COMPLETE','NEEDS_ATTENTION','STALLED_CHECK_UPLOADER'):
            print(json.dumps(receipt),flush=True)
            return
        time.sleep(60)
    write(args.receipt,dict(state='MONITOR_TIMEOUT',checkedAt=time.time()))


if __name__=='__main__':
    main()
