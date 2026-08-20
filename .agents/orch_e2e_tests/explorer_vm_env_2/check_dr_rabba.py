import os
p = '/mnt/models/Dr Rabba Abduk'
if os.path.exists(p):
    for f in os.listdir(p):
        fp = os.path.join(p, f)
        print(f, os.path.getsize(fp))
