import glob
for p in glob.glob('/home/ubuntu/translation_kiosk/*.py'):
    with open(p, 'r') as f:
        lines = [l for l in f.read().splitlines() if l.strip() != 'EOF']
    with open(p, 'w') as f:
        f.write('\n'.join(lines) + '\n')
