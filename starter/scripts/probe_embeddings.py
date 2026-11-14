"""Smoke test for LocalSentenceEmbedder: dim, norm, VN cosine sanity."""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from src.embeddings import LocalSentenceEmbedder


def main() -> None:
    emb = LocalSentenceEmbedder()
    print(f"model={emb.model_name}")
    print(f"dimensions={emb.dimensions}")

    docs = [
        "Tuổi nghỉ hưu của người lao động trong điều kiện bình thường.",
        "Lộ trình điều chỉnh tuổi nghỉ hưu theo quy định của Chính phủ.",
        "Thời gian nghỉ phép hằng năm của người lao động.",
        "Công thức nấu phở bò Hà Nội truyền thống.",
    ]
    vecs = np.array(emb.embed_documents(docs))
    norms = np.linalg.norm(vecs, axis=1)
    print(f"shape={vecs.shape}  norms(min={norms.min():.4f} max={norms.max():.4f})")

    query = "Khi nào người lao động được nghỉ hưu?"
    q = np.array(emb.embed_query(query))
    sims = vecs @ q  # cosine (vì đã L2-normalize)
    print(f"\nQuery: {query!r}")
    for text, s in zip(docs, sims):
        print(f"  sim={s:+.4f}  {text}")


if __name__ == "__main__":
    main()
