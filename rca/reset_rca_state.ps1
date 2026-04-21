[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [string]$CorrelationConfig = "log_correlation_engine/config/config.yml",
    [string]$RcaConfig = "log_rca_engine/config/config.yml",
    [ValidateSet("direct-stream", "compatibility", "all")]
    [string]$Profile = "direct-stream",
    [switch]$Rebuild,
    [Alias("RestartPm")]
    [switch]$RestartPm2,
    [switch]$RunTests,
    [switch]$SkipClean,
    [switch]$SkipRedis,
    [switch]$SkipElasticsearch,
    [switch]$SkipLocalFiles,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param(
        [string]$State,
        [string]$Message
    )

    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Write-Host ("[{0}] [{1}] {2}" -f $timestamp, $State.ToUpperInvariant(), $Message)
}

function As-Array {
    param(
        [Parameter(ValueFromPipeline = $true)]
        $Value
    )

    if ($null -eq $Value) {
        return ,([object[]]@())
    }

    return ,([object[]]@($Value))
}

function Add-PhaseResult {
    param(
        [string]$Name,
        [string]$Status,
        [string]$Message
    )

    $script:PhaseResults.Add([pscustomobject]@{
        Name    = $Name
        Status  = $Status
        Message = $Message
    }) | Out-Null
}

function Invoke-Phase {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    try {
        & $Action
        Add-PhaseResult -Name $Name -Status "ok" -Message ""
    } catch {
        $message = $_.Exception.Message
        Write-Step "error" ("phase '{0}' failed: {1}" -f $Name, $message)
        Add-PhaseResult -Name $Name -Status "failed" -Message $message
    }
}

function Get-AbsolutePath {
    param(
        [string]$BasePath,
        [string]$RawPath
    )

    if ([string]::IsNullOrWhiteSpace($RawPath)) {
        return ""
    }

    $trimmed = $RawPath.Trim().Trim("'`"")
    if ([System.IO.Path]::IsPathRooted($trimmed)) {
        return [System.IO.Path]::GetFullPath($trimmed)
    }

    $baseDirectory = Split-Path -Parent (Resolve-Path $BasePath)
    return [System.IO.Path]::GetFullPath((Join-Path $baseDirectory $trimmed))
}

function Get-YamlSectionValue {
    param(
        [string]$Path,
        [string]$Section,
        [string]$Key
    )

    $lines = Get-Content -Path $Path
    $insideSection = $false
    $sectionPattern = "^\s*" + [Regex]::Escape($Section) + ":\s*$"
    $keyPattern = "^\s{2}" + [Regex]::Escape($Key) + ":\s*(.+?)\s*$"

    foreach ($line in $lines) {
        if ($line -match '^\S') {
            $insideSection = $false
        }

        if ($line -match $sectionPattern) {
            $insideSection = $true
            continue
        }

        if (-not $insideSection) {
            continue
        }

        if ($line -match '^\S') {
            break
        }

        if ($line -match $keyPattern) {
            return $Matches[1].Trim().Trim("'`"")
        }
    }

    return ""
}

function Get-YamlSectionList {
    param(
        [string]$Path,
        [string]$Section,
        [string]$Key
    )

    $lines = Get-Content -Path $Path
    $insideSection = $false
    $insideList = $false
    $sectionPattern = "^\s*" + [Regex]::Escape($Section) + ":\s*$"
    $listStartPattern = "^\s{2}" + [Regex]::Escape($Key) + ":\s*$"
    $values = New-Object System.Collections.Generic.List[string]

    foreach ($line in $lines) {
        if ($line -match '^\S') {
            $insideSection = $false
            $insideList = $false
        }

        if ($line -match $sectionPattern) {
            $insideSection = $true
            $insideList = $false
            continue
        }

        if (-not $insideSection) {
            continue
        }

        if ($insideList) {
            if ($line -match '^\s{4}-\s*(.+?)\s*$') {
                $values.Add($Matches[1].Trim().Trim("'`""))
                continue
            }

            if ($line -notmatch '^\s{4,}') {
                break
            }
        }

        if ($line -match $listStartPattern) {
            $insideList = $true
            continue
        }
    }

    return @($values)
}

function Get-BasicAuthHeader {
    param(
        [string]$Username,
        [string]$Password
    )

    if ([string]::IsNullOrWhiteSpace($Username) -and [string]::IsNullOrWhiteSpace($Password)) {
        return @{}
    }

    $pair = "{0}:{1}" -f $Username, $Password
    $encoded = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
    return @{
        Authorization = "Basic $encoded"
    }
}

function Invoke-ElasticDelete {
    param(
        [string]$Address,
        [string]$IndexPattern,
        [hashtable]$Headers
    )

    $trimmedAddress = $Address.Trim().TrimEnd('/')
    $uri = "{0}/{1}" -f $trimmedAddress, $IndexPattern

    try {
        $response = Invoke-WebRequest -Method Delete -Uri $uri -Headers $Headers -UseBasicParsing
        Write-Step "info" ("deleted elasticsearch index pattern {0} from {1} (status {2})" -f $IndexPattern, $trimmedAddress, [int]$response.StatusCode)
    } catch {
        $statusCode = $null
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $statusCode = [int]$_.Exception.Response.StatusCode
        }

        if ($statusCode -eq 404) {
            Write-Step "info" ("elasticsearch index pattern {0} not present on {1}" -f $IndexPattern, $trimmedAddress)
            return
        }

        throw
    }
}

function Read-RedisLine {
    param(
        [System.IO.Stream]$Stream
    )

    $bytes = New-Object System.Collections.Generic.List[byte]
    while ($true) {
        $first = $Stream.ReadByte()
        if ($first -lt 0) {
            throw "unexpected end of stream while reading redis reply"
        }

        if ($first -eq 13) {
            $second = $Stream.ReadByte()
            if ($second -ne 10) {
                throw "invalid redis reply line terminator"
            }
            break
        }

        $bytes.Add([byte]$first)
    }

    return [Text.Encoding]::UTF8.GetString($bytes.ToArray())
}

function Read-RedisBytes {
    param(
        [System.IO.Stream]$Stream,
        [int]$Length
    )

    $buffer = New-Object byte[] $Length
    $offset = 0
    while ($offset -lt $Length) {
        $read = $Stream.Read($buffer, $offset, $Length - $offset)
        if ($read -le 0) {
            throw "unexpected end of stream while reading redis bulk reply"
        }
        $offset += $read
    }

    $cr = $Stream.ReadByte()
    $lf = $Stream.ReadByte()
    if ($cr -ne 13 -or $lf -ne 10) {
        throw "invalid redis bulk reply terminator"
    }

    return [Text.Encoding]::UTF8.GetString($buffer)
}

function Read-RedisReply {
    param(
        [System.IO.Stream]$Stream
    )

    $prefixByte = $Stream.ReadByte()
    if ($prefixByte -lt 0) {
        throw "unexpected end of stream while reading redis response prefix"
    }

    $prefix = [char]$prefixByte
    switch ($prefix) {
        '+' { return (Read-RedisLine -Stream $Stream) }
        '-' {
            $message = Read-RedisLine -Stream $Stream
            throw "redis error: $message"
        }
        ':' {
            $value = Read-RedisLine -Stream $Stream
            return [long]::Parse($value, [Globalization.CultureInfo]::InvariantCulture)
        }
        '$' {
            $length = [int](Read-RedisLine -Stream $Stream)
            if ($length -lt 0) {
                return $null
            }
            return (Read-RedisBytes -Stream $Stream -Length $length)
        }
        '*' {
            $count = [int](Read-RedisLine -Stream $Stream)
            if ($count -lt 0) {
                return $null
            }

            $items = New-Object object[] $count
            for ($index = 0; $index -lt $count; $index++) {
                $items[$index] = Read-RedisReply -Stream $Stream
            }
            return $items
        }
        default {
            throw "unsupported redis reply prefix '$prefix'"
        }
    }
}

function Write-RedisCommand {
    param(
        [System.IO.Stream]$Stream,
        [string[]]$Args
    )

    $builder = New-Object Text.StringBuilder
    [void]$builder.Append('*').Append($Args.Length).Append("`r`n")
    foreach ($arg in $Args) {
        $value = if ($null -eq $arg) { "" } else { [string]$arg }
        $bytes = [Text.Encoding]::UTF8.GetBytes($value)
        [void]$builder.Append('$').Append($bytes.Length).Append("`r`n")
        [void]$builder.Append($value).Append("`r`n")
    }

    $payload = [Text.Encoding]::UTF8.GetBytes($builder.ToString())
    $Stream.Write($payload, 0, $payload.Length)
    $Stream.Flush()
}

function Invoke-RedisCommand {
    param(
        [System.IO.Stream]$Stream,
        [string[]]$Args
    )

    Write-RedisCommand -Stream $Stream -Args $Args
    return Read-RedisReply -Stream $Stream
}

function Test-RedisNoPasswordAuthError {
    param(
        [string]$Message
    )

    $normalized = if ($null -eq $Message) { "" } else { $Message.ToLowerInvariant() }
    return ($normalized.Contains("err auth") -and $normalized.Contains("without any password configured"))
}

function Open-RedisSession {
    param(
        [string]$Address,
        [string]$Username,
        [string]$Password,
        [int]$Database
    )

    if ($Address -notmatch '^(?<host>.+):(?<port>\d+)$') {
        throw "unsupported redis address format '$Address'"
    }

    $host = $Matches['host']
    $port = [int]$Matches['port']

    $client = [System.Net.Sockets.TcpClient]::new()
    $client.SendTimeout = 5000
    $client.ReceiveTimeout = 5000
    $client.Connect($host, $port)

    $stream = $client.GetStream()

    if (-not [string]::IsNullOrWhiteSpace($Password)) {
        try {
            if (-not [string]::IsNullOrWhiteSpace($Username)) {
                [void](Invoke-RedisCommand -Stream $stream -Args @("AUTH", $Username, $Password))
            } else {
                [void](Invoke-RedisCommand -Stream $stream -Args @("AUTH", $Password))
            }
        } catch {
            if (Test-RedisNoPasswordAuthError -Message $_.Exception.Message) {
                Write-Step "warn" "redis server has no password configured; continuing without AUTH"
            } else {
                throw
            }
        }
    }

    [void](Invoke-RedisCommand -Stream $stream -Args @("SELECT", [string]$Database))

    return @{
        Client = $client
        Stream = $stream
    }
}

function Close-RedisSession {
    param(
        [hashtable]$Session
    )

    if ($null -eq $Session) {
        return
    }

    if ($Session.Stream) {
        $Session.Stream.Dispose()
    }
    if ($Session.Client) {
        $Session.Client.Close()
        $Session.Client.Dispose()
    }
}

function Get-RedisKeys {
    param(
        [System.IO.Stream]$Stream,
        [string]$Pattern
    )

    $cursor = "0"
    $keys = New-Object System.Collections.Generic.HashSet[string]
    do {
        $reply = Invoke-RedisCommand -Stream $Stream -Args @("SCAN", $cursor, "MATCH", $Pattern, "COUNT", "500")
        if ($reply.Length -lt 2) {
            throw "unexpected redis SCAN response"
        }

        $cursor = [string]$reply[0]
        $batch = $reply[1]
        if ($batch) {
            foreach ($key in $batch) {
                if (-not [string]::IsNullOrWhiteSpace($key)) {
                    [void]$keys.Add([string]$key)
                }
            }
        }
    } while ($cursor -ne "0")

    return @($keys.ToArray() | Sort-Object)
}

function Remove-RedisKeys {
    param(
        [System.IO.Stream]$Stream,
        [string[]]$Keys
    )

    $keyArray = @($Keys)
    if ($keyArray.Count -eq 0) {
        return 0
    }

    $deleted = 0
    $batchSize = 200
    for ($offset = 0; $offset -lt $keyArray.Count; $offset += $batchSize) {
        $count = [Math]::Min($batchSize, $keyArray.Count - $offset)
        $chunk = $keyArray[$offset..($offset + $count - 1)]
        $command = @("DEL") + $chunk
        $reply = Invoke-RedisCommand -Stream $Stream -Args $command
        $deleted += [int]$reply
    }
    return $deleted
}

function Remove-LocalPath {
    param(
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Step "info" ("local path not present: {0}" -f $Path)
        return
    }

    $item = Get-Item -LiteralPath $Path
    if ($item.PSIsContainer) {
        Remove-Item -LiteralPath $Path -Recurse -Force
        Write-Step "info" ("deleted directory {0}" -f $Path)
    } else {
        Remove-Item -LiteralPath $Path -Force
        Write-Step "info" ("deleted file {0}" -f $Path)
    }
}

function Resolve-Executable {
    param(
        [string]$Name,
        [string[]]$Candidates = @()
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    foreach ($candidate in $Candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw "executable '$Name' not found"
}

function Invoke-ExternalCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = "",
        [switch]$IgnoreFailure
    )

    $resolvedWorkingDirectory = $WorkingDirectory
    if ([string]::IsNullOrWhiteSpace($resolvedWorkingDirectory)) {
        $resolvedWorkingDirectory = (Get-Location).Path
    }

    Push-Location $resolvedWorkingDirectory
    try {
        & $FilePath @Arguments
        $exitCode = $LASTEXITCODE
        if ($null -eq $exitCode) {
            $exitCode = 0
        }
        if ($exitCode -ne 0 -and -not $IgnoreFailure) {
            throw ("command failed with exit code {0}: {1} {2}" -f $exitCode, $FilePath, ($Arguments -join " "))
        }
        return $exitCode
    } finally {
        Pop-Location
    }
}

function Get-Pm2AppNamesForProfile {
    param(
        [string]$SelectedProfile
    )

    switch ($SelectedProfile) {
        "compatibility" { return @("signaled-logs-collector") }
        "all" { return @("signalizing-engine", "correlation-engine", "log-rca-engine", "signaled-logs-collector") }
        default { return @("signalizing-engine", "correlation-engine", "log-rca-engine") }
    }
}

function Restart-Pm2Services {
    param(
        [string]$RepoRoot,
        [string]$SelectedProfile
    )

    $pm2Exe = Resolve-Executable -Name "pm2"

    if ($SelectedProfile -eq "compatibility") {
        $collectorCwd = Join-Path $RepoRoot "log_signal_processor"
        $collectorScript = ".\bin\signaled-logs-collector.exe"
        $collectorArgs = @(
            "start",
            $collectorScript,
            "--name", "signaled-logs-collector",
            "--cwd", $collectorCwd,
            "--",
            "--config", ".\config.yml"
        )
        Invoke-ExternalCommand -FilePath $pm2Exe -Arguments $collectorArgs -WorkingDirectory $RepoRoot
        Write-Step "info" "started PM2 compatibility collector"
        return
    }

    Invoke-ExternalCommand -FilePath $pm2Exe -Arguments @("start", ".\ecosystem.config.js") -WorkingDirectory $RepoRoot
    Write-Step "info" "started PM2 services from ecosystem.config.js"

    if ($SelectedProfile -eq "all") {
        $collectorCwd = Join-Path $RepoRoot "log_signal_processor"
        $collectorScript = ".\bin\signaled-logs-collector.exe"
        $collectorArgs = @(
            "start",
            $collectorScript,
            "--name", "signaled-logs-collector",
            "--cwd", $collectorCwd,
            "--",
            "--config", ".\config.yml"
        )
        Invoke-ExternalCommand -FilePath $pm2Exe -Arguments $collectorArgs -WorkingDirectory $RepoRoot
        Write-Step "info" "started PM2 compatibility collector"
    }
}

function Invoke-Rebuild {
    param(
        [string]$RepoRoot,
        [string]$SelectedProfile,
        [switch]$SelectedRunTests,
        [switch]$SelectedSkipClean
    )

    $powershellExe = Resolve-Executable -Name "powershell" -Candidates @(
        "C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe"
    )

    $arguments = @(
        "-ExecutionPolicy", "Bypass",
        "-File", ".\rebuild_all.ps1",
        "-Profile", $SelectedProfile
    )
    if ($SelectedRunTests) {
        $arguments += "-RunTests"
    }
    if ($SelectedSkipClean) {
        $arguments += "-SkipClean"
    }

    Invoke-ExternalCommand -FilePath $powershellExe -Arguments $arguments -WorkingDirectory $RepoRoot
    Write-Step "info" ("rebuild completed for profile {0}" -f $SelectedProfile)
}

$repoRoot = (Get-Location).Path
$script:PhaseResults = New-Object System.Collections.Generic.List[object]
$correlationConfigPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $CorrelationConfig))
$rcaConfigPath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $RcaConfig))

if (-not (Test-Path -LiteralPath $correlationConfigPath)) {
    throw "correlation config not found at $correlationConfigPath"
}
if (-not (Test-Path -LiteralPath $rcaConfigPath)) {
    throw "RCA config not found at $rcaConfigPath"
}

$redisAddress = Get-YamlSectionValue -Path $correlationConfigPath -Section "redis" -Key "address"
$redisUsername = Get-YamlSectionValue -Path $correlationConfigPath -Section "redis" -Key "username"
$redisPassword = Get-YamlSectionValue -Path $correlationConfigPath -Section "redis" -Key "password"
$redisDbRaw = Get-YamlSectionValue -Path $correlationConfigPath -Section "redis" -Key "db"
$redisDb = if ([string]::IsNullOrWhiteSpace($redisDbRaw)) { 0 } else { [int]$redisDbRaw }
$redisKeyPrefix = Get-YamlSectionValue -Path $correlationConfigPath -Section "redis" -Key "key_prefix"

$elasticAddresses = @(Get-YamlSectionList -Path $correlationConfigPath -Section "elasticsearch" -Key "addresses")
if (@($elasticAddresses).Count -eq 0) {
    $singleElasticAddress = Get-YamlSectionValue -Path $correlationConfigPath -Section "elasticsearch" -Key "address"
    if (-not [string]::IsNullOrWhiteSpace($singleElasticAddress)) {
        $elasticAddresses = @($singleElasticAddress)
    }
}

$elasticUsername = Get-YamlSectionValue -Path $correlationConfigPath -Section "elasticsearch" -Key "username"
$elasticPassword = Get-YamlSectionValue -Path $correlationConfigPath -Section "elasticsearch" -Key "password"
$correlationIndex = Get-YamlSectionValue -Path $correlationConfigPath -Section "elasticsearch" -Key "index"
$currentCorrelationIndex = Get-YamlSectionValue -Path $correlationConfigPath -Section "elasticsearch" -Key "current_index"
$rcaCorrelationIndex = Get-YamlSectionValue -Path $rcaConfigPath -Section "elasticsearch" -Key "correlation_index"

$correlationCheckpointDirectoryRaw = Get-YamlSectionValue -Path $correlationConfigPath -Section "engine" -Key "checkpoint_directory"
$correlationCheckpointDirectory = Get-AbsolutePath -BasePath $correlationConfigPath -RawPath $correlationCheckpointDirectoryRaw
$rcaResultsFileRaw = Get-YamlSectionValue -Path $rcaConfigPath -Section "storage" -Key "results_file"
$rcaResultsFile = Get-AbsolutePath -BasePath $rcaConfigPath -RawPath $rcaResultsFileRaw
$rcaCheckpointFileRaw = Get-YamlSectionValue -Path $rcaConfigPath -Section "storage" -Key "checkpoint_file"
$rcaCheckpointFile = Get-AbsolutePath -BasePath $rcaConfigPath -RawPath $rcaCheckpointFileRaw

$redisPattern = if ([string]::IsNullOrWhiteSpace($redisKeyPrefix)) { "Rca:*" } else { $redisKeyPrefix.TrimEnd(':') + ":*" }
$esPatterns = New-Object System.Collections.Generic.HashSet[string]
foreach ($value in @($correlationIndex, $currentCorrelationIndex, $rcaCorrelationIndex)) {
    if ([string]::IsNullOrWhiteSpace($value)) {
        continue
    }

    [void]$esPatterns.Add($value)
    if ($value -notlike "*`**") {
        [void]$esPatterns.Add("$value*")
    }
}
$elasticIndexPatterns = @($esPatterns.ToArray() | Sort-Object)

$targets = @()
if (-not $SkipRedis) {
    $targets += "Redis keys matching $redisPattern on $redisAddress (db $redisDb)"
}
if (-not $SkipElasticsearch) {
    $targets += "Elasticsearch index patterns: $($elasticIndexPatterns -join ', ')"
}
if (-not $SkipLocalFiles) {
    $targets += "Local path $correlationCheckpointDirectory"
    $targets += "Local path $rcaCheckpointFile"
    $targets += "Local path $rcaResultsFile"
}

Write-Step "info" "planned RCA reset targets:"
foreach ($target in $targets) {
    Write-Host ("  - {0}" -f $target)
}

if (-not $Force) {
    $caption = "Reset RCA state"
    $message = "This will delete RCA/correlation state in Redis, Elasticsearch, and local files. Continue?"
    if (-not $PSCmdlet.ShouldContinue($message, $caption)) {
        Write-Step "warn" "reset cancelled by user"
        exit 1
    }
}

if ($RestartPm2) {
    Invoke-Phase -Name "pm2-delete" -Action {
        Write-Step "info" ("stopping PM2 services for profile {0}" -f $Profile)
        $pm2Exe = Resolve-Executable -Name "pm2"
        $apps = Get-Pm2AppNamesForProfile -SelectedProfile $Profile
        foreach ($app in $apps) {
            $deleteExit = Invoke-ExternalCommand -FilePath $pm2Exe -Arguments @("delete", $app) -WorkingDirectory $repoRoot -IgnoreFailure
            if ($deleteExit -eq 0) {
                Write-Step "info" ("deleted PM2 app {0}" -f $app)
            } else {
                Write-Step "warn" ("PM2 app {0} was not deleted cleanly, continuing" -f $app)
            }
        }
    }
}

if (-not $SkipRedis) {
    Invoke-Phase -Name "redis-reset" -Action {
        Write-Step "info" ("resetting redis keys on {0}" -f $redisAddress)
        $redisSession = $null
        try {
            $redisSession = Open-RedisSession -Address $redisAddress -Username $redisUsername -Password $redisPassword -Database $redisDb
            $keys = @(Get-RedisKeys -Stream $redisSession.Stream -Pattern $redisPattern)
            if (@($keys).Count -eq 0) {
                Write-Step "info" "no matching redis keys found"
            } else {
                $deleted = Remove-RedisKeys -Stream $redisSession.Stream -Keys $keys
                Write-Step "info" ("deleted {0} redis keys" -f $deleted)
            }
        } finally {
            Close-RedisSession -Session $redisSession
        }
    }
}

if (-not $SkipElasticsearch) {
    Invoke-Phase -Name "elasticsearch-reset" -Action {
        Write-Step "info" "resetting elasticsearch correlation indices"
        $headers = Get-BasicAuthHeader -Username $elasticUsername -Password $elasticPassword
        foreach ($address in @($elasticAddresses)) {
            foreach ($pattern in @($elasticIndexPatterns)) {
                try {
                    Invoke-ElasticDelete -Address $address -IndexPattern $pattern -Headers $headers
                } catch {
                    Write-Step "warn" ("failed to delete elasticsearch pattern {0} on {1}: {2}" -f $pattern, $address, $_.Exception.Message)
                }
            }
        }
    }
}

if (-not $SkipLocalFiles) {
    Invoke-Phase -Name "local-reset" -Action {
        Write-Step "info" "resetting local checkpoint and result files"
        foreach ($path in @($correlationCheckpointDirectory, $rcaCheckpointFile, $rcaResultsFile)) {
            if (-not [string]::IsNullOrWhiteSpace($path)) {
                try {
                    Remove-LocalPath -Path $path
                } catch {
                    Write-Step "warn" ("failed to remove local path {0}: {1}" -f $path, $_.Exception.Message)
                }
            }
        }
    }
}

if ($Rebuild) {
    Invoke-Phase -Name "rebuild" -Action {
        Write-Step "info" ("rebuilding services for profile {0}" -f $Profile)
        Invoke-Rebuild -RepoRoot $repoRoot -SelectedProfile $Profile -SelectedRunTests:$RunTests -SelectedSkipClean:$SkipClean
    }
}

if ($RestartPm2) {
    Invoke-Phase -Name "pm2-start" -Action {
        Write-Step "info" ("starting PM2 services for profile {0}" -f $Profile)
        Restart-Pm2Services -RepoRoot $repoRoot -SelectedProfile $Profile
    }
}

Write-Step "info" "RCA state script completed"
Write-Host ""
Write-Host "Phase summary:"
foreach ($result in $script:PhaseResults) {
    if ($result.Status -eq "ok") {
        Write-Host ("  [OK] {0}" -f $result.Name)
    } else {
        Write-Host ("  [FAILED] {0}: {1}" -f $result.Name, $result.Message)
    }
}
