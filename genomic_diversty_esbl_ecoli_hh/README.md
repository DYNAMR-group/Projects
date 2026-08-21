# Genomic Diversity of ESBL-Producing *Escherichia coli* in Households (HH)

Whole-genome sequencing (WGS) pipeline for characterising the genomic diversity, resistome, and phylogenetic relationships of extended-spectrum β-lactamase (ESBL)-producing *E. coli* isolates collected from household settings.

This repository organises the analysis into ordered, modular pipeline folders — each one representing a discrete stage from raw sequencing reads through to a final phylogeny. Every folder is self-contained (scripts/config + inputs/outputs) so stages can be re-run independently.

---

## Pipeline Overview

```
Raw reads → QC → Trimming → Assembly → Assembly QC → Species/Typing
          → AMR & Virulence → Plasmids → Pan-genome/Core alignment
          → Recombination filtering → Phylogenetics → Visualisation
```

## 
