import unicodedata

def normalize_path(path):
    """ Normalise les caractères spéciaux pour garantir la correspondance """
    return unicodedata.normalize("NFC", path)
