# Parallax Sample Research Corpus

This directory contains the sample research papers used to demonstrate and benchmark the **Parallax AI-Powered Research Synthesis Engine**.

---

## 1. Dataset Overview & Licensing Scope

The full Parallax evaluation corpus consists of **34 representative academic research papers** spanning Deep Learning, Distributed Systems, Computer Networking, Compiler Optimization, and Information Visualization, plus one intentional culinary outlier paper (`paper34.pdf`).

To respect copyright and publisher distribution policies:
- **Redistributable Papers (Tracked in Git):** Only papers with explicit open-access redistribution-compatible licenses (Creative Commons) are included directly in this repository.
- **Non-Redistributed Papers (Local Reproduction):** Papers with restrictive distribution licenses are intentionally omitted from public version control. 

---

## 2. Complete 34-Paper Corpus Mapping

To replicate the complete [Empirical Evaluation](../../docs/EVALUATION.md) and all quantitative benchmarks, download the missing papers from their respective open-access publisher repositories (e.g., arXiv, ACM Digital Library, IEEE Xplore, USENIX) and place them into `data/sample_docs/` using the exact filename mapping below:

| ID | Title | Authors / Source | Redistribution Status |
|---|---|---|---|
| `paper1.pdf` | Attention Is All You Need | Vaswani et al., NeurIPS 2017 | Local only (arXiv:1706.03762) |
| `paper2.pdf` | Deep Residual Learning for Image Recognition | He et al., CVPR 2016 | Local only (arXiv:1512.03385) |
| `paper3.pdf` | ImageNet Classification with Deep Convolutional Neural Networks | Krizhevsky et al., NeurIPS 2012 | Local only (ACM DL) |
| `paper4.pdf` | Generative Adversarial Nets | Goodfellow et al., NeurIPS 2014 | Local only (arXiv:1406.2661) |
| `paper5.pdf` | Dropout: A Simple Way to Prevent Neural Networks from Overfitting | Srivastava et al., JMLR 2014 | **Included** (CC BY 4.0) |
| `paper6.pdf` | The Google File System | Ghemawat et al., SOSP 2003 | Local only (ACM DL) |
| `paper7.pdf` | MapReduce: Simplified Data Processing on Large Clusters | Dean & Ghemawat, OSDI 2004 | Local only (USENIX) |
| `paper8.pdf` | Bigtable: A Distributed Storage System for Structured Data | Chang et al., OSDI 2006 | Local only (USENIX) |
| `paper9.pdf` | In Search of an Understandable Consensus Algorithm | Ongaro & Ousterhout, ATC 2014 | Local only (USENIX) |
| `paper10.pdf` | Dynamo: Amazon's Highly Available Key-value Store | DeCandia et al., SOSP 2007 | Local only (ACM DL) |
| `paper11.pdf` | A Protocol for Packet Network Intercommunication | Cerf & Kahn, IEEE Trans. Comm. 1974 | Local only (IEEE) |
| `paper12.pdf` | Transport Layer Security (TLS) Security Guidelines version 2025-05 | NIST / IETF | Local only (IETF RFC) |
| `paper13.pdf` | Border Gateway Protocol - Implementation | Rekhter & Li, RFC 4271 | Local only (IETF RFC) |
| `paper14.pdf` | A Comparative Survey of TCP SYN Flooding DDoS Attacks Defense Methods | Al-Duwairi et al. | Local only (IEEE) |
| `paper15.pdf` | Tor: The Second-Generation Onion Router | Dingledine et al., USENIX Security 2004 | Local only (USENIX) |
| `paper16.pdf` | HAST-IDS: Learning Hierarchical Spatial-Temporal Features using Deep Neural Networks to Improve Intrusion Detection | Wang et al., IEEE Access 2018 | Local only (IEEE Access) |
| `paper17.pdf` | Efficient Global Register Allocation | Chaitin, SIGPLAN 1982 | Local only (ACM DL) |
| `paper18.pdf` | Register Allocation By Model Transformer Semantics | Poletto & Sarkar, TOPLAS 1999 | Local only (ACM DL) |
| `paper19.pdf` | Survey on Combinatorial Register Allocation and Instruction Scheduling | Castaneda Lozano & Schulte, ACM CSUR 2019 | Local only (ACM DL) |
| `paper20.pdf` | RL4ReAl: Reinforcement Learning for Register Allocation | Barany, CC 2024 | Local only (ACM DL) |
| `paper21.pdf` | VERILOCC: End-to-End Cross-Architecture Register Allocation via LLM | Chen et al., 2024 | Local only (arXiv) |
| `paper22.pdf` | Visualizing Time-Dependent Data Using Dynamic t-SNE | Rauber et al., EuroVis 2016 | Local only (EG/IEEE) |
| `paper23.pdf` | VOSviewer, a computer program for bibliometric mapping | van Eck & Waltman, Scientometrics 2010 | **Included** (CC BY-NC) |
| `paper24.pdf` | ForceAtlas2, a Continuous Graph Layout Algorithm for Handy Network Visualization Designed for the Gephi Software | Jacomy et al., PLOS ONE 2014 | **Included** (CC BY) |
| `paper25.pdf` | Constrained K-means Clustering with Background Knowledge | Wagstaff et al., ICML 2001 | Local only (ICML) |
| `paper26.pdf` | Vital Insight: Assisting Experts' Context-Driven Sensemaking of Multi-modal Personal Tracking Data Using Visualization and Human-in-the-Loop LLM | Zhao et al., IEEE TVCG 2024 | **Included** (CC BY-NC-SA 4.0) |
| `paper27.pdf` | Beyond Location: Hypertext Workspaces and Non-Linear Views | Shipman et al., Hypertext 1998 | Local only (ACM DL) |
| `paper28.pdf` | The Cost Structure of Sensemaking | Russell et al., CHI 1993 | Local only (ACM DL) |
| `paper29.pdf` | MPNet: Masked and Permuted Pre-training for Language Understanding | Song et al., NeurIPS 2020 | Local only (arXiv:2004.09297) |
| `paper30.pdf` | Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks | Reimers & Gurevych, EMNLP 2019 | Local only (arXiv:1908.10084) |
| `paper31.pdf` | UMAP: Uniform Manifold Approximation and Projection for Dimension Reduction | McInnes et al., 2018 | Local only (arXiv:1802.03426) |
| `paper32.pdf` | Continual Multi-View Clustering with Consistent Anchor Guidance | Li et al., IEEE TKDE 2024 | Local only (IEEE) |
| `paper33.pdf` | k-means++: The Advantages of Careful Seeding | Arthur & Vassilvitskii, SODA 2007 | Local only (SIAM) |
| `paper34.pdf` | Assessment of Indian cooking practices and cookwares on nutritional security: A review | Sharma et al., J. Ethnic Foods 2023 | **Included** (CC BY-NC 4.0) |

---

## 3. Reproduction Instructions

1. If you only wish to test the live Parallax UI and pipeline with sample data, the 5 included open-access papers provide an immediate functioning demo corpus.
2. If you wish to reproduce the exact 34-paper evaluation report (`python -u backend/evaluation/run_all_evaluations.py`), ensure all 34 PDFs are present in this directory with the filenames `paper1.pdf` through `paper34.pdf`.
