$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptPath
$Date = Get-Date -Format "yyyy-MM-dd"
# Charger les chemins depuis config.env
$envFile = "config.env"

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^(.*?)=(.*)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2].Trim(), "Process")
        }
    }
    Write-Host "✅ Variables chargées depuis config.env"
} else {
    Write-Host "❌ Fichier config.env introuvable !" -ForegroundColor Red
    exit 1
}

# Récupérer les chemins
$base_import = [System.Environment]::GetEnvironmentVariable("BASE_IMPORT")
$DatabasePath = [System.Environment]::GetEnvironmentVariable("DATABASE_PATH")
$SqlCeCmdPath = [System.Environment]::GetEnvironmentVariable("SQLCE_PATH")
$log_dir = [System.Environment]::GetEnvironmentVariable("LOGS_DIR")
# Récupérer l'argument passé au script
$mode = $args[0]  # Premier argument passé


$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$hostname = $env:COMPUTERNAME
$export_file_temp = "$($base_import)\recap_$($hostname)_$($timestamp)_temp.csv"
$export_file = "$($base_import)\recap_$($hostname)_$($timestamp).csv"

Start-Transcript -Path "$log_dir\$($date)_script_log.txt" -Append
# Définir la passerelle cible
$gatewayTarget = "192.168.50.1"

# Trouver l'interface réseau associée à cette passerelle
$interfaceIndex = (Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Where-Object { $_.NextHop -eq $gatewayTarget } | Select-Object -ExpandProperty ifIndex)

# Récupérer l'adresse IP associée à cette interface
$ip_address = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceIndex -eq $interfaceIndex } | Select-Object -ExpandProperty IPAddress -First 1)

# Vérifier si l'IP a bien été récupérée
if (-not $ip_address) {
    $ip_address = "0.0.0.0"  # Valeur par défaut si aucune IP valide trouvée
}

Write-Host "Adresse IP détectée pour la passerelle $gatewayTarget : $ip_address"

# Définir la requête SQL selon l'argument
if ($mode -eq "all") {
    # Extraction complète
    $sql_query = "
    SELECT '|' + '|' + '$ip_address' AS ip_address, 
    CONVERT(NVARCHAR, Timestamp, 120) AS Timestamp, 
    UserID, 
    ""UserName"", 
    ApplicationID, 
    ""ApplicationName"", 
    WindowID, 
    REPLACE(WindowTitle, '|', '_') AS WindowTitle, 
    Duration 
    FROM Recap"
} else {
    # Calcul des 12 dernières heures
    $past12h = (Get-Date).AddHours(-12).ToString("yyyy-MM-dd HH:mm:ss")
    $sql_query = "
    SELECT '|' + '|' + '$ip_address' AS ip_address, 
    CONVERT(NVARCHAR, Timestamp, 120) AS Timestamp, 
    UserID, 
    ""UserName"", 
    ApplicationID, 
    ""ApplicationName"", 
    WindowID, 
    REPLACE(WindowTitle, '|', '_') AS WindowTitle, 
    Duration 
    FROM Recap 
    WHERE Timestamp >= '$past12h'"
}

# Exécuter la requête SQL avec SqlCeCmd40
& "$SqlCeCmdPath" -d "$DatabasePath" -q "$sql_query" -s "|" -o "$export_file_temp"

(Get-Content $export_file_temp | Where-Object {$_ -notmatch '^\(\d+ rows affected\)$' -and $_ -ne ""}) | Set-Content $export_file

# 🔹 Supprimer le fichier temporaire
Remove-Item $export_file_temp -Force

Write-Host "✅ Export terminé : $export_file"

Stop-Transcript
