"""EXPLICITLY SYNTHETIC protocol fixture. Never used as a production fallback."""
import json
import sys
import time
mode = sys.argv[1] if len(sys.argv) > 1 else 'normal'
initialized = False
for line in sys.stdin:
    msg = json.loads(line)
    method = msg.get('method')
    if method == 'initialize':
        print(json.dumps({'id': msg['id'], 'result': {'userAgent': 'SYNTHETIC'}}), flush=True)
    elif method == 'initialized':
        initialized = True
    elif method == 'model/list' and initialized:
        if mode == 'timeout':
            time.sleep(10)
            continue
        if mode == 'error':
            print(json.dumps({'id': msg['id'], 'error': {'code': -1}}), flush=True)
            continue
        if mode == 'server-request':
            print(json.dumps({'id': 99, 'method': 'exec/approve', 'params': {}}), flush=True)
            continue
        if mode == 'garbage':
            print('not json', flush=True)
            continue
        if mode == 'exit':
            break
        page2 = 'cursor' in msg['params']
        model = {'model': 'synthetic-model-2' if page2 else 'synthetic-model-1',
                 'displayName': 'SYNTHETIC ONLY', 'defaultReasoningEffort': 'medium',
                 'supportedReasoningEfforts': [{'reasoningEffort': 'medium', 'description': 'SYNTHETIC'}]}
        if mode == 'unknown-effort':
            model['supportedReasoningEfforts'].append({'reasoningEffort': 'future-native', 'description': 'Unclassified synthetic value'})
        if mode == 'duplicate': model['model'] = 'synthetic-model-1'
        result = {'data': [model], 'nextCursor': None if page2 else 'next'}
        if mode == 'repeat-cursor': result['nextCursor'] = 'next'
        if mode == 'missing-cursor': del result['nextCursor']
        print(json.dumps({'id': msg['id'], 'result': result}), flush=True)
    else:
        print(json.dumps({'id': msg.get('id'), 'error': {'code': -999}}), flush=True)
