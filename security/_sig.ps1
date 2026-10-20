
param($InFile, $OutFile)
$paths = Get-Content -Raw -Encoding UTF8 $InFile | ConvertFrom-Json
$out = @{}
foreach ($p in $paths) {
    try {
        $s = Get-AuthenticodeSignature -LiteralPath $p -ErrorAction Stop
        $subj = ''
        if ($s.SignerCertificate) { $subj = [string]$s.SignerCertificate.Subject }
        $out[$p] = @{ status = [string]$s.Status; subject = $subj }
    } catch {
        $out[$p] = @{ status = 'Error'; subject = '' }
    }
}
$out | ConvertTo-Json -Compress | Out-File -Encoding UTF8 $OutFile
