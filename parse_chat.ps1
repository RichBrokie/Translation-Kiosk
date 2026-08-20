$files = Get-ChildItem -Path "C:\Work\chats\antigravity\brain" -Recurse -Filter "transcript.jsonl"
$target = $null
foreach ($f in $files) {
    if (Get-Content $f.FullName -Raw | Select-String "voice satellite") {
        $target = $f.FullName
        break
    }
}

if ($target) {
    $lines = Get-Content $target
    $count = 0
    foreach ($line in $lines) {
        $obj = $line | ConvertFrom-Json
        if ($obj.type -eq "USER_INPUT" -or $obj.type -eq "PLANNER_RESPONSE") {
            $text = $obj.content
            if ($text.Length -gt 500) { $text = $text.Substring(0, 500) + "..." }
            "[{0}] {1}" -f $obj.type, $text
            $count++
        }
        if ($count -gt 45) { break }
    }
}
