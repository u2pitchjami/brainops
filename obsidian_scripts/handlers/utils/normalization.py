import unicodedata
import os

def normalize_full_path(path):
    """ Nettoie un chemin de fichier (slashs, accents, espaces, etc.) """
    path = unicodedata.normalize("NFC", path)
    path = path.strip()
    return os.path.normpath(path)
