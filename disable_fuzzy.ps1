$headers = @{ "Content-Type" = "application/json" }
$body = '{ "enabled": false }'
$indexes = @(
    "moniteur_docs",
    "eurlex_docs",
    "conseil_etat_arrets100",
    "constcourtjudgments2025",
    "annexes_juridique"
)

foreach ($index in $indexes) {
    $url = "http://127.0.0.1:7700/indexes/$index/settings/typo-tolerance"
    Invoke-WebRequest -Uri $url -Method PATCH -Headers $headers -Body $body
    Write-Host "Fuzzy search désactivée pour $index"
}
