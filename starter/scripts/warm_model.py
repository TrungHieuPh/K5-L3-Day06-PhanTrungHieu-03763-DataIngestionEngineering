"""Pre-download the embedding model into ~/.cache/huggingface/ so later runs are fast."""
import sys
import time
sys.stdout.reconfigure(encoding="utf-8")

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
print(f"Loading {MODEL} ...", flush=True)
t0 = time.time()

from sentence_transformers import SentenceTransformer
m = SentenceTransformer(MODEL)
elapsed = time.time() - t0

sample = ["Giờ làm việc ban đêm được tính từ 22 giờ đến 06 giờ sáng ngày hôm sau."]
v = m.encode(sample)
print(f"Loaded in {elapsed:.1f}s | embedding dim = {v.shape[1]} | sample[0..5] = {v[0][:5]}")
