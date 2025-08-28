-- Étape 2 : Ajouter les nouvelles machines dans machines si elles n'existent pas
INSERT INTO machines (machine_name, os, ip_address)
SELECT DISTINCT 'truc', 'OS inconnu', r.ip_address
FROM recap_staging r
LEFT JOIN machines m ON r.ip_address = m.ip_address
WHERE m.ip_address IS NULL;

-- Étape 3 : Mise à jour machine_id dans recap_staging
UPDATE recap_staging r
JOIN machines m ON r.ip_address = m.ip_address
SET r.machine_id = m.machine_id;

-- Étape 4 : Transfert vers recap_temp et suppression des doublons
INSERT IGNORE INTO recap_temp
SELECT * FROM recap_staging;

-- Étape 5 : Insérer les données nettoyées dans recap
INSERT IGNORE INTO recap (machine_id, ip_address, timestamp, user_id, user_name, application_id, application_name, window_id, window_title, duration)
SELECT machine_id, ip_address, timestamp, user_id, user_name, application_id, application_name, window_id, window_title, duration
FROM recap_temp;

