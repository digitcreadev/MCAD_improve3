Article update package
======================

Files:
- MCAD_article_main_updated.tex : updated LaTeX article.
- MCAD_article_main_updated.pdf : compiled preview of the updated article.
- article_figures/              : regenerated figures used by the updated article.
- figure_scripts/               : Python scripts used to regenerate the figures.

How to regenerate the figures:
    cd /mnt/data/article_update/figure_scripts
    python generate_all_figures.py

How to compile the article:
    cd /mnt/data/article_update
    pdflatex MCAD_article_main_updated.tex
    pdflatex MCAD_article_main_updated.tex
