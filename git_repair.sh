# 0) Valider l'état propre
cd /home/pipo/dev/brainops/brainops
git add -A && git commit -m "chore: prepare repo root move" || true

cd /home/pipo/dev/brainops

# 1) Sauvegarder le working tree actuel pour éviter les collisions
mv brainops brainops_src

# 2) Déplacer le dépôt (le .git) au niveau parent
mv brainops_src/.git .

# 3) Reconstituer le working tree à la racine
git reset --hard

# À ce stade, les fichiers suivis sont directement dans /path/brainops
# 4) Créer le sous-dossier 'brainops' (le package) et y déplacer le contenu suivi
mkdir brainops
# déplacer tous les fichiers suivis (y compris dotfiles, hors .git) dans le sous-dossier
git mv * .[^.]* brainops 2>/dev/null || true

# 5) Commit du déplacement
git commit -m "refactor(repo): move project under brainops/ subfolder"

# 6) Rapatrier d'éventuels fichiers non suivis depuis la sauvegarde
rsync -a --exclude='.git' brainops_src/ brainops/
rm -rf brainops_src
