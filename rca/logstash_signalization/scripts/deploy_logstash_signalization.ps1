[CmdletBinding()]
param(
    [string]$RemoteHost = "10.0.4.132",
    [string]$User = "root",
    [int]$Port = 22,
    [string]$IdentityFile,
    [string]$ConfigFile = "deploy_logstash_signalization.config.psd1",
    [string]$RemoteScriptsDir = "/etc/logstash/scripts",
    [string]$RemoteRulesDir = "/etc/logstash/rules",
    [string]$RemoteRulesZip = "/etc/logstash/rules.zip",
    [string]$RemotePipelineConf = "/etc/logstash/conf.d/Linux_Pipeline_135098068173316952064_pl.conf",
    [string]$RemoteLogstashSettingsDir = "/etc/logstash",
    [string]$RemoteLogstashBin = "/usr/share/logstash/bin/logstash",
    [string]$RemoteLogstashStdout = "/var/log/logstash/manual-start.log",
    [bool]$UseSudo = $true,
    [switch]$UseNewRulesZip,
    [switch]$UseOldRulesZip,
    [switch]$SkipRestart,
    [switch]$KeepRemoteStaging
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$logstashDir = Join-Path $repoRoot "logstash_signalization"
$signalizingRulesDir = Join-Path $repoRoot "log_signalizing\rules"

$localRedisStreamer = Join-Path $logstashDir "signal_redis_streamer.rb"
$localRuleMatcher = Join-Path $logstashDir "signal_rule_matcher.rb"
$localPipelineConf = Join-Path $logstashDir "Linux_Pipeline_135098068173316952064_pl.conf"
$localExistingRulesZip = Join-Path $logstashDir "rules.zip"
$configData = @{}
$passwordFromConfig = $null

if (-not [System.IO.Path]::IsPathRooted($ConfigFile)) {
    $ConfigFile = Join-Path $scriptDir $ConfigFile
}

if (Test-Path -LiteralPath $ConfigFile) {
    $configData = Import-PowerShellDataFile -LiteralPath $ConfigFile

    if (-not $PSBoundParameters.ContainsKey("RemoteHost") -and $configData.ContainsKey("RemoteHost")) {
        $RemoteHost = [string]$configData["RemoteHost"]
    }

    if (-not $PSBoundParameters.ContainsKey("User") -and $configData.ContainsKey("User")) {
        $User = [string]$configData["User"]
    }

    if (-not $PSBoundParameters.ContainsKey("Port") -and $configData.ContainsKey("Port")) {
        $Port = [int]$configData["Port"]
    }

    if (-not $PSBoundParameters.ContainsKey("IdentityFile") -and $configData.ContainsKey("IdentityFile")) {
        $IdentityFile = [string]$configData["IdentityFile"]
    }

    if ($configData.ContainsKey("Password")) {
        $candidatePassword = [string]$configData["Password"]
        if (-not [string]::IsNullOrWhiteSpace($candidatePassword)) {
            $passwordFromConfig = $candidatePassword
        }
    }
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Quote-BashArgument {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + $Value.Replace("'", "'""'""'") + "'"
}

function Assert-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found in PATH."
    }
}

function Assert-PathExists {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Description not found: $Path"
    }
}

function Assert-NonEmptyFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Description
    )

    Assert-PathExists -Path $Path -Description $Description
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -le 0) {
        throw "$Description is empty: $Path"
    }
}

function Get-ZipMode {
    if ($UseNewRulesZip -and $UseOldRulesZip) {
        throw "Use either -UseNewRulesZip or -UseOldRulesZip, not both."
    }

    if ($UseNewRulesZip) {
        return "new"
    }

    if ($UseOldRulesZip) {
        return "old"
    }

    while ($true) {
        $answer = (Read-Host "Choose rules zip to deploy [new/old]").Trim().ToLowerInvariant()
        switch ($answer) {
            "new" { return "new" }
            "old" { return "old" }
            default { Write-Warning "Please enter either 'new' or 'old'." }
        }
    }
}

function New-LocalStagingDirectory {
    $path = Join-Path ([System.IO.Path]::GetTempPath()) ("logstash-signalization-deploy-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    New-Item -ItemType Directory -Path $path -Force | Out-Null
    return $path
}

function New-RulesZipFromSignalizingRules {
    param(
        [Parameter(Mandatory = $true)][string]$RulesDirectory,
        [Parameter(Mandatory = $true)][string]$DestinationZip
    )

    Assert-PathExists -Path $RulesDirectory -Description "Signalizing rules directory"
    $entries = Get-ChildItem -LiteralPath $RulesDirectory -Force
    if (-not $entries) {
        throw "Signalizing rules directory is empty: $RulesDirectory"
    }

    if (Test-Path -LiteralPath $DestinationZip) {
        Remove-Item -LiteralPath $DestinationZip -Force
    }

    Compress-Archive -LiteralPath ($entries.FullName) -DestinationPath $DestinationZip -Force
    Assert-NonEmptyFile -Path $DestinationZip -Description "Newly created rules zip"
}

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter()][string[]]$ArgumentList = @()
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($ArgumentList -join ' ')"
    }
}

function Invoke-ProcessCapture {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter()][string[]]$ArgumentList = @()
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FilePath
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true

    foreach ($arg in $ArgumentList) {
        [void]$psi.ArgumentList.Add($arg)
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    [void]$process.Start()

    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        StdOut = $stdout
        StdErr = $stderr
    }
}

function Get-SshCommonArguments {
    $args = @("-p", $Port.ToString())
    if ($IdentityFile) {
        $args += @("-i", $IdentityFile)
    }

    return $args
}

function Test-PasswordlessSsh {
    param(
        [Parameter(Mandatory = $true)][string]$RemoteTarget
    )

    $probeArgs = Get-SshCommonArguments
    $probeArgs += @(
        "-o", "BatchMode=yes",
        "-o", "PreferredAuthentications=publickey",
        "-o", "ConnectTimeout=8",
        $RemoteTarget,
        "true"
    )

    $result = Invoke-ProcessCapture -FilePath "ssh" -ArgumentList $probeArgs
    return ($result.ExitCode -eq 0)
}

function New-SshAskpassHelper {
    param(
        [Parameter(Mandatory = $true)][string]$Directory
    )

    $cmdPath = Join-Path $Directory "ssh-askpass.cmd"
    $jsPath = Join-Path $Directory "ssh-askpass.js"

    $cmdContent = @'
@echo off
cscript //nologo "%~dp0ssh-askpass.js"
'@

    $jsContent = @'
var shell = WScript.CreateObject("WScript.Shell");
var env = shell.Environment("PROCESS");
var password = env("CODEX_DEPLOY_SSH_PASSWORD");
WScript.StdOut.Write(password);
'@

    Set-Content -LiteralPath $cmdPath -Value $cmdContent -Encoding Ascii
    Set-Content -LiteralPath $jsPath -Value $jsContent -Encoding Ascii

    return $cmdPath
}

function Invoke-OpenSshCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter()][string[]]$ArgumentList = @(),
        [string]$Password,
        [string]$AskpassCommandPath
    )

    $originalAskpass = $env:SSH_ASKPASS
    $originalAskpassRequire = $env:SSH_ASKPASS_REQUIRE
    $originalDisplay = $env:DISPLAY
    $originalDeployPassword = $env:CODEX_DEPLOY_SSH_PASSWORD

    try {
        if ($Password -and $AskpassCommandPath) {
            $env:SSH_ASKPASS = $AskpassCommandPath
            $env:SSH_ASKPASS_REQUIRE = "force"
            $env:DISPLAY = "codex"
            $env:CODEX_DEPLOY_SSH_PASSWORD = $Password
        }

        $result = Invoke-ProcessCapture -FilePath $FilePath -ArgumentList $ArgumentList
        $stdout = $result.StdOut
        $stderr = $result.StdErr

        if (-not [string]::IsNullOrWhiteSpace($stdout)) {
            Write-Host $stdout.TrimEnd()
        }

        if ($result.ExitCode -ne 0) {
            if (-not [string]::IsNullOrWhiteSpace($stderr)) {
                Write-Error $stderr.TrimEnd()
            }
            throw "Command failed with exit code $($result.ExitCode): $FilePath $($ArgumentList -join ' ')"
        }

        if (-not [string]::IsNullOrWhiteSpace($stderr)) {
            Write-Warning $stderr.TrimEnd()
        }
    }
    finally {
        $env:SSH_ASKPASS = $originalAskpass
        $env:SSH_ASKPASS_REQUIRE = $originalAskpassRequire
        $env:DISPLAY = $originalDisplay
        $env:CODEX_DEPLOY_SSH_PASSWORD = $originalDeployPassword
    }
}

$localStagingDir = $null
$remoteTarget = $null
$askpassCommandPath = $null

try {
    Write-Step "Validating local prerequisites"
    Assert-Command -Name "ssh"
    Assert-Command -Name "scp"

    Assert-NonEmptyFile -Path $localRedisStreamer -Description "Redis streamer Ruby script"
    Assert-NonEmptyFile -Path $localRuleMatcher -Description "Rule matcher Ruby script"

    Assert-PathExists -Path $localPipelineConf -Description "Pipeline config"

    $zipMode = Get-ZipMode
    $localStagingDir = New-LocalStagingDirectory

    if ($zipMode -eq "new") {
        Write-Step "Creating a fresh rules zip from log_signalizing\\rules"
        $localRulesZip = Join-Path $localStagingDir "rules.zip"
        New-RulesZipFromSignalizingRules -RulesDirectory $signalizingRulesDir -DestinationZip $localRulesZip
    }
    else {
        Write-Step "Using the existing rules zip from logstash_signalization"
        $localRulesZip = $localExistingRulesZip
        Assert-NonEmptyFile -Path $localRulesZip -Description "Existing rules zip"
    }

    $localRemoteScript = Join-Path $localStagingDir "remote-deploy-logstash.sh"
    $remoteScriptContent = @'
#!/usr/bin/env bash
set -euo pipefail

STAGING_DIR="${1:?missing staging dir}"
REMOTE_SCRIPTS_DIR="${2:?missing scripts dir}"
REMOTE_RULES_DIR="${3:?missing rules dir}"
REMOTE_RULES_ZIP="${4:?missing rules zip path}"
REMOTE_PIPELINE_CONF="${5:?missing pipeline conf path}"
REMOTE_LOGSTASH_SETTINGS_DIR="${6:?missing logstash settings dir}"
REMOTE_LOGSTASH_BIN="${7:?missing logstash bin}"
REMOTE_LOGSTASH_STDOUT="${8:?missing logstash stdout path}"
SKIP_RESTART="${9:-0}"
KEEP_STAGING="${10:-0}"

log() {
    printf '[remote] %s\n' "$*"
}

fail() {
    printf '[remote] ERROR: %s\n' "$*" >&2
    exit 1
}

require_non_empty_file() {
    local path="$1"
    [[ -s "$path" ]] || fail "Required file missing or empty: $path"
}

quote_for_shell() {
    printf "%q" "$1"
}

cleanup() {
    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        if [[ "$KEEP_STAGING" != "1" && -d "$STAGING_DIR" ]]; then
            rm -rf "$STAGING_DIR"
        fi
        return
    fi

    if [[ "${ROLLBACK_NEEDED:-0}" == "1" ]]; then
        log "Deployment failed; attempting rollback."

        if [[ -n "${BACKUP_REDIS_STREAMER:-}" && -e "$BACKUP_REDIS_STREAMER" ]]; then
            cp -a "$BACKUP_REDIS_STREAMER" "$REMOTE_SCRIPTS_DIR/signal_redis_streamer.rb"
        fi

        if [[ -n "${BACKUP_RULE_MATCHER:-}" && -e "$BACKUP_RULE_MATCHER" ]]; then
            cp -a "$BACKUP_RULE_MATCHER" "$REMOTE_SCRIPTS_DIR/signal_rule_matcher.rb"
        fi

        if [[ -n "${BACKUP_PIPELINE_CONF:-}" && -e "$BACKUP_PIPELINE_CONF" ]]; then
            cp -a "$BACKUP_PIPELINE_CONF" "$REMOTE_PIPELINE_CONF"
        fi

        if [[ -n "${BACKUP_RULES_ZIP:-}" && -e "$BACKUP_RULES_ZIP" ]]; then
            cp -a "$BACKUP_RULES_ZIP" "$REMOTE_RULES_ZIP"
        fi

        if [[ -n "${BACKUP_RULES_DIR:-}" && -d "$BACKUP_RULES_DIR" ]]; then
            rm -rf "$REMOTE_RULES_DIR"
            mv "$BACKUP_RULES_DIR" "$REMOTE_RULES_DIR"
        fi

        if [[ "${SKIP_RESTART}" != "1" && -n "${ORIGINAL_LOGSTASH_PID:-}" ]]; then
            if ! kill -0 "$ORIGINAL_LOGSTASH_PID" 2>/dev/null; then
                log "Trying to bring the previous Logstash process back after rollback."
                start_logstash "${LOGSTASH_RUN_USER:-logstash}" || true
            fi
        fi
    fi
}

start_logstash() {
    local run_user="$1"
    local stdout_dir
    local escaped_bin
    local escaped_settings
    local escaped_stdout
    local start_command
    local new_pid

    stdout_dir="$(dirname "$REMOTE_LOGSTASH_STDOUT")"
    mkdir -p "$stdout_dir"
    touch "$REMOTE_LOGSTASH_STDOUT"

    if id "$run_user" >/dev/null 2>&1; then
        chown "$run_user":"$run_user" "$REMOTE_LOGSTASH_STDOUT" 2>/dev/null || true
    fi

    escaped_bin="$(quote_for_shell "$REMOTE_LOGSTASH_BIN")"
    escaped_settings="$(quote_for_shell "$REMOTE_LOGSTASH_SETTINGS_DIR")"
    escaped_stdout="$(quote_for_shell "$REMOTE_LOGSTASH_STDOUT")"
    start_command="nohup ${escaped_bin} --path.settings ${escaped_settings} >> ${escaped_stdout} 2>&1 & echo \$!"

    if [[ "$run_user" == "root" ]]; then
        new_pid="$(bash -lc "$start_command")"
    else
        new_pid="$(su -s /bin/bash "$run_user" -c "$start_command")"
    fi

    printf '%s' "$new_pid"
}

trap cleanup EXIT

INCOMING_DIR="$STAGING_DIR/incoming"
REMOTE_SETTINGS_PARENT="$(dirname "$REMOTE_LOGSTASH_SETTINGS_DIR")"
BACKUP_ROOT="$REMOTE_LOGSTASH_SETTINGS_DIR/.deploy-backups/$(date +%Y%m%d-%H%M%S)"
RULES_EXTRACT_DIR="$STAGING_DIR/rules-extracted"
NEW_RULES_DIR="$STAGING_DIR/rules-next"

ROLLBACK_NEEDED=0
ORIGINAL_LOGSTASH_PID=""
LOGSTASH_RUN_USER=""
BACKUP_REDIS_STREAMER=""
BACKUP_RULE_MATCHER=""
BACKUP_PIPELINE_CONF=""
BACKUP_RULES_ZIP=""
BACKUP_RULES_DIR=""

require_non_empty_file "$INCOMING_DIR/signal_redis_streamer.rb"
require_non_empty_file "$INCOMING_DIR/signal_rule_matcher.rb"
require_non_empty_file "$INCOMING_DIR/rules.zip"

command -v unzip >/dev/null 2>&1 || fail "'unzip' is required on the remote host."
[[ -x "$REMOTE_LOGSTASH_BIN" ]] || fail "Logstash binary not found or not executable: $REMOTE_LOGSTASH_BIN"

mkdir -p "$REMOTE_SCRIPTS_DIR" "$(dirname "$REMOTE_PIPELINE_CONF")" "$BACKUP_ROOT"
rm -rf "$RULES_EXTRACT_DIR" "$NEW_RULES_DIR"
mkdir -p "$RULES_EXTRACT_DIR" "$NEW_RULES_DIR"

log "Unpacking rules zip in remote staging."
unzip -oq "$INCOMING_DIR/rules.zip" -d "$RULES_EXTRACT_DIR"

RULES_SOURCE_DIR="$RULES_EXTRACT_DIR"
if [[ -d "$RULES_EXTRACT_DIR/rules" && -d "$RULES_EXTRACT_DIR/rules/services" ]]; then
    RULES_SOURCE_DIR="$RULES_EXTRACT_DIR/rules"
fi

[[ -d "$RULES_SOURCE_DIR/services" ]] || fail "Rules archive does not contain a top-level services directory."
cp -a "$RULES_SOURCE_DIR"/. "$NEW_RULES_DIR/"

if pgrep -f 'org\.logstash\.Logstash|/usr/share/logstash/bin/logstash' >/dev/null 2>&1; then
    ORIGINAL_LOGSTASH_PID="$(pgrep -o -f 'org\.logstash\.Logstash|/usr/share/logstash/bin/logstash')"
    LOGSTASH_RUN_USER="$(ps -o user= -p "$ORIGINAL_LOGSTASH_PID" | awk '{print $1}')"
fi

if [[ -z "$LOGSTASH_RUN_USER" ]]; then
    if id logstash >/dev/null 2>&1; then
        LOGSTASH_RUN_USER="logstash"
    else
        LOGSTASH_RUN_USER="root"
    fi
fi

log "Taking backups before replacement."

if [[ -e "$REMOTE_SCRIPTS_DIR/signal_redis_streamer.rb" ]]; then
    BACKUP_REDIS_STREAMER="$BACKUP_ROOT/signal_redis_streamer.rb"
    cp -a "$REMOTE_SCRIPTS_DIR/signal_redis_streamer.rb" "$BACKUP_REDIS_STREAMER"
fi

if [[ -e "$REMOTE_SCRIPTS_DIR/signal_rule_matcher.rb" ]]; then
    BACKUP_RULE_MATCHER="$BACKUP_ROOT/signal_rule_matcher.rb"
    cp -a "$REMOTE_SCRIPTS_DIR/signal_rule_matcher.rb" "$BACKUP_RULE_MATCHER"
fi

if [[ -e "$REMOTE_PIPELINE_CONF" ]]; then
    BACKUP_PIPELINE_CONF="$BACKUP_ROOT/$(basename "$REMOTE_PIPELINE_CONF")"
    cp -a "$REMOTE_PIPELINE_CONF" "$BACKUP_PIPELINE_CONF"
fi

if [[ -e "$REMOTE_RULES_ZIP" ]]; then
    BACKUP_RULES_ZIP="$BACKUP_ROOT/$(basename "$REMOTE_RULES_ZIP")"
    cp -a "$REMOTE_RULES_ZIP" "$BACKUP_RULES_ZIP"
fi

if [[ -d "$REMOTE_RULES_DIR" ]]; then
    BACKUP_RULES_DIR="$BACKUP_ROOT/rules"
    mv "$REMOTE_RULES_DIR" "$BACKUP_RULES_DIR"
fi

ROLLBACK_NEEDED=1

log "Replacing Ruby scripts and pipeline config atomically."
install -m 0644 "$INCOMING_DIR/signal_redis_streamer.rb" "$REMOTE_SCRIPTS_DIR/.signal_redis_streamer.rb.new"
mv -f "$REMOTE_SCRIPTS_DIR/.signal_redis_streamer.rb.new" "$REMOTE_SCRIPTS_DIR/signal_redis_streamer.rb"

install -m 0644 "$INCOMING_DIR/signal_rule_matcher.rb" "$REMOTE_SCRIPTS_DIR/.signal_rule_matcher.rb.new"
mv -f "$REMOTE_SCRIPTS_DIR/.signal_rule_matcher.rb.new" "$REMOTE_SCRIPTS_DIR/signal_rule_matcher.rb"

if [[ -e "$INCOMING_DIR/Linux_Pipeline_135098068173316952064_pl.conf" ]]; then
    install -m 0644 "$INCOMING_DIR/Linux_Pipeline_135098068173316952064_pl.conf" "$(dirname "$REMOTE_PIPELINE_CONF")/.Linux_Pipeline_135098068173316952064_pl.conf.new"
    mv -f "$(dirname "$REMOTE_PIPELINE_CONF")/.Linux_Pipeline_135098068173316952064_pl.conf.new" "$REMOTE_PIPELINE_CONF"
fi

log "Replacing rules zip and extracted rules directory."
install -m 0644 "$INCOMING_DIR/rules.zip" "$(dirname "$REMOTE_RULES_ZIP")/.rules.zip.new"
mv -f "$(dirname "$REMOTE_RULES_ZIP")/.rules.zip.new" "$REMOTE_RULES_ZIP"
mv "$NEW_RULES_DIR" "$REMOTE_RULES_DIR"

if [[ "$SKIP_RESTART" == "1" ]]; then
    log "Deployment completed without restart because restart was skipped."
    ROLLBACK_NEEDED=0
    exit 0
fi

if [[ -n "$ORIGINAL_LOGSTASH_PID" ]]; then
    log "Stopping current Logstash process PID $ORIGINAL_LOGSTASH_PID."
    kill "$ORIGINAL_LOGSTASH_PID" 2>/dev/null || true
    for _ in $(seq 1 30); do
        if ! kill -0 "$ORIGINAL_LOGSTASH_PID" 2>/dev/null; then
            break
        fi
        sleep 1
    done

    if kill -0 "$ORIGINAL_LOGSTASH_PID" 2>/dev/null; then
        log "PID $ORIGINAL_LOGSTASH_PID did not stop in time; sending SIGKILL."
        kill -9 "$ORIGINAL_LOGSTASH_PID"
    fi
else
    log "No running Logstash PID found; starting a fresh process."
fi

log "Starting Logstash as user $LOGSTASH_RUN_USER."
NEW_LOGSTASH_PID="$(start_logstash "$LOGSTASH_RUN_USER")"

sleep 5
if ! kill -0 "$NEW_LOGSTASH_PID" 2>/dev/null; then
    tail -n 100 "$REMOTE_LOGSTASH_STDOUT" >&2 || true
    fail "Logstash did not stay up after restart."
fi

log "Logstash restarted successfully with PID $NEW_LOGSTASH_PID."
ROLLBACK_NEEDED=0
'@

    Set-Content -LiteralPath $localRemoteScript -Value $remoteScriptContent -Encoding Ascii

    Write-Step "Preparing remote staging on $RemoteHost"
    $remoteTarget = "$User@$RemoteHost"
    $passwordlessSsh = Test-PasswordlessSsh -RemoteTarget $remoteTarget
    if ($passwordlessSsh) {
        Write-Host "Passwordless SSH is available for $remoteTarget." -ForegroundColor Green
    }
    elseif ($passwordFromConfig) {
        Write-Host "Using password from config file $ConfigFile for $remoteTarget." -ForegroundColor Yellow
        $askpassCommandPath = New-SshAskpassHelper -Directory $localStagingDir
    }
    else {
        Write-Warning "Passwordless SSH is not available for $remoteTarget. SSH and SCP may prompt for the password interactively."
    }

    $remoteStagingDir = "/tmp/logstash-signalization-deploy-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    $remoteIncomingDir = "$remoteStagingDir/incoming"
    $remoteScriptPath = "$remoteStagingDir/remote-deploy-logstash.sh"

    $sshArgs = Get-SshCommonArguments
    $scpArgs = @()
    if ($IdentityFile) {
        $scpArgs += @("-i", $IdentityFile)
    }
    $scpArgs += @("-P", $Port.ToString())

    if ($passwordFromConfig) {
        $sshArgs += @(
            "-o", "PreferredAuthentications=password,keyboard-interactive",
            "-o", "PubkeyAuthentication=no",
            "-o", "NumberOfPasswordPrompts=1"
        )
        $scpArgs += @(
            "-o", "PreferredAuthentications=password,keyboard-interactive",
            "-o", "PubkeyAuthentication=no",
            "-o", "NumberOfPasswordPrompts=1"
        )
    }

    $mkdirCommand = "mkdir -p $(Quote-BashArgument $remoteIncomingDir)"
    Invoke-OpenSshCommand -FilePath "ssh" -ArgumentList ($sshArgs + @($remoteTarget, $mkdirCommand)) -Password $passwordFromConfig -AskpassCommandPath $askpassCommandPath

    Write-Step "Uploading deployment payload to remote staging"
    $scpArgs += @(
        $localRedisStreamer,
        $localRuleMatcher,
        $localPipelineConf,
        $localRulesZip,
        $localRemoteScript,
        "$remoteTarget`:$remoteIncomingDir/"
    )

    Invoke-OpenSshCommand -FilePath "scp" -ArgumentList $scpArgs -Password $passwordFromConfig -AskpassCommandPath $askpassCommandPath

    Write-Step "Running remote deployment with staging, backups, replacement, and restart"
    $skipRestartFlag = if ($SkipRestart) { "1" } else { "0" }
    $keepStagingFlag = if ($KeepRemoteStaging) { "1" } else { "0" }
    $sudoPrefix = if ($UseSudo -and $User -ne "root") { "sudo " } else { "" }
    $moveScriptCommand = "mv $(Quote-BashArgument "$remoteIncomingDir/remote-deploy-logstash.sh") $(Quote-BashArgument $remoteScriptPath) && chmod 700 $(Quote-BashArgument $remoteScriptPath)"
    Invoke-OpenSshCommand -FilePath "ssh" -ArgumentList ($sshArgs + @($remoteTarget, $moveScriptCommand)) -Password $passwordFromConfig -AskpassCommandPath $askpassCommandPath

    $remoteCommand = @(
        "$sudoPrefix" + "bash",
        (Quote-BashArgument $remoteScriptPath),
        (Quote-BashArgument $remoteStagingDir),
        (Quote-BashArgument $RemoteScriptsDir),
        (Quote-BashArgument $RemoteRulesDir),
        (Quote-BashArgument $RemoteRulesZip),
        (Quote-BashArgument $RemotePipelineConf),
        (Quote-BashArgument $RemoteLogstashSettingsDir),
        (Quote-BashArgument $RemoteLogstashBin),
        (Quote-BashArgument $RemoteLogstashStdout),
        (Quote-BashArgument $skipRestartFlag),
        (Quote-BashArgument $keepStagingFlag)
    ) -join " "

    Invoke-OpenSshCommand -FilePath "ssh" -ArgumentList ($sshArgs + @($remoteTarget, $remoteCommand)) -Password $passwordFromConfig -AskpassCommandPath $askpassCommandPath

    Write-Step "Deployment finished successfully"
    Write-Host "Remote host:          $RemoteHost"
    Write-Host "Rules zip mode:       $zipMode"
    Write-Host "Remote staging dir:   $remoteStagingDir"
    Write-Host "Restart skipped:      $($SkipRestart.IsPresent)"
    Write-Host "Keep remote staging:  $($KeepRemoteStaging.IsPresent)"
}
finally {
    if ($localStagingDir -and (Test-Path -LiteralPath $localStagingDir)) {
        Remove-Item -LiteralPath $localStagingDir -Recurse -Force
    }
}
