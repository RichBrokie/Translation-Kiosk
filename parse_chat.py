import json
import glob
files = glob.glob('C:/Work/chats/antigravity/brain/*/.system_generated/logs/transcript.jsonl')
target_file = None
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
        if 'voice satellite' in content:
            target_file = f
            break
if target_file:
    with open(target_file, 'r', encoding='utf-8') as file:
        count = 0
        for line in file:
            data = json.loads(line)
            if data['type'] in ('USER_INPUT', 'PLANNER_RESPONSE'):
                print(f"[{data['type']}] {data['content'][:500]}...")
                count += 1
            if count > 45:
                break
