import sys
sys.path.append("/home/ubuntu/translation_kiosk")
from audio_pipeline import TextStitcher

s = TextStitcher(overlap_ratio=0.5)
c1, t1, d1, r1 = s.process_window("Here we have ancient egypt")
print("Window 1:", "committed=", repr(c1), "tail=", repr(t1), "display=", repr(d1))

c2, t2, d2, r2 = s.process_window("ancient egyptian artifacts from the tomb")
print("Window 2:", "committed=", repr(c2), "tail=", repr(t2), "display=", repr(d2))
print("\n--- Test No Match ---")
s2 = TextStitcher(overlap_ratio=0.5)
s2.process_window("The quick brown fox jumps")
c_nm, t_nm, d_nm, r_nm = s2.process_window("over a lazy dog")
print("Window 1 committed='The quick', tail='brown fox jumps'")
print("Window 2 after 'over a lazy dog':")
print("committed=", repr(c_nm), "tail=", repr(t_nm), "display=", repr(d_nm))
