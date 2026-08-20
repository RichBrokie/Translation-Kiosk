param(
    [string]$LocalPath,
    [string]$RemotePath
)
$content = [System.IO.File]::ReadAllText($LocalPath, [System.Text.Encoding]::UTF8)
$bytes = [System.Text.Encoding]::UTF8.GetBytes($content)
$b64 = [System.Convert]::ToBase64String($bytes)
# Write base64 string to remote temp file and decode
$cmd = "echo '$b64' | base64 -d > '$RemotePath'"
& 'c:\Work\plink.exe' -batch -ssh -pw 'Metropolis0!' -hostkey 'SHA256:d7wY3MAFRw/nRhQKl2nCcnYosDplIemd9i+KDtw0bVM' ubuntu@100.109.43.41 $cmd
